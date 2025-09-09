"""
DG-LAB WebSocket 设备服务实现

基于WebSocketController的纯WebSocket设备连接服务，只负责硬件通信，
不包含任何业务逻辑。所有业务逻辑由OSCActionService统一处理。
"""

import asyncio
import logging
from typing import Optional, List

from core.websocket import websocket_models

import pydglab_ws
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap

from core.core_interface import CoreInterface
from core.osc_common import Pulse
from core.websocket import WebSocketController
from core.recording import IPulseRecordHandler, BaseRecordHandler, IPulsePlaybackHandler, BasePlaybackHandler
from core.recording.recording_models import RecordingSnapshot
from models import Channel, ConnectionState, StrengthData, PulseOperation, StrengthOperationType, PlaybackMode, FramesEventType, FramesEventCallback, PlaybackModeChangedCallback, ProgressChangedCallback
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
        
        # 外部回调（可选）
        self._progress_changed_callback: Optional[ProgressChangedCallback] = None
        self._frames_event_callback: Optional[FramesEventCallback] = None
        self._playback_mode_changed_callback: Optional[PlaybackModeChangedCallback] = None

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
        self._websocket_controller.set_progress_changed_callback(self._on_progress_changed)
        self._websocket_controller.set_frames_event_callback(self._on_frames_event)
        self._websocket_controller.set_playback_mode_changed_callback(self._on_playback_mode_changed)

    # ============ 回调处理方法 ============

    async def _on_qrcode_generated(self, qr_code: str) -> None:
        """处理二维码生成回调"""
        qrcode_image: QPixmap = generate_qrcode(qr_code)
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

    async def _on_feedback_button(self, button: pydglab_ws.FeedbackButton) -> None:
        """处理反馈按钮回调"""
        logger.info(f"App 触发了反馈按钮：{button.name}")
        # 可以在这里添加按钮响应逻辑

    async def _on_ret_code(self, ret_code: pydglab_ws.RetCode) -> None:
        """处理返回码回调"""
        if ret_code == pydglab_ws.RetCode.CLIENT_DISCONNECTED:
            logger.info("App 已断开连接，你可以尝试重新扫码进行连接绑定")
        elif ret_code == pydglab_ws.RetCode.SUCCESS:
            logger.debug("收到心跳响应")
        else:
            logger.warning(f"收到未处理的返回码: {ret_code}")

    def _on_data_sync(self) -> None:
        """处理数据同步通知（用于录制和播放进度更新）"""
        # 处理录制数据同步
        if self._record_handler:
            self._record_handler.on_data_sync()
        
        # 处理播放进度更新
        # 进度更新通过回调系统处理
    
    def _on_progress_changed(self) -> None:
        if self._playback_handler:
            self._playback_handler.on_progress_changed()
        
        # 触发外部进度回调
        if self._progress_changed_callback:
            self._progress_changed_callback()
    
    def _on_frames_event(self, event_type: websocket_models.FramesEventType) -> None:
        """处理帧事件回调"""
        # 转换协议层事件类型到服务层事件类型
        service_event = self._convert_frames_event_type_from_websocket(event_type)
        
        # 转发到回放处理器（使用服务层类型）
        if self._playback_handler:
            self._playback_handler.on_frames_event(service_event)
        
        # 触发外部帧事件回调
        if self._frames_event_callback:
            self._frames_event_callback(service_event)
    
    def _on_playback_mode_changed(self, old_mode: websocket_models.PlaybackMode, new_mode: websocket_models.PlaybackMode) -> None:
        """处理播放模式变更回调"""
        # 转换协议层播放模式到服务层播放模式
        service_old_mode = self._convert_playback_mode_from_websocket(old_mode)
        service_new_mode = self._convert_playback_mode_from_websocket(new_mode)
        
        # 转发到回放处理器（使用服务层类型）
        if self._playback_handler:
            self._playback_handler.on_playback_mode_changed(service_old_mode, service_new_mode)
        
        # 触发外部播放模式变更回调
        if self._playback_mode_changed_callback:
            self._playback_mode_changed_callback(service_old_mode, service_new_mode)

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

    async def reset_strength(self, channel: Channel) -> None:
        """重置通道强度为0（原始设备操作）"""
        await self._websocket_controller.set_strength(
            self._convert_channel_to_pydglab(channel),
            self._convert_strength_operation_to_pydglab(StrengthOperationType.SET_TO),
            0
        )

    async def increase_strength(self, channel: Channel) -> None:
        """增加通道强度（原始设备操作）"""
        await self._websocket_controller.set_strength(
            self._convert_channel_to_pydglab(channel),
            self._convert_strength_operation_to_pydglab(StrengthOperationType.INCREASE),
            1
        )

    async def decrease_strength(self, channel: Channel) -> None:
        """减少通道强度（原始设备操作）"""
        await self._websocket_controller.set_strength(
            self._convert_channel_to_pydglab(channel),
            self._convert_strength_operation_to_pydglab(StrengthOperationType.DECREASE),
            1
        )

    # ============ 波形数据操作（实现IDGLabService接口） ============

    async def set_pulse_data(self, channel: Channel, pulse: Optional[Pulse]) -> None:
        """设置指定通道的波形数据"""
        if pulse:
            self._websocket_controller.set_pulse_data(
                self._convert_channel_to_pydglab(channel),
                self._convert_pulse_operations_to_pydglab(pulse.data)
            )
        else:
            self._websocket_controller.clear_frame_data(
                self._convert_channel_to_pydglab(channel)
            )
    
    async def set_snapshots(self, snapshots: Optional[List[RecordingSnapshot]]) -> None:
        """直接播放录制快照列表"""
        if snapshots:
            self._websocket_controller.set_snapshots(snapshots)
        else:
            self._websocket_controller.clear_frames()
    
    async def pause_frames(self) -> None:
        """暂停波形数据"""
        self._websocket_controller.pause_frames()
    
    async def resume_frames(self) -> None:
        """继续波形数据"""
        self._websocket_controller.resume_frames()

    def get_frames_position(self) -> int:
        """获取播放位置"""
        return self._websocket_controller.get_frames_position()

    async def seek_frames_to_position(self, position: int) -> None:
        """跳转到指定位置"""
        if not self._websocket_controller.is_connected:
            raise RuntimeError("设备未连接")
        
        # 设置播放位置
        self._websocket_controller.set_frames_position(position)

    def get_current_pulse_data(self, channel: Channel) -> Optional[PulseOperation]:
        """获取指定通道当前的脉冲操作数据"""
        return self._websocket_controller.get_current_pulse_data(
            self._convert_channel_to_pydglab(channel)
        )

    # ============ 播放模式控制（实现IDGLabService接口） ============

    def set_playback_mode(self, mode: PlaybackMode) -> None:
        """设置播放模式（服务层接口）"""
        # 转换服务层播放模式到协议层播放模式
        protocol_mode = self._convert_playback_mode_to_websocket(mode)
        self._websocket_controller.set_playback_mode(protocol_mode)

    def get_playback_mode(self) -> PlaybackMode:
        """获取当前播放模式（服务层接口）"""
        # 从协议层获取播放模式并转换到服务层
        protocol_mode = self._websocket_controller.get_playback_mode()
        return self._convert_playback_mode_from_websocket(protocol_mode)

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

    def _convert_pulse_operations_to_pydglab(self, operations: List[PulseOperation]) -> List[pydglab_ws.PulseOperation]:
        """将models.PulseOperation转换为pydglab_ws.PulseOperation"""
        return operations

    def _convert_strength_data_from_pydglab(self, pydglab_data: pydglab_ws.StrengthData) -> StrengthData:
        """将pydglab_ws的StrengthData转换为models的StrengthData"""
        return {
            "strength": {Channel.A: pydglab_data.a, Channel.B: pydglab_data.b},
            "strength_limit": {Channel.A: pydglab_data.a_limit, Channel.B: pydglab_data.b_limit}
        }

    def _convert_playback_mode_to_websocket(self, mode: PlaybackMode) -> websocket_models.PlaybackMode:
        if mode == PlaybackMode.ONCE:
            return websocket_models.PlaybackMode.ONCE
        elif mode == PlaybackMode.LOOP:
            return websocket_models.PlaybackMode.LOOP

    def _convert_playback_mode_from_websocket(self, ws_mode: websocket_models.PlaybackMode) -> PlaybackMode:
        if ws_mode == websocket_models.PlaybackMode.ONCE:
            return PlaybackMode.ONCE
        elif ws_mode == websocket_models.PlaybackMode.LOOP:
            return PlaybackMode.LOOP
    
    def _convert_frames_event_type_from_websocket(self, ws_event: websocket_models.FramesEventType) -> FramesEventType:
        """转换协议层帧事件类型到服务层帧事件类型"""
        if ws_event == websocket_models.FramesEventType.COMPLETED:
            return FramesEventType.COMPLETED
        elif ws_event == websocket_models.FramesEventType.LOOPED:
            return FramesEventType.LOOPED

    # ============ 回调设置方法 ============
    
    def set_progress_changed_callback(self, callback: Optional[ProgressChangedCallback]) -> None:
        """设置播放进度变更回调"""
        self._progress_changed_callback = callback
    
    def set_frames_event_callback(self, callback: Optional[FramesEventCallback]) -> None:
        """设置帧事件回调"""
        self._frames_event_callback = callback
    
    def set_playback_mode_changed_callback(self, callback: Optional[PlaybackModeChangedCallback]) -> None:
        """设置播放模式变更回调"""
        self._playback_mode_changed_callback = callback

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

        def _get_current_pulse_data(self, channel: Channel) -> PulseOperation:
            """获取指定通道当前的脉冲操作数据"""
            return self._websocket_service.get_current_pulse_data(channel) or ((10, 10, 10, 10), (0, 0, 0, 0))

        def _get_current_strength(self, channel: Channel) -> int:
            """获取指定通道当前的强度值"""
            last_strength = self._websocket_service.get_last_strength()
            if last_strength:
                return last_strength['strength'].get(channel, 0)
            return 0

    class _WebSocketPlaybackHandler(BasePlaybackHandler):
        """WebSocket回放处理器"""
        
        def __init__(self, websocket_service: 'DGLabWebSocketService') -> None:
            super().__init__()
            self._websocket_service = websocket_service
        
        def get_current_position(self) -> int:
            """获取当前播放位置"""
            return self._websocket_service.get_frames_position()
        
        async def _start_playback(self, snapshots: List[RecordingSnapshot]) -> None:
            """启动controller的快照播放"""
            await self._websocket_service.set_snapshots(snapshots)

        async def _stop_playback(self) -> None:
            """停止controller的播放并清理设备状态"""
            await self._websocket_service.reset_strength(Channel.A)
            await self._websocket_service.reset_strength(Channel.B)
            await self._websocket_service.set_snapshots(None)

        async def _pause_playback(self) -> None:
            """暂停controller的播放但保持设备状态"""
            await self._websocket_service.pause_frames()

        async def _resume_playback(self) -> None:
            """从暂停状态继续controller的播放"""
            await self._websocket_service.resume_frames()

        async def _seek_to_position(self, position: int) -> None:
            """跳转到指定位置"""
            await self._websocket_service.seek_frames_to_position(position)