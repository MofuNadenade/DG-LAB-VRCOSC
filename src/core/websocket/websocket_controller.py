"""
WebSocket控制器

负责WebSocket服务器的生命周期管理和数据处理，
使用回调模式与外部服务通信，避免直接依赖服务层。
"""

import asyncio
import logging
import time
from typing import List, Optional, Dict, Callable, Awaitable

from pydglab_ws import Channel, DGLabLocalClient, DGLabWSServer, FeedbackButton, PulseDataTooLong, PulseOperation, RetCode, StrengthData, StrengthOperationType

from core.osc_common import Pulse
from .websocket_models import WebSocketData, WebSocketChannelState

logger = logging.getLogger(__name__)


class WebSocketController:
    """WebSocket控制器
    
    负责：
    1. WebSocket服务器生命周期管理
    2. 客户端连接处理
    3. 数据收发管理
    4. 通道波形管理
    5. 回调处理
    """


    def __init__(self, ip: str, port: int, remote_address: Optional[str] = None):
        super().__init__()
        self._ip = ip
        self._port = port
        self._remote_address = remote_address
        self._server: Optional[DGLabWSServer] = None
        self._client: Optional[DGLabLocalClient] = None
        self._websocket_task: Optional[asyncio.Task[None]] = None
        self._data_send_task: Optional[asyncio.Task[None]] = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._channel_state: Dict[Channel, WebSocketChannelState] = {
            Channel.A: WebSocketChannelState(),
            Channel.B: WebSocketChannelState()
        }
        self._pulse_buffer_count = 0
        self._pulse_buffer_min = 10
        self._pulse_buffer_max = 20
        self._is_running: bool = False
        self._is_connected: bool = False
        self._connected_event: asyncio.Event = asyncio.Event()

        # 回调函数
        self._on_qrcode_generated: Optional[Callable[[str], Awaitable[None]]] = None
        self._on_connecting: Optional[Callable[[], Awaitable[None]]] = None
        self._on_connected: Optional[Callable[[], Awaitable[None]]] = None
        self._on_disconnected: Optional[Callable[[], Awaitable[None]]] = None
        self._on_reconnected: Optional[Callable[[], Awaitable[None]]] = None
        self._on_strength_data: Optional[Callable[[StrengthData], Awaitable[None]]] = None
        self._on_feedback_button: Optional[Callable[[FeedbackButton], Awaitable[None]]] = None
        self._on_ret_code: Optional[Callable[[RetCode], Awaitable[None]]] = None
        self._on_data_sync: Optional[Callable[[], None]] = None

    # ============ 回调设置 ============

    def set_qrcode_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """设置二维码生成回调"""
        self._on_qrcode_generated = callback

    def set_connecting_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """设置连接中回调"""
        self._on_connecting = callback

    def set_connected_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """设置连接成功回调"""
        self._on_connected = callback

    def set_disconnected_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """设置断开连接回调"""
        self._on_disconnected = callback

    def set_reconnected_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """设置重连成功回调"""
        self._on_reconnected = callback

    def set_strength_data_callback(self, callback: Callable[[StrengthData], Awaitable[None]]) -> None:
        """设置强度数据回调"""
        self._on_strength_data = callback

    def set_feedback_button_callback(self, callback: Callable[[FeedbackButton], Awaitable[None]]) -> None:
        """设置反馈按钮回调"""
        self._on_feedback_button = callback

    def set_ret_code_callback(self, callback: Callable[[RetCode], Awaitable[None]]) -> None:
        """设置返回码回调"""
        self._on_ret_code = callback
    
    def set_data_sync_callback(self, callback: Callable[[], None]) -> None:
        """设置数据同步回调"""
        self._on_data_sync = callback

    # ============ 公共接口 ============

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._is_running
    
    @property
    def is_connected(self) -> bool:
        """检查客户端是否已连接并绑定"""
        return self._is_connected

    async def start(self) -> bool:
        """启动WebSocket服务器"""
        if self._is_running:
            logger.warning("服务器已在运行")
            return True

        # 启动WebSocket任务（包含服务器、QR码生成和连接处理）
        self._websocket_task = asyncio.create_task(self._run_websocket_task(self._ip, self._port))
        
        # 启动波形发送任务
        self._data_send_task = asyncio.create_task(self._data_send_loop())

        # 设置运行状态
        self._is_running = True

        return True

    async def stop(self) -> None:
        """停止WebSocket服务器"""
        if not self._is_running:
            return
            
        logger.info("正在停止WebSocket服务...")
        self._is_running = False

        # 取消所有任务
        if self._websocket_task and not self._websocket_task.done():
            self._websocket_task.cancel()
            
        if self._data_send_task and not self._data_send_task.done():
            self._data_send_task.cancel()

        # 清理状态
        self._websocket_task = None
        self._data_send_task = None
        self._server = None
        self._client = None
        self._stop_event.clear()
        self._is_connected = False
        self._connected_event.clear()
        
        logger.info("WebSocket服务已停止")

    async def set_strength(self, channel: Channel, operation_type: StrengthOperationType, value: int) -> None:
        """设置通道强度"""
        if self._client:
            await self._client.set_strength(channel, operation_type, value)

    def set_pulse_data(self, channel: Channel, pulse: Optional[Pulse]) -> None:
        """设置指定通道的波形数据"""
        if pulse:
            self._channel_state[channel].set_pulse_data(pulse.data)
        else:
            self._channel_state[channel].clear_pulse_data()

    def get_current_pulse_data(self, channel: Channel) -> Optional[PulseOperation]:
        """获取指定通道当前播放的脉冲操作数据"""
        return self._channel_state[channel].get_current_playing_pulse()

    # ============ 内部实现 ============

    async def _run_websocket_task(self, ip: str, port: int) -> None:
        """运行WebSocket的异步任务，包含服务器、QR码生成和连接处理"""
        try:
            # 创建服务器实例
            self._server = DGLabWSServer(ip, port, 60)

            async with self._server:
                logger.info(f"WebSocket服务器已启动，监听地址: {self._ip}:{self._port}")

                try:
                    # 创建本地客户端
                    self._client = self._server.new_local_client()
                    logger.debug("本地客户端已创建")
                    
                    # 生成二维码URL
                    url = self._client.get_qrcode(f"ws://{self._remote_address or ip}:{port}")
                    if not url:
                        logger.error("无法生成二维码URL")
                        return
                    
                    # 触发二维码生成回调
                    if self._on_qrcode_generated:
                        await self._on_qrcode_generated(url)
                    
                    # 直接处理连接生命周期，不再使用独立任务
                    await self._handle_connection_lifecycle(self._server)
                    
                except Exception as e:
                    logger.error(f"创建本地客户端或QR码失败: {e}")
                    self._client = None
                    return
        except OSError as e:
            if e.errno == 10048:  # 端口被占用
                logger.error(f"服务器端口被占用: {e}")
            else:
                logger.error(f"服务器运行异常: {e}")
            raise
        except Exception as e:
            logger.error(f"服务器运行异常: {e}")
            raise
        finally:
            logger.debug("WebSocket任务已退出")

    async def _data_send_loop(self) -> None:
        """数据发送循环"""
        try:
            next_time = time.time()
            while self._is_running:
                if not self.is_connected:
                    await self._connected_event.wait()
                    self._pulse_buffer_count = 0
                    next_time = time.time()
                    continue

                if self._pulse_buffer_count < self._pulse_buffer_min:
                    pulses_to_send = self._pulse_buffer_max - self._pulse_buffer_count
                    await self._send_multiple_pulse_data(pulses_to_send)
                    self._pulse_buffer_count += pulses_to_send

                if self._pulse_buffer_count > 0:
                    self._pulse_buffer_count -= 1

                # 推进逻辑播放位置（模拟设备播放进度）
                for channel in Channel:
                    self._channel_state[channel].advance_logical_playback()
                
                self._notify_data_sync()

                next_time += (0.1 - 0.01)  # 时间补偿，减少累积误差
                sleep_time = max(0, next_time - time.time())
                await asyncio.sleep(sleep_time)
                    
        except asyncio.CancelledError:
            logger.debug("波形发送任务被取消")
        except Exception as e:
            logger.error(f"波形发送任务中发生错误: {e}")

    async def _send_multiple_pulse_data(self, count: int) -> None:
        """批量发送多个脉冲数据包"""
        if not self._client:
            return
            
        for channel in Channel:
            state = self._channel_state[channel]
            pulses: List[PulseOperation] = []
            for _ in range(count):
                pulse_data = state.advance_buffer_for_send()
                if pulse_data:
                    pulses.append(pulse_data)
            
            if pulses:
                try:
                    await self._client.add_pulses(channel, *pulses)
                except PulseDataTooLong:
                    logger.warning(f"通道 {channel} 波形数据过长，发送失败")

    async def _send_pulse_data(self) -> None:
        """发送所有通道的波形数据"""
        if not self._client:
            return
            
        for channel in Channel:
            state = self._channel_state[channel]
            pulse_data = state.advance_buffer_for_send()
            if pulse_data:
                try:
                    await self._client.add_pulses(channel, pulse_data)
                except PulseDataTooLong:
                    logger.warning(f"通道 {channel} 波形数据过长，发送失败")
    
    def _notify_data_sync(self) -> None:
        """通知数据同步"""
        if self._on_data_sync:
            self._on_data_sync()


    async def _handle_connection_lifecycle(self, server: DGLabWSServer) -> None:
        """处理连接生命周期"""
        if not self._client:
            logger.error("无法获取客户端实例")
            return

        try:
            # 设置等待连接状态
            if self._on_connecting:
                await self._on_connecting()

            # 等待绑定
            logger.info("等待 DG-Lab App 扫码绑定...")
            await self._client.bind()

            # 获取客户端ID
            client_id = self._client.client_id
            if not client_id:
                logger.error("无法获取客户端ID")
                return
            
            # 更新连接状态
            self._is_connected = True
            self._connected_event.set()
            
            # 触发连接成功回调
            if self._on_connected:
                await self._on_connected()
            logger.info(f"已与 App {self._client.target_id} 成功绑定")

            # 处理数据流
            try:
                async for data in self._client.data_generator():  # type: ignore
                    await self._handle_data(data)  # type: ignore
            finally:
                logger.debug("正在断开本地客户端连接")
                await server.remove_local_client(client_id)
                logger.debug("本地客户端已断开连接")

        except asyncio.CancelledError:
            logger.info("连接处理任务被取消")
        except Exception as e:
            logger.error(f"连接处理异常: {e}")
            # 更新连接状态
            self._is_connected = False
            self._connected_event.clear()
            
            if self._on_disconnected:
                await self._on_disconnected()

    async def _handle_data(self, data: WebSocketData) -> None:
        """统一数据处理入口"""
        try:
            if isinstance(data, StrengthData):
                await self._handle_strength_data(data)
            elif isinstance(data, FeedbackButton):
                await self._handle_feedback_button(data)
            elif data.__class__.__name__ == 'RetCode':
                await self._handle_ret_code(data)
            else:
                logger.warning(f"收到未知数据类型: {type(data)}, 值: {data}")
        except Exception as e:
            logger.error(f"数据处理异常: {e}", exc_info=True)

    async def _handle_strength_data(self, data: StrengthData) -> None:
        """处理强度数据"""
        # 日志记录
        logger.info(f"接收到数据包 - A通道: {data.a}, B通道: {data.b}")

        # 触发强度数据回调
        if self._on_strength_data:
            await self._on_strength_data(data)

    async def _handle_feedback_button(self, data: FeedbackButton) -> None:
        """处理反馈按钮"""
        logger.info(f"App 触发了反馈按钮：{data.name}")
        
        # 触发反馈按钮回调
        if self._on_feedback_button:
            await self._on_feedback_button(data)

    async def _handle_ret_code(self, data: RetCode) -> None:
        """处理返回码"""
        if data == RetCode.CLIENT_DISCONNECTED:
            await self._handle_client_disconnected()
        elif data == RetCode.SUCCESS:
            logger.debug("收到心跳响应")
        else:
            logger.warning(f"收到未处理的返回码: {data}")

        # 触发返回码回调
        if self._on_ret_code:
            await self._on_ret_code(data)

    async def _handle_client_disconnected(self) -> None:
        """处理客户端断开连接"""
        logger.info("App 已断开连接，你可以尝试重新扫码进行连接绑定")

        # 更新连接状态
        self._is_connected = False
        self._connected_event.clear()

        # 触发断开连接回调
        if self._on_disconnected:
            await self._on_disconnected()

        # 尝试重新绑定
        await self._attempt_reconnection()

    async def _attempt_reconnection(self) -> None:
        """尝试重新连接"""
        if self._client:
            try:
                await self._client.rebind()
                logger.info("重新绑定成功")
                
                # 更新连接状态
                self._is_connected = True
                self._connected_event.set()
                
                if self._on_reconnected:
                    await self._on_reconnected()
            except Exception as e:
                logger.error(f"重新绑定失败: {e}")
