"""
DG-LAB WebSocket 设备服务实现

基于现有 DGLabService 的 WebSocket 连接实现，包含完整的连接管理功能。
"""

import asyncio
import math
from typing import Optional, List, Union, Dict, Any
import pydglab_ws
from pydglab_ws import DGLabLocalClient, DGLabWSServer, PulseDataTooLong
from models import Channel, StrengthData, PulseOperation, StrengthOperationType, FeedbackButton, RetCode
from core.dglab_pulse import Pulse
from PySide6.QtGui import QPixmap
from util import generate_qrcode
import logging
from gui.ui_interface import UIInterface, UIFeature, ConnectionState

logger = logging.getLogger(__name__)


def _convert_strength_data(pydglab_data: pydglab_ws.StrengthData) -> StrengthData:
    """将pydglab_ws的StrengthData转换为models的StrengthData"""
    return StrengthData(
        a=pydglab_data.a,
        b=pydglab_data.b,
        a_limit=pydglab_data.a_limit,
        b_limit=pydglab_data.b_limit
    )


class ChannelPulseTask:
    """通道波形任务管理"""
    
    def __init__(self, client: DGLabLocalClient, channel: Channel) -> None:
        self.client: DGLabLocalClient = client
        self.channel: Channel = channel
        self.pulse: Optional[Pulse] = None
        self.task: Optional[asyncio.Task[None]] = None
        self.data: List[PulseOperation] = []

    def set_pulse(self, pulse: Pulse) -> None:
        """设置波形"""
        old_pulse = self.pulse
        self.pulse = pulse
        if old_pulse is None or pulse.index != old_pulse.index:
            self.set_pulse_data(pulse.data)

    def set_pulse_data(self, data: List[PulseOperation]) -> None:
        """设置波形数据"""
        self.data = data
        if self.task and not self.task.cancelled() and not self.task.done():
            self.task.cancel()
        self.task = asyncio.create_task(self._internal_task(data))

    async def _internal_task(self, data: List[PulseOperation], send_duration: float = 5, send_interval: float = 1) -> None:
        try:
            await self.client.clear_pulses(self.channel)

            data_duration = len(data) * 0.1
            repeat_num = int(send_duration // data_duration)
            duration = repeat_num * data_duration
            pulse_num = int(50 // duration)
            pulse_data = data * repeat_num

            try:
                for _ in range(pulse_num):
                    await self.client.add_pulses(self.channel, *pulse_data)
                    await asyncio.sleep(send_interval)

                await asyncio.sleep(abs(data_duration - send_interval))
                while True:
                    await self.client.add_pulses(self.channel, *pulse_data)
                    await asyncio.sleep(data_duration)
            except PulseDataTooLong:
                logger.warning(f"发送失败，波形数据过长")
        except Exception as e:
            logger.error(f"send_pulse_task 任务中发生错误: {e}")


class DGLabWebSocketService:
    """DG-LAB WebSocket 设备服务实现
    
    基于 WebSocket 连接的 DG-LAB 设备控制服务，包含完整的连接管理功能。
    """
    
    class _ServerManager:
        """内部服务器管理器 - 封装服务器生命周期"""
        
        def __init__(self, service: 'DGLabWebSocketService'):
            self._service = service
            self._server: Optional[DGLabWSServer] = None
            self._client: Optional[DGLabLocalClient] = None
            self._server_task: Optional[asyncio.Task[None]] = None
            self._server_ready_event: asyncio.Event = asyncio.Event()
            self._stop_event: asyncio.Event = asyncio.Event()
        
        async def start(self, ip: str, port: int, remote_address: Optional[str] = None) -> bool:
            """启动服务器"""
            if self.is_running:
                logger.warning("服务器已在运行")
                return True
            
            try:
                # 创建服务器实例
                self._server = DGLabWSServer(ip, port, 60)
                
                # 启动服务器任务，在任务中使用 async with
                self._server_task = asyncio.create_task(self._run_server())
                
                # 等待服务器启动完成
                await asyncio.wait_for(self._server_ready_event.wait(), timeout=5.0)
                
                # 创建本地客户端
                self._client = self._server.new_local_client()
                
                # 生成二维码
                url = self._client.get_qrcode(f"ws://{remote_address or ip}:{port}")
                if not url:
                    raise RuntimeError("无法生成二维码")
                
                qrcode_image: QPixmap = generate_qrcode(url)
                self._service._ui_interface.update_qrcode(qrcode_image)
                
                # 更新服务引用
                self._service._client = self._client
                self._service._update_channel_pulse_tasks()
                
                logger.info(f"WebSocket服务器已启动，监听地址: {ip}:{port}")
                return True
                
            except Exception as e:
                logger.error(f"服务器启动失败: {e}")
                await self.stop()
                return False
        
        async def _run_server(self) -> None:
            """运行服务器的异步任务"""
            if not self._server:
                logger.error("服务器实例未创建")
                return
            
            try:
                async with self._server:
                    logger.debug("服务器上下文已进入")
                    self._server_ready_event.set()
                    try:
                        # 等待停止事件，而不是无意义的轮询
                        await self._stop_event.wait()
                    except asyncio.CancelledError:
                        logger.info("服务器任务被取消")
                        raise
            except asyncio.CancelledError:
                logger.info("服务器任务被取消")
                raise
            except Exception as e:
                logger.error(f"服务器运行异常: {e}")
                raise
            finally:
                logger.debug("服务器上下文已退出")
        
        async def stop(self) -> None:
            """停止服务器"""
            if self._server_task and not self._server_task.done():
                logger.info("正在停止WebSocket服务器...")
                # 设置停止事件，优雅地停止服务器
                self._stop_event.set()
                try:
                    await self._server_task
                except asyncio.CancelledError:
                    pass
                logger.info("WebSocket服务器已停止")
            
            # 清理状态
            self._server_task = None
            self._server = None
            self._client = None
            self._service._client = None
            self._server_ready_event.clear()
            self._stop_event.clear()
        
        @property
        def is_running(self) -> bool:
            return (self._server_task is not None and 
                    not self._server_task.done() and 
                    self._server_ready_event.is_set())
        
        @property
        def client(self) -> Optional[DGLabLocalClient]:
            return self._client
    
    def __init__(self, ui_interface: UIInterface) -> None:
        # 移除client参数，改为内部管理
        self._ui_interface: UIInterface = ui_interface
        self._client: Optional[DGLabLocalClient] = None
        
        # 服务器管理器
        self._server_manager = self._ServerManager(self)
        
        # 连接状态管理
        self._connection_task: Optional[asyncio.Task[None]] = None
        self._is_connected: bool = False
        
        # 服务器停止通知事件（用于替代轮询）
        self._server_stopped_event: asyncio.Event = asyncio.Event()
        
        # 通道管理
        self._current_select_channel: Channel = Channel.A
        self._channel_pulse_tasks: Dict[Channel, ChannelPulseTask] = {}
        
        # 强度管理
        self._last_strength: Optional[StrengthData] = None
        self._dynamic_bone_modes: Dict[Channel, bool] = {Channel.A: False, Channel.B: False}
        
        # 波形管理
        self._pulse_modes: Dict[Channel, int] = {Channel.A: 0, Channel.B: 0}
        
        # 开火模式管理
        self._fire_mode_disabled: bool = False
        self._fire_mode_strength_step: int = 30
        self._fire_mode_active: bool = False
        self._fire_mode_lock: asyncio.Lock = asyncio.Lock()
        self._data_updated_event: asyncio.Event = asyncio.Event()
        self._fire_mode_origin_strengths: Dict[Channel, int] = {Channel.A: 0, Channel.B: 0}
        
        # 模式切换管理
        self._set_mode_timer: Optional[asyncio.Task[None]] = None
        
        # 面板控制
        self._enable_panel_control: bool = True

    # ============ 连接管理 ============
    
    async def start_server(self, ip: str, port: int, osc_port: int, remote_address: Optional[str] = None) -> bool:
        """启动WebSocket服务器"""
        if self._server_manager.is_running:
            logger.warning("服务器已在运行")
            return True
        
        # 重置停止事件
        self._server_stopped_event.clear()
        
        success = await self._server_manager.start(ip, port, remote_address)
        if success:
            # 启动连接处理任务
            self._connection_task = asyncio.create_task(self._handle_connection_lifecycle())
        
        return success
    
    async def stop_server(self) -> None:
        """停止WebSocket服务器"""
        # 停止连接处理任务
        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
            self._connection_task = None
        
        # 断开设备连接
        await self.disconnect()
        
        # 停止服务器
        await self._server_manager.stop()
        
        # 通知服务器已停止（用于替代轮询）
        self._server_stopped_event.set()
    
    def is_server_running(self) -> bool:
        """检查服务器运行状态"""
        return self._server_manager.is_running
    
    def get_qrcode_image(self) -> Optional[QPixmap]:
        """获取二维码图像（由服务器管理器生成）"""
        # 二维码已在服务器启动时生成并更新到UI
        return None
    
    def get_connection_state(self) -> ConnectionState:
        """获取当前连接状态"""
        if not self._server_manager.is_running:
            return ConnectionState.DISCONNECTED
        elif not self._is_connected:
            return ConnectionState.WAITING
        else:
            return ConnectionState.CONNECTED
    
    async def connect(self) -> bool:
        """连接设备（WebSocket连接由服务器管理器管理）"""
        self._is_connected = True
        return True
    
    async def disconnect(self) -> None:
        """断开设备连接"""
        self._is_connected = False
        # 取消所有波形任务
        for task_manager in self._channel_pulse_tasks.values():
            if task_manager.task and not task_manager.task.done():
                task_manager.task.cancel()
        
        # 取消模式切换定时器
        if self._set_mode_timer:
            self._set_mode_timer.cancel()
            self._set_mode_timer = None
    
    def is_connected(self) -> bool:
        """检查设备连接状态"""
        return self._is_connected
    
    def get_connection_type(self) -> str:
        """获取连接类型标识"""
        return "websocket"
    
    async def wait_for_server_stop(self) -> None:
        """等待服务器停止事件（用于替代轮询）"""
        await self._server_stopped_event.wait()

    # ============ 属性访问 ============
    
    @property
    def fire_mode_strength_step(self) -> int:
        """开火模式强度步进"""
        return self._fire_mode_strength_step

    @fire_mode_strength_step.setter
    def fire_mode_strength_step(self, value: int) -> None:
        self._fire_mode_strength_step = value

    @property
    def fire_mode_disabled(self) -> bool:
        """开火模式是否禁用"""
        return self._fire_mode_disabled

    @fire_mode_disabled.setter
    def fire_mode_disabled(self, value: bool) -> None:
        self._fire_mode_disabled = value

    @property
    def enable_panel_control(self) -> bool:
        """面板控制是否启用"""
        return self._enable_panel_control

    @enable_panel_control.setter
    def enable_panel_control(self, value: bool) -> None:
        self._enable_panel_control = value

    # ============ 状态查询 ============
    
    def get_current_channel(self) -> Channel:
        """获取当前选中的通道"""
        return self._current_select_channel
    
    def get_last_strength(self) -> Optional[StrengthData]:
        """获取最后的强度数据"""
        return self._last_strength
    
    def is_dynamic_bone_enabled(self, channel: Channel) -> bool:
        """检查指定通道的动骨模式是否启用"""
        return self._dynamic_bone_modes[channel]
    
    def get_pulse_mode(self, channel: Channel) -> int:
        """获取指定通道的波形模式索引"""
        return self._pulse_modes[channel]
    
    def get_current_pulse_name(self, channel: Channel) -> str:
        """获取指定通道当前波形的名称"""
        pulse_index = self.get_pulse_mode(channel)
        return self._ui_interface.pulse_registry.pulses[pulse_index].name

    # ============ 通道控制 ============
    
    async def set_channel(self, value: Union[int, float]) -> Optional[Channel]:
        """设置当前活动通道"""
        if value >= 0:
            self._current_select_channel = Channel.A if value <= 1 else Channel.B
            logger.info(f"set activate channel to: {self._current_select_channel}")
            # 更新 UI 显示
            if self._ui_interface:
                channel_name = "A" if self._current_select_channel == Channel.A else "B"
                self._ui_interface.update_current_channel_display(channel_name)
            return self._current_select_channel
        return None

    # ============ 强度控制 ============
    
    async def set_float_output(self, value: float, channel: Channel) -> None:
        """设置浮点输出强度（用于动骨模式）"""
        if not self._enable_panel_control or not self._client:
            return

        if value >= 0.0 and self._last_strength:
            if channel == Channel.A and self._dynamic_bone_modes[Channel.A]:
                final_output_a = math.ceil(self._map_value(value, self._last_strength.a_limit * 0.2, self._last_strength.a_limit))
                await self._client.set_strength(channel, StrengthOperationType.SET_TO, final_output_a)
            elif channel == Channel.B and self._dynamic_bone_modes[Channel.B]:
                final_output_b = math.ceil(self._map_value(value, self._last_strength.b_limit * 0.2, self._last_strength.b_limit))
                await self._client.set_strength(channel, StrengthOperationType.SET_TO, final_output_b)
    
    async def adjust_strength(self, operation_type: StrengthOperationType, value: int, channel: Channel) -> None:
        """调整通道强度"""
        if self._client:
            await self._client.set_strength(channel, operation_type, value)
    
    async def reset_strength(self, value: bool, channel: Channel) -> None:
        """重置通道强度为0"""
        if value and self._client:
            await self._client.set_strength(channel, StrengthOperationType.SET_TO, 0)
    
    async def increase_strength(self, value: bool, channel: Channel) -> None:
        """增加通道强度"""
        if value and self._client:
            await self._client.set_strength(channel, StrengthOperationType.INCREASE, 1)
    
    async def decrease_strength(self, value: bool, channel: Channel) -> None:
        """减少通道强度"""
        if value and self._client:
            await self._client.set_strength(channel, StrengthOperationType.DECREASE, 1)

    # ============ 波形控制 ============
    
    async def update_pulse_data(self) -> None:
        """更新设备上的波形数据"""
        pulse_a = self._ui_interface.pulse_registry.pulses[self._pulse_modes[Channel.A]]
        pulse_b = self._ui_interface.pulse_registry.pulses[self._pulse_modes[Channel.B]]
        logger.info(f"更新波形 A {pulse_a.name} B {pulse_b.name}")
        self._channel_pulse_tasks[Channel.A].set_pulse(pulse_a)
        self._channel_pulse_tasks[Channel.B].set_pulse(pulse_b)
    
    async def set_pulse_data(self, _: bool, channel: Channel, pulse_index: int, update_ui: bool = True) -> None:
        """设置指定通道的波形数据"""
        self._update_pulse_mode(channel, pulse_index)
        if update_ui:
            self._update_pulse_ui(channel, pulse_index)
        await self.update_pulse_data()
    
    async def set_test_pulse(self, channel: Channel, pulse: Pulse) -> None:
        """在指定通道播放测试波形"""
        self._channel_pulse_tasks[channel].set_pulse(pulse)
    
    def set_pulse_mode(self, channel: Channel, value: int) -> None:
        """设置指定通道的波形模式"""
        self._update_pulse_mode(channel, value)
        self._update_pulse_ui(channel, value)

    # ============ 模式控制 ============
    
    def set_dynamic_bone_mode(self, channel: Channel, enabled: bool) -> None:
        """设置指定通道的动骨模式"""
        self._dynamic_bone_modes[channel] = enabled
    
    async def set_mode(self, value: int, channel: Channel) -> None:
        """切换工作模式（延时触发）"""
        if value == 1:  # 按下按键
            if self._set_mode_timer is not None:
                self._set_mode_timer.cancel()
            self._set_mode_timer = asyncio.create_task(self._set_mode_timer_handle(channel))
        elif value == 0:  # 松开按键
            if self._set_mode_timer:
                self._set_mode_timer.cancel()
                self._set_mode_timer = None
    
    async def set_panel_control(self, value: float) -> None:
        """设置面板控制功能开关"""
        self._enable_panel_control = value > 0
        mode_name = "开启面板控制" if self._enable_panel_control else "已禁用面板控制"
        logger.info(f": {mode_name}")
        # 更新 UI 组件
        self._ui_interface.set_feature_state(UIFeature.PANEL_CONTROL, self._enable_panel_control, silent=True)
    
    async def set_strength_step(self, value: float) -> None:
        """设置开火模式步进值"""
        self._fire_mode_strength_step = math.floor(self._map_value(value, 0, 100))
        logger.info(f"current strength step: {self._fire_mode_strength_step}")
        # 更新 UI 组件
        self._ui_interface.set_strength_step(self._fire_mode_strength_step, silent=True)

    # ============ 开火模式 ============
    
    async def strength_fire_mode(self, value: bool, channel: Channel, fire_strength: int, last_strength: Optional[StrengthData]) -> None:
        """一键开火模式"""
        if self._fire_mode_disabled:
            return

        logger.info(f"Trigger FireMode: {value}")

        # 防止重复触发
        if value and self._fire_mode_active:
            logger.debug("已有开火操作在进行中，跳过本次开始请求")
            return
        if not value and not self._fire_mode_active:
            logger.debug("没有进行中的开火操作，跳过本次结束请求")
            return

        async with self._fire_mode_lock:
            if value:
                # 开始 fire mode
                self._fire_mode_active = True
                logger.debug(f"FIRE START {last_strength}")
                if last_strength and self._client:
                    if channel == Channel.A:
                        self._fire_mode_origin_strengths[Channel.A] = last_strength.a
                        await self._client.set_strength(
                            channel,
                            StrengthOperationType.SET_TO,
                            min(self._fire_mode_origin_strengths[Channel.A] + fire_strength, last_strength.a_limit)
                        )
                    elif channel == Channel.B:
                        self._fire_mode_origin_strengths[Channel.B] = last_strength.b
                        await self._client.set_strength(
                            channel,
                            StrengthOperationType.SET_TO,
                            min(self._fire_mode_origin_strengths[Channel.B] + fire_strength, last_strength.b_limit)
                        )
                self._data_updated_event.clear()
                await self._data_updated_event.wait()
            else:
                if self._client:
                    if channel == Channel.A:
                        await self._client.set_strength(channel, StrengthOperationType.SET_TO, self._fire_mode_origin_strengths[Channel.A])
                    elif channel == Channel.B:
                        await self._client.set_strength(channel, StrengthOperationType.SET_TO, self._fire_mode_origin_strengths[Channel.B])
                # 等待数据更新
                self._data_updated_event.clear()
                await self._data_updated_event.wait()
                # 结束 fire mode
                logger.debug(f"FIRE END {last_strength}")
                self._fire_mode_active = False

    # ============ 数据更新 ============
    
    def update_strength_data(self, strength_data: StrengthData) -> None:
        """更新强度数据（通常由连接层调用）"""
        self._last_strength = strength_data
        self._data_updated_event.set()

    # ============ 私有辅助方法 ============
    
    def _update_pulse_mode(self, channel: Channel, pulse_index: int) -> None:
        """更新波形模式索引"""
        self._pulse_modes[channel] = pulse_index
    
    def _update_pulse_ui(self, channel: Channel, pulse_index: int) -> None:
        """更新波形UI显示"""
        pulse_name = self._ui_interface.pulse_registry.pulses[pulse_index].name
        self._ui_interface.set_pulse_mode(channel, pulse_name, silent=True)
    
    async def _set_mode_timer_handle(self, channel: Channel) -> None:
        """模式切换计时器处理"""
        try:
            # 使用更精确的延迟，避免不必要的轮询
            await asyncio.sleep(1.0)

            new_mode = not self._dynamic_bone_modes[channel]
            self.set_dynamic_bone_mode(channel, new_mode)
            mode_name = "可交互模式" if new_mode else "面板设置模式"
            logger.info(f"通道 {self._get_channel_name(channel)} 切换为{mode_name}")
            # 更新UI
            ui_feature = self._get_dynamic_bone_ui_feature(channel)
            self._ui_interface.set_feature_state(ui_feature, new_mode, silent=True)
        except asyncio.CancelledError:
            logger.debug(f"通道 {self._get_channel_name(channel)} 模式切换计时器被取消")
            raise
    
    def _get_channel_name(self, channel: Channel) -> str:
        """获取通道名称"""
        return "A" if channel == Channel.A else "B"
    
    def _get_dynamic_bone_ui_feature(self, channel: Channel) -> UIFeature:
        """获取动骨模式对应的UI特性"""
        return UIFeature.DYNAMIC_BONE_A if channel == Channel.A else UIFeature.DYNAMIC_BONE_B
    
    def _map_value(self, value: float, min_value: float, max_value: float) -> float:
        """将值映射到指定范围"""
        return min_value + value * (max_value - min_value)
    
    # ============ 连接生命周期处理 ============
    
    async def _handle_connection_lifecycle(self) -> None:
        """处理连接生命周期"""
        client = self._server_manager.client
        if not client:
            logger.error("无法获取客户端实例")
            return
        
        try:
            # 设置等待连接状态
            self._ui_interface.set_connection_state(ConnectionState.WAITING)
            
            # 等待绑定
            logger.info("等待 DG-Lab App 扫码绑定...")
            await client.bind()
            self._is_connected = True
            self._ui_interface.on_client_connected()
            logger.info(f"已与 App {client.target_id} 成功绑定")
            
            # 处理数据流
            async for data in client.data_generator():
                await self._handle_data(data)
                
        except asyncio.CancelledError:
            logger.info("连接处理任务被取消")
            raise
        except Exception as e:
            logger.error(f"连接处理异常: {e}")
            self._is_connected = False
            self._ui_interface.on_client_disconnected()
    
    async def _handle_data(self, data: Any) -> None:
        """统一数据处理入口"""
        try:
            if isinstance(data, pydglab_ws.StrengthData):
                await self._handle_strength_data(data)
            elif isinstance(data, pydglab_ws.FeedbackButton):
                await self._handle_feedback_button(data)
            elif isinstance(data, pydglab_ws.RetCode):
                await self._handle_ret_code(data)
            else:
                logger.warning(f"收到未知数据类型: {type(data)}, 值: {data}")
        except Exception as e:
            logger.error(f"数据处理异常: {e}", exc_info=True)
    
    async def _handle_strength_data(self, data: pydglab_ws.StrengthData) -> None:
        """处理强度数据"""
        # 转换为models中的StrengthData类型
        models_strength_data = _convert_strength_data(data)
        
        # 首次接收数据时更新波形数据
        if self._last_strength is None:
            asyncio.create_task(self.update_pulse_data())
        
        # 更新内部状态
        self.update_strength_data(models_strength_data)
        
        # 日志记录
        logger.info(f"接收到数据包 - A通道: {data.a}, B通道: {data.b}")
        
        # 更新应用状态和UI
        self._ui_interface.update_status(models_strength_data)
    
    async def _handle_feedback_button(self, data: pydglab_ws.FeedbackButton) -> None:
        """处理反馈按钮"""
        logger.info(f"App 触发了反馈按钮：{data.name}")
        # 可以在这里添加按钮响应逻辑
    
    async def _handle_ret_code(self, data: pydglab_ws.RetCode) -> None:
        """处理返回码"""
        if data == pydglab_ws.RetCode.CLIENT_DISCONNECTED:
            await self._handle_client_disconnected()
        elif data == pydglab_ws.RetCode.SUCCESS:
            logger.debug("收到心跳响应")
        else:
            logger.warning(f"收到未处理的返回码: {data}")
    
    async def _handle_client_disconnected(self) -> None:
        """处理客户端断开连接"""
        logger.info("App 已断开连接，你可以尝试重新扫码进行连接绑定")
        
        # 更新连接状态
        self._is_connected = False
        self._ui_interface.on_client_disconnected()
        
        # 尝试重新绑定
        await self._attempt_reconnection()
    
    async def _attempt_reconnection(self) -> None:
        """尝试重新连接"""
        client = self._server_manager.client
        if client:
            try:
                await client.rebind()
                logger.info("重新绑定成功")
                self._is_connected = True
                self._ui_interface.on_client_reconnected()
            except Exception as e:
                logger.error(f"重新绑定失败: {e}")
    
    def _update_channel_pulse_tasks(self) -> None:
        """更新通道波形任务（当客户端变化时）"""
        if self._client:
            self._channel_pulse_tasks = {
                Channel.A: ChannelPulseTask(self._client, Channel.A),
                Channel.B: ChannelPulseTask(self._client, Channel.B)
            }
        else:
            self._channel_pulse_tasks.clear()
