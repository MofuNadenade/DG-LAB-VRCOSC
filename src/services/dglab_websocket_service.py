"""
DG-LAB WebSocket 设备服务实现

基于pydglab_ws库实现的纯WebSocket设备连接服务，只负责硬件通信，
不包含任何业务逻辑。所有业务逻辑由OSCActionService统一处理。
"""

import asyncio
import logging
from typing import Optional, List, Dict, Union

import pydglab_ws
from PySide6.QtGui import QPixmap
from pydglab_ws import DGLabLocalClient, DGLabWSServer, PulseDataTooLong

from core.core_interface import CoreInterface
from core.dglab_pulse import Pulse
from models import Channel, ConnectionState, StrengthData, PulseOperation, StrengthOperationType
from util import generate_qrcode

logger = logging.getLogger(__name__)


class DGLabWebSocketService:
    """DG-LAB WebSocket 设备服务实现
    
    纯粹的WebSocket连接管理和基础设备操作，实现IDGLabService接口。
    不包含业务逻辑（如动骨模式、开火模式等），这些由OSCActionService处理。
    """

    _DGLabWebSocketData = Union[pydglab_ws.StrengthData, pydglab_ws.FeedbackButton, pydglab_ws.RetCode]
    """DGLab WebSocket 服务可处理的数据类型"""

    class _ChannelPulseTask:
        """通道波形任务管理"""

        def __init__(self, service: 'DGLabWebSocketService', client: DGLabLocalClient, channel: Channel) -> None:
            super().__init__()
            self.service: DGLabWebSocketService = service
            self.client: DGLabLocalClient = client
            self.channel: Channel = channel
            self.pulse: Optional[Pulse] = None
            self.task: Optional[asyncio.Task[None]] = None
            self.data: List[PulseOperation] = []

        def set_pulse(self, pulse: Optional[Pulse]) -> None:
            """设置波形"""
            old_pulse = self.pulse
            self.pulse = pulse
            if pulse != old_pulse:
                if pulse:
                    self.set_pulse_data(pulse.data)
                else:
                    self.set_pulse_data([])

        def set_pulse_data(self, data: List[PulseOperation]) -> None:
            """设置波形数据"""
            self.data = data
            if self.task and not self.task.cancelled() and not self.task.done():
                self.task.cancel()
            self.task = asyncio.create_task(self._internal_task(data))

        async def _internal_task(self, data: List[PulseOperation], send_duration: float = 5,
                                 send_interval: float = 1) -> None:
            try:
                await self.client.clear_pulses(self.service._convert_channel_to_pydglab(self.channel))

                data_duration = len(data) * 0.1
                repeat_num = int(send_duration // data_duration)
                duration = repeat_num * data_duration
                pulse_num = int(50 // duration)
                pulse_data = data * repeat_num

                try:
                    for _ in range(pulse_num):
                        await self.client.add_pulses(self.service._convert_channel_to_pydglab(self.channel), *pulse_data)
                        await asyncio.sleep(send_interval)

                    await asyncio.sleep(abs(data_duration - send_interval))
                    while True:
                        await self.client.add_pulses(self.service._convert_channel_to_pydglab(self.channel), *pulse_data)
                        await asyncio.sleep(data_duration)
                except PulseDataTooLong:
                    logger.warning("发送失败，波形数据过长")
            except Exception as e:
                logger.error(f"波形发送任务中发生错误: {e}")

    class _ServerManager:
        """内部服务器管理器 - 封装服务器生命周期"""

        def __init__(self, service: 'DGLabWebSocketService', ip: str, port: int, remote_address: Optional[str] = None):
            super().__init__()
            self._service = service
            self._ip = ip
            self._port = port
            self._remote_address = remote_address
            self._server: Optional[DGLabWSServer] = None
            self._client: Optional[DGLabLocalClient] = None
            self._server_task: Optional[asyncio.Task[None]] = None
            self._stop_event: asyncio.Event = asyncio.Event()
            self._client_event: asyncio.Event = asyncio.Event()
            self._is_running: bool = False

        async def start(self) -> bool:
            """启动服务器"""
            if self._is_running:
                logger.warning("服务器已在运行")
                return True

            try:
                # 启动服务器任务
                self._server_task = asyncio.create_task(self._run_server(self._ip, self._port))

                # 等待客户端就绪事件
                await self._client_event.wait()

                # 检查客户端是否成功创建
                if not self._client:
                    logger.error("本地客户端创建失败")
                    await self.stop()
                    return False

                # 生成二维码
                url = self._client.get_qrcode(f"ws://{self._remote_address or self._ip}:{self._port}")
                if not url:
                    logger.error("无法生成二维码")
                    await self.stop()
                    return False

                qrcode_image: QPixmap = generate_qrcode(url)
                self._service._core_interface.update_qrcode(qrcode_image)

                # 更新服务引用
                self._service._update_channel_pulse_tasks()

                # 设置运行状态
                self._is_running = True

                logger.info(f"WebSocket服务器已启动，监听地址: {self._ip}:{self._port}")
                return True

            except Exception as e:
                logger.error(f"服务器启动失败: {e}")
                await self.stop()
                return False

        async def _run_server(self, ip: str, port: int) -> None:
            """运行服务器的异步任务"""
            try:
                # 创建服务器实例
                self._server = DGLabWSServer(ip, port, 60)

                async with self._server:
                    logger.debug("服务器已连接")

                    try:
                        self._client = self._server.new_local_client()
                        logger.debug("本地客户端已创建")
                        self._client_event.set()
                    except Exception as e:
                        logger.error(f"创建本地客户端失败: {e}")
                        self._client = None
                        self._client_event.set()
                        return

                    try:
                        await self._stop_event.wait()
                    except asyncio.CancelledError:
                        logger.info("服务器任务被取消")
                        raise

                    try:
                        logger.debug("正在断开本地客户端连接")
                        client_id = self._client.client_id
                        if client_id:
                            await self._server.remove_local_client(client_id)
                        logger.debug("本地客户端已断开连接")
                    except Exception as e:
                        logger.error(f"断开本地客户端连接失败: {e}")
                        raise
            except OSError as e:
                if e.errno == 10048:  # 端口被占用
                    logger.error(f"服务器端口被占用: {e}")
                    raise
                else:
                    logger.error(f"服务器运行异常: {e}")
                    raise
            except Exception as e:
                logger.error(f"服务器运行异常: {e}")
                raise
            finally:
                logger.debug("服务器已退出")

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
            self._stop_event.clear()
            self._client_event.clear()
            self._is_running = False

        @property
        def is_running(self) -> bool:
            return self._is_running

        @property
        def client(self) -> Optional[DGLabLocalClient]:
            return self._client

    def __init__(self, core_interface: CoreInterface, ip: str, port: int, remote_address: Optional[str] = None) -> None:
        super().__init__()

        self._core_interface = core_interface

        # 服务器管理器
        self._server_manager: DGLabWebSocketService._ServerManager = self._ServerManager(self, ip, port, remote_address)

        # 连接状态管理
        self._connection_task: Optional[asyncio.Task[None]] = None

        # 服务器停止通知事件（用于替代轮询）
        self._server_stopped_event: asyncio.Event = asyncio.Event()

        # 通道波形任务管理
        self._channel_pulse_tasks: Dict[Channel, DGLabWebSocketService._ChannelPulseTask] = {}

        # 强度数据缓存
        self._last_strength: Optional[StrengthData] = None

    @property
    def client(self) -> Optional[DGLabLocalClient]:
        """获取当前客户端实例"""
        return self._server_manager.client

    # ============ 连接管理（实现IDGLabService接口） ============

    async def start_service(self) -> bool:
        """启动WebSocket服务器"""
        if self._server_manager.is_running:
            logger.warning("服务器已在运行")
            return True

        # 重置停止事件
        self._server_stopped_event.clear()

        success = await self._server_manager.start()
        if success:
            # 启动连接处理任务
            self._connection_task = asyncio.create_task(self._handle_connection_lifecycle())

        return success

    async def stop_service(self) -> None:
        """停止WebSocket服务器"""
        # 停止服务器
        await self._server_manager.stop()

        # 停止连接处理任务
        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
            self._connection_task = None

        # 取消所有波形任务
        for task_manager in self._channel_pulse_tasks.values():
            if task_manager.task and not task_manager.task.done():
                task_manager.task.cancel()

        # 通知服务器已停止（用于替代轮询）
        self._server_stopped_event.set()

    def is_service_running(self) -> bool:
        """检查服务器运行状态"""
        return self._server_manager.is_running

    def get_connection_type(self) -> str:
        """获取连接类型标识"""
        return "websocket"

    async def wait_for_server_stop(self) -> None:
        """等待服务器停止事件（用于替代轮询）"""
        await self._server_stopped_event.wait()

    # ============ 基础强度操作（实现IDGLabService接口） ============

    async def set_float_output(self, value: float, channel: Channel) -> None:
        """设置浮点输出强度（原始设备操作）"""
        if not self.client:
            return
        
        # 直接设置，不处理任何业务逻辑（如动骨模式映射）
        await self.client.set_strength(
            self._convert_channel_to_pydglab(channel),
            self._convert_strength_operation_to_pydglab(StrengthOperationType.SET_TO),
            int(value)
        )

    async def adjust_strength(self, operation_type: StrengthOperationType, value: int, channel: Channel) -> None:
        """调整通道强度（原始设备操作）"""
        if self.client:
            await self.client.set_strength(
                self._convert_channel_to_pydglab(channel),
                self._convert_strength_operation_to_pydglab(operation_type), 
                value
            )

    async def reset_strength(self, value: bool, channel: Channel) -> None:
        """重置通道强度为0（原始设备操作）"""
        if value and self.client:
            await self.client.set_strength(
                self._convert_channel_to_pydglab(channel),
                self._convert_strength_operation_to_pydglab(StrengthOperationType.SET_TO), 
                0
            )

    async def increase_strength(self, value: bool, channel: Channel) -> None:
        """增加通道强度（原始设备操作）"""
        if value and self.client:
            await self.client.set_strength(
                self._convert_channel_to_pydglab(channel),
                self._convert_strength_operation_to_pydglab(StrengthOperationType.INCREASE), 
                1
            )

    async def decrease_strength(self, value: bool, channel: Channel) -> None:
        """减少通道强度（原始设备操作）"""
        if value and self.client:
            await self.client.set_strength(
                self._convert_channel_to_pydglab(channel),
                self._convert_strength_operation_to_pydglab(StrengthOperationType.DECREASE), 
                1
            )

    # ============ 波形数据操作（实现IDGLabService接口） ============

    async def set_pulse_data(self, channel: Channel, pulse: Optional[Pulse]) -> None:
        """设置指定通道的波形数据"""
        if channel not in self._channel_pulse_tasks:
            logger.warning(f"通道 {channel} 任务未初始化，跳过波形设置")
            return
        self._channel_pulse_tasks[channel].set_pulse(pulse)


    # ============ 数据访问（实现IDGLabService接口） ============

    def get_last_strength(self) -> Optional[StrengthData]:
        """获取最后的强度数据"""
        return self._last_strength

    def update_strength_data(self, strength_data: StrengthData) -> None:
        """更新强度数据（通常由连接层调用）"""
        self._last_strength = strength_data

    # ============ 连接生命周期处理 ============

    async def _handle_connection_lifecycle(self) -> None:
        """处理连接生命周期"""
        client = self._server_manager.client
        if not client:
            logger.error("无法获取客户端实例")
            return

        try:
            # 设置等待连接状态
            self._core_interface.set_connection_state(ConnectionState.WAITING)

            # 等待绑定
            logger.info("等待 DG-Lab App 扫码绑定...")
            await client.bind()
            self._core_interface.on_client_connected()
            logger.info(f"已与 App {client.target_id} 成功绑定")

            # 处理数据流
            async for data in client.data_generator():  # type: ignore
                await self._handle_data(data)  # type: ignore

        except asyncio.CancelledError:
            logger.info("连接处理任务被取消")
            raise
        except Exception as e:
            logger.error(f"连接处理异常: {e}")
            self._core_interface.on_client_disconnected()

    async def _handle_data(self, data: _DGLabWebSocketData) -> None:
        """统一数据处理入口"""
        try:
            if isinstance(data, pydglab_ws.StrengthData):
                await self._handle_strength_data(data)
            elif isinstance(data, pydglab_ws.FeedbackButton):
                await self._handle_feedback_button(data)
            elif data.__class__.__name__ == 'RetCode':
                await self._handle_ret_code(data)
            else:
                logger.warning(f"收到未知数据类型: {type(data)}, 值: {data}")
        except Exception as e:
            logger.error(f"数据处理异常: {e}", exc_info=True)

    async def _handle_strength_data(self, data: pydglab_ws.StrengthData) -> None:
        """处理强度数据"""
        # 转换为models中的StrengthData类型
        models_strength_data = self._convert_strength_data_from_pydglab(data)

        # 更新内部状态
        self.update_strength_data(models_strength_data)

        # 日志记录
        logger.info(f"接收到数据包 - A通道: {data.a}, B通道: {data.b}")

        # 更新应用状态和UI
        self._core_interface.update_status(models_strength_data)

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
        self._core_interface.on_client_disconnected()

        # 尝试重新绑定
        await self._attempt_reconnection()

    async def _attempt_reconnection(self) -> None:
        """尝试重新连接"""
        client = self._server_manager.client
        if client:
            try:
                await client.rebind()
                logger.info("重新绑定成功")
                self._core_interface.on_client_reconnected()
            except Exception as e:
                logger.error(f"重新绑定失败: {e}")

    def _update_channel_pulse_tasks(self) -> None:
        """更新通道波形任务（当客户端变化时）"""
        if self.client:
            self._channel_pulse_tasks = {
                Channel.A: DGLabWebSocketService._ChannelPulseTask(self, self.client, Channel.A),
                Channel.B: DGLabWebSocketService._ChannelPulseTask(self, self.client, Channel.B)
            }
            logger.debug("通道波形任务已初始化")
        else:
            self._channel_pulse_tasks.clear()
            logger.debug("通道波形任务已清空")

    # ============ 类型转换函数 ============

    def _convert_channel_to_pydglab(self, channel: Channel) -> pydglab_ws.Channel:
        """将models.Channel转换为pydglab_ws.Channel"""
        if channel == Channel.A:
            return pydglab_ws.Channel.A
        elif channel == Channel.B:
            return pydglab_ws.Channel.B

    def _convert_strength_operation_to_pydglab(self, op: StrengthOperationType) -> pydglab_ws.StrengthOperationType:
        """将models.StrengthOperationType转换为pydglab_ws.StrengthOperationType"""
        if op == StrengthOperationType.DECREASE:
            return pydglab_ws.StrengthOperationType.DECREASE
        elif op == StrengthOperationType.INCREASE:
            return pydglab_ws.StrengthOperationType.INCREASE
        elif op == StrengthOperationType.SET_TO:
            return pydglab_ws.StrengthOperationType.SET_TO

    def _convert_strength_data_from_pydglab(self, pydglab_data: pydglab_ws.StrengthData) -> StrengthData:
        """将pydglab_ws的StrengthData转换为models的StrengthData"""
        return StrengthData(
            a=pydglab_data.a,
            b=pydglab_data.b,
            a_limit=pydglab_data.a_limit,
            b_limit=pydglab_data.b_limit
        )