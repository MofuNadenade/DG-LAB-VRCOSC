"""
DG-LAB WebSocket 设备服务实现

基于WebSocketController的纯WebSocket设备连接服务，只负责硬件通信，
不包含任何业务逻辑。所有业务逻辑由OSCActionService统一处理。
"""

import asyncio
import logging
from typing import Optional

import pydglab_ws
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap

from core.core_interface import CoreInterface
from core.osc_common import Pulse
from core.websocket import WebSocketController
from core.recording import IPulseRecordHandler, BaseRecordHandler, IPulsePlaybackHandler, BasePlaybackHandler
from core.recording.recording_models import ChannelSnapshot
from models import Channel, ConnectionState, StrengthData, PulseOperation, StrengthOperationType
from services.dglab_service_interface import IDGLabDeviceService
from util import generate_qrcode

logger = logging.getLogger(__name__)


class WebSocketSignals(QObject):
    qrcode_updated = Signal(QPixmap)  # QR码更新信号


class DGLabWebSocketService(IDGLabDeviceService):
    """DG-LAB WebSocket 设备服务实现
    
    基于WebSocketController的纯WebSocket连接管理和基础设备操作，实现IDGLabService接口。
    不包含业务逻辑（如动骨模式、开火模式等），这些由OSCActionService处理。
    """

    def __init__(self, core_interface: CoreInterface, ip: str, port: int, remote_address: Optional[str] = None) -> None:
        super().__init__()

        self._core_interface = core_interface

        # 信号组件 - 使用组合模式
        self.signals: WebSocketSignals = WebSocketSignals()

        # WebSocket控制器
        self._websocket_controller: WebSocketController = WebSocketController(ip, port, remote_address)

        # 设置回调
        self._setup_controller_callbacks()

        # 服务器停止通知事件（用于替代轮询）
        self._server_stopped_event: asyncio.Event = asyncio.Event()

        # 强度数据缓存
        self._last_strength: Optional[StrengthData] = None
        
        # 录制处理器实例
        self._record_handler: DGLabWebSocketService._WebSocketRecordHandler = self._WebSocketRecordHandler(self)

        # 回放处理器实例
        self._playback_handler: DGLabWebSocketService._WebSocketPlaybackHandler = self._WebSocketPlaybackHandler(self)

    def _setup_controller_callbacks(self) -> None:
        """设置WebSocket控制器回调"""
        self._websocket_controller.set_qrcode_callback(self._on_qrcode_generated)
        self._websocket_controller.set_connecting_callback(self._on_connecting)
        self._websocket_controller.set_connected_callback(self._on_connected)
        self._websocket_controller.set_disconnected_callback(self._on_disconnected)
        self._websocket_controller.set_reconnected_callback(self._on_reconnected)
        self._websocket_controller.set_strength_data_callback(self._on_strength_data)
        self._websocket_controller.set_feedback_button_callback(self._on_feedback_button)
        self._websocket_controller.set_ret_code_callback(self._on_ret_code)
        self._websocket_controller.set_data_sync_callback(self._on_data_sync)

    # ============ 回调处理方法 ============

    async def _on_qrcode_generated(self, qrcode_url: str) -> None:
        """处理二维码生成回调"""
        qrcode_image: QPixmap = generate_qrcode(qrcode_url)
        self.signals.qrcode_updated.emit(qrcode_image)

    async def _on_connecting(self) -> None:
        """处理连接中回调"""
        self._core_interface.set_connection_state(ConnectionState.WAITING)

    async def _on_connected(self) -> None:
        """处理连接成功回调"""
        self._core_interface.on_client_connected()

    async def _on_disconnected(self) -> None:
        """处理断开连接回调"""
        self._core_interface.on_client_disconnected()

    async def _on_reconnected(self) -> None:
        """处理重连成功回调"""
        self._core_interface.on_client_reconnected()

    async def _on_strength_data(self, data: pydglab_ws.StrengthData) -> None:
        """处理强度数据回调"""
        # 转换为models中的StrengthData类型
        models_strength_data = self._convert_strength_data_from_pydglab(data)

        # 更新内部状态
        self.update_strength_data(models_strength_data)

        # 日志记录
        logger.info(f"接收到数据包 - A通道: {data.a}, B通道: {data.b}")

        # 更新应用状态和UI
        self._core_interface.on_strength_data_updated(models_strength_data)

    async def _on_feedback_button(self, data: pydglab_ws.FeedbackButton) -> None:
        """处理反馈按钮回调"""
        logger.info(f"App 触发了反馈按钮：{data.name}")
        # 可以在这里添加按钮响应逻辑

    async def _on_ret_code(self, data: pydglab_ws.RetCode) -> None:
        """处理返回码回调"""
        if data == pydglab_ws.RetCode.CLIENT_DISCONNECTED:
            logger.info("App 已断开连接，你可以尝试重新扫码进行连接绑定")
        elif data == pydglab_ws.RetCode.SUCCESS:
            logger.debug("收到心跳响应")
        else:
            logger.warning(f"收到未处理的返回码: {data}")

    def _on_data_sync(self) -> None:
        """处理数据同步通知（用于录制）"""
        if self._record_handler:
            self._record_handler.on_data_sync()

    # ============ 连接管理（实现IDGLabService接口） ============

    async def start_service(self) -> bool:
        """启动WebSocket服务器"""
        if self._websocket_controller.is_running:
            logger.warning("服务器已在运行")
            return True

        # 重置停止事件
        self._server_stopped_event.clear()

        success = await self._websocket_controller.start()
        return success

    async def stop_service(self) -> None:
        """停止WebSocket服务器"""
        # 停止服务器
        await self._websocket_controller.stop()

        # 通知服务器已停止（用于替代轮询）
        self._server_stopped_event.set()

    def is_service_running(self) -> bool:
        """检查服务器运行状态"""
        return self._websocket_controller.is_running

    def get_connection_type(self) -> str:
        """获取连接类型标识"""
        return "websocket"

    async def wait_for_server_stop(self) -> None:
        """等待服务器停止事件（用于替代轮询）"""
        await self._server_stopped_event.wait()

    # ============ 基础强度操作（实现IDGLabService接口） ============

    async def set_float_output(self, value: float, channel: Channel) -> None:
        """设置浮点输出强度（原始设备操作）"""
        await self._websocket_controller.set_strength(
            self._convert_channel_to_pydglab(channel),
            self._convert_strength_operation_to_pydglab(StrengthOperationType.SET_TO),
            int(value)
        )

    async def adjust_strength(self, operation_type: StrengthOperationType, value: int, channel: Channel) -> None:
        """调整通道强度（原始设备操作）"""
        await self._websocket_controller.set_strength(
            self._convert_channel_to_pydglab(channel),
            self._convert_strength_operation_to_pydglab(operation_type), 
            value
        )

    async def reset_strength(self, value: bool, channel: Channel) -> None:
        """重置通道强度为0（原始设备操作）"""
        if value:
            await self._websocket_controller.set_strength(
                self._convert_channel_to_pydglab(channel),
                self._convert_strength_operation_to_pydglab(StrengthOperationType.SET_TO), 
                0
            )

    async def increase_strength(self, value: bool, channel: Channel) -> None:
        """增加通道强度（原始设备操作）"""
        if value:
            await self._websocket_controller.set_strength(
                self._convert_channel_to_pydglab(channel),
                self._convert_strength_operation_to_pydglab(StrengthOperationType.INCREASE), 
                1
            )

    async def decrease_strength(self, value: bool, channel: Channel) -> None:
        """减少通道强度（原始设备操作）"""
        if value:
            await self._websocket_controller.set_strength(
                self._convert_channel_to_pydglab(channel),
                self._convert_strength_operation_to_pydglab(StrengthOperationType.DECREASE), 
                1
            )

    # ============ 波形数据操作（实现IDGLabService接口） ============

    async def set_pulse_data(self, channel: Channel, pulse: Optional[Pulse]) -> None:
        """设置指定通道的波形数据"""
        self._websocket_controller.set_pulse_data(
            self._convert_channel_to_pydglab(channel),
            pulse
        )

    # ============ 数据访问（实现IDGLabService接口） ============

    def get_last_strength(self) -> Optional[StrengthData]:
        """获取最后的强度数据"""
        return self._last_strength

    def update_strength_data(self, strength_data: StrengthData) -> None:
        """更新强度数据（通常由连接层调用）"""
        self._last_strength = strength_data

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
        return {
            "strength": {Channel.A: pydglab_data.a, Channel.B: pydglab_data.b},
            "strength_limit": {Channel.A: pydglab_data.a_limit, Channel.B: pydglab_data.b_limit}
        }

    # ============ 录制功能 ============

    def get_record_handler(self) -> IPulseRecordHandler:
        """创建脉冲录制处理器"""
        return self._record_handler
    
    def get_playback_handler(self) -> IPulsePlaybackHandler:
        """创建脉冲回放处理器"""
        return self._playback_handler

    class _WebSocketRecordHandler(BaseRecordHandler):
        """WebSocket录制处理器"""

        def __init__(self, websocket_service: 'DGLabWebSocketService') -> None:
            super().__init__()
            self._websocket_service = websocket_service

        def _get_current_pulse_data(self, channel: Channel) -> Optional[PulseOperation]:
            """获取指定通道当前的脉冲操作数据"""
            try:
                return self._websocket_service._websocket_controller.get_current_pulse_data(
                    self._websocket_service._convert_channel_to_pydglab(channel)
                )

            except Exception as e:
                logger.error(f"获取WebSocket通道{channel}脉冲操作失败: {e}")
                return None

        def _get_current_strength(self, channel: Channel) -> int:
            """获取指定通道当前的强度值"""
            try:
                last_strength = self._websocket_service.get_last_strength()
                if last_strength and 'strength' in last_strength:
                    return last_strength['strength'].get(channel, 0)

                return 0

            except Exception as e:
                logger.error(f"获取WebSocket通道{channel}强度失败: {e}")
                return 0

    class _WebSocketPlaybackHandler(BasePlaybackHandler):
        """WebSocket回放处理器"""
        
        def __init__(self, websocket_service: 'DGLabWebSocketService') -> None:
            super().__init__()
            self._websocket_service = websocket_service
        
        async def _apply_channel_data(self, channel: Channel, data: ChannelSnapshot) -> None:
            """应用通道数据到WebSocket设备"""
            try:
                # 1. 设置强度
                await self._websocket_service.adjust_strength(
                    operation_type=StrengthOperationType.SET_TO,
                    value=data.current_strength,
                    channel=channel
                )
                
                # 2. 设置波形数据
                if data.pulse_operation:
                    # 创建临时波形（只包含一个操作）
                    temp_pulse = Pulse(
                        pulse_id=-1,  # 临时ID
                        name="playback_temp", 
                        data=[data.pulse_operation]
                    )
                    await self._websocket_service.set_pulse_data(channel, temp_pulse)
                else:
                    # 清空波形数据
                    await self._websocket_service.set_pulse_data(channel, None)
                    
            except Exception as e:
                logger.error(f"应用WebSocket通道{channel}数据失败: {e}")

        async def _cleanup_device_state(self) -> None:
            """清理设备状态"""
            try:
                # 重置所有通道强度为0
                await self._websocket_service.adjust_strength(
                    operation_type=StrengthOperationType.SET_TO,
                    value=0,
                    channel=Channel.A
                )
                await self._websocket_service.adjust_strength(
                    operation_type=StrengthOperationType.SET_TO,
                    value=0,
                    channel=Channel.B
                )
                
                # 清空波形数据
                await self._websocket_service.set_pulse_data(Channel.A, None)
                await self._websocket_service.set_pulse_data(Channel.B, None)
                
            except Exception as e:
                logger.error(f"清理设备状态失败: {e}")