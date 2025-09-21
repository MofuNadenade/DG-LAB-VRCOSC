"""
WebSocket控制器

负责WebSocket服务器的生命周期管理和数据处理，
使用回调模式与外部服务通信，避免直接依赖服务层。
"""

import asyncio
import logging
import time
from typing import List, Optional, Callable

from pydglab_ws import Channel, DGLabLocalClient, DGLabWSServer, FeedbackButton, PulseDataTooLong, PulseOperation, RetCode, StrengthData, StrengthOperationType

from core.recording.recording_models import ChannelSnapshot, RecordingSnapshot

from .websocket_models import (
    WebSocketData, PlaybackMode, FramesEventType,
    QRCodeCallback, ConnectionStateCallback, StrengthDataCallback, FeedbackButtonCallback,
    RetCodeCallback, DataSyncCallback, ProgressChangedCallback, FramesEventCallback,
    PlaybackModeChangedCallback
)
from .websocket_channel_state_handler import WebSocketChannelStateHandler

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
        # 通道状态处理器（统一管理AB通道）
        self._channel_handler = WebSocketChannelStateHandler()
        self._pulse_buffer_count = 0
        self._pulse_buffer_min = 5
        self._pulse_buffer_max = 5
        self._is_running: bool = False
        self._is_connected: bool = False
        self._connected_event: asyncio.Event = asyncio.Event()

        # 快照播放状态
        self._snapshot_playing = False
        self._snapshot_playback_task: Optional[asyncio.Task[None]] = None
        self._snapshot_progress_callback: Optional[Callable[[int, int], None]] = None
        
        # 暂停状态
        self._is_paused: bool = False

        # 播放模式相关状态
        self._current_playback_mode: PlaybackMode = PlaybackMode.ONCE
        self._last_frame_finished: bool = False

        # 回调函数 - 使用Protocol类型
        self._on_qrcode_generated: Optional[QRCodeCallback] = None
        self._on_connecting: Optional[ConnectionStateCallback] = None
        self._on_connected: Optional[ConnectionStateCallback] = None
        self._on_disconnected: Optional[ConnectionStateCallback] = None
        self._on_reconnected: Optional[ConnectionStateCallback] = None
        self._on_strength_data: Optional[StrengthDataCallback] = None
        self._on_feedback_button: Optional[FeedbackButtonCallback] = None
        self._on_ret_code: Optional[RetCodeCallback] = None
        self._on_data_sync: Optional[DataSyncCallback] = None
        self._on_progress_changed: Optional[ProgressChangedCallback] = None
        
        # 播放模式相关回调
        self._on_frames_event: Optional[FramesEventCallback] = None
        self._on_playback_mode_changed: Optional[PlaybackModeChangedCallback] = None

    # ============ 回调设置 ============

    def set_qrcode_callback(self, callback: Optional[QRCodeCallback]) -> None:
        """设置二维码生成回调"""
        self._on_qrcode_generated = callback

    def set_connecting_callback(self, callback: Optional[ConnectionStateCallback]) -> None:
        """设置连接中回调"""
        self._on_connecting = callback

    def set_connected_callback(self, callback: Optional[ConnectionStateCallback]) -> None:
        """设置连接成功回调"""
        self._on_connected = callback

    def set_disconnected_callback(self, callback: Optional[ConnectionStateCallback]) -> None:
        """设置断开连接回调"""
        self._on_disconnected = callback

    def set_reconnected_callback(self, callback: Optional[ConnectionStateCallback]) -> None:
        """设置重连成功回调"""
        self._on_reconnected = callback

    def set_strength_data_callback(self, callback: Optional[StrengthDataCallback]) -> None:
        """设置强度数据回调"""
        self._on_strength_data = callback

    def set_feedback_button_callback(self, callback: Optional[FeedbackButtonCallback]) -> None:
        """设置反馈按钮回调"""
        self._on_feedback_button = callback

    def set_ret_code_callback(self, callback: Optional[RetCodeCallback]) -> None:
        """设置返回码回调"""
        self._on_ret_code = callback
    
    def set_data_sync_callback(self, callback: Optional[DataSyncCallback]) -> None:
        """设置数据同步回调"""
        self._on_data_sync = callback

    def set_progress_changed_callback(self, callback: Optional[ProgressChangedCallback]) -> None:
        """设置进度回调"""
        self._on_progress_changed = callback

    def set_frames_event_callback(self, callback: Optional[FramesEventCallback]) -> None:
        """设置帧事件回调"""
        self._on_frames_event = callback

    def set_playback_mode_changed_callback(self, callback: Optional[PlaybackModeChangedCallback]) -> None:
        """设置播放模式变更回调"""
        self._on_playback_mode_changed = callback

    # ============ 播放模式接口 ============

    def set_playback_mode(self, mode: PlaybackMode) -> None:
        """设置播放模式"""
        old_mode = self._current_playback_mode
        self._current_playback_mode = mode
        self._channel_handler.set_playback_mode(mode)
        
        # 通知播放模式变更
        self._notify_playback_mode_changed(old_mode, mode)

    def get_playback_mode(self) -> PlaybackMode:
        """获取当前播放模式"""
        return self._current_playback_mode

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

    def set_pulse_data(self, channel: Channel, pulses: List[PulseOperation]) -> None:
        """设置指定通道的波形数据"""
        self._channel_handler.set_pulse_data(channel, pulses)
        # 重置播放状态，确保新数据可以正常播放
        self._is_paused = False
        self._last_frame_finished = False
    
    def set_snapshot_data(self, channel: Channel, snapshots: List[ChannelSnapshot]) -> None:
        """设置指定通道的快照数据"""
        self._channel_handler.set_snapshot_data(channel, snapshots)

    def clear_frame_data(self, channel: Channel) -> None:
        """清除指定通道的波形数据"""
        self._channel_handler.clear_frame_data(channel)

    def clear_frames(self) -> None:
        """清除所有通道的波形数据"""
        self._channel_handler.clear_all_frames()

    def set_snapshots(self, snapshots: List[RecordingSnapshot]) -> None:
        """设置录制快照列表"""
        self._channel_handler.set_snapshots(snapshots)
        # 重置播放状态，确保新数据可以正常播放
        self._is_paused = False
        self._last_frame_finished = False
        logger.info("开始播放快照序列")

    def pause_frames(self) -> None:
        """暂停波形数据"""
        self._is_paused = True

    def resume_frames(self) -> None:
        """继续波形数据"""
        self._is_paused = False    
    
    def get_frames_position(self) -> int:
        """获取帧播放位置"""
        return self._channel_handler.get_frame_position()

    def set_frames_position(self, position: int) -> None:
        """设置帧播放位置"""
        self._channel_handler.set_frame_position(position)
        
        # 通知进度变化
        if self._on_progress_changed:
            self._on_progress_changed()

    def get_current_pulse_data(self, channel: Channel) -> Optional[PulseOperation]:
        """获取指定通道当前播放的脉冲操作数据"""
        return self._channel_handler.get_current_pulse_data(channel)
    
    # ============ 通道状态处理器接口 ============
    
    @property
    def channel_handler(self) -> WebSocketChannelStateHandler:
        """获取通道状态处理器"""
        return self._channel_handler
    
    def has_any_frame_data(self) -> bool:
        """检查是否有任何通道有波形数据"""
        return self._channel_handler.has_any_frame_data()

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

                # 检查是否暂停
                if not self._is_paused:
                    # 未暂停时正常发送数据
                    if self._pulse_buffer_count < self._pulse_buffer_min:
                        pulses_to_send = self._pulse_buffer_max - self._pulse_buffer_count
                        await self._send_multiple_pulse_data(pulses_to_send)
                        self._pulse_buffer_count += pulses_to_send

                    if self._pulse_buffer_count > 0:
                        self._pulse_buffer_count -= 1

                    # 推进逻辑帧位置（模拟设备播放进度）
                    self._channel_handler.advance_logical_frame()
                    
                    # 检测播放状态变化并触发回调
                    current_finished = self._channel_handler.is_frame_sequence_finished()
                    
                    if not self._last_frame_finished and current_finished:
                        # 帧序列刚刚完成
                        if self._current_playback_mode == PlaybackMode.ONCE:
                            logger.info("帧序列播放已完成（单次模式）")
                            self._notify_frames_event(FramesEventType.COMPLETED)
                            # 清空快照数据，让后续循环发送空数据
                            self._channel_handler.clear_all_frames()
                        elif self._current_playback_mode == PlaybackMode.LOOP:
                            logger.info("帧序列播放完成，开始新循环")
                            self._notify_frames_event(FramesEventType.LOOPED)
                            # 重置帧位置开始新循环
                            self._channel_handler.reset_frame_progress()
                    
                    self._last_frame_finished = current_finished
                    
                    # 通知进度变化
                    if self._on_progress_changed:
                        self._on_progress_changed()
                else:
                    # 暂停时保持连接但不发送新数据，也不推进播放位置
                    pass
                
                self._notify_data_sync()

                next_time += (0.1 - 0.001)  # 时间补偿，减少累积误差
                sleep_time = max(0, next_time - time.time())
                await asyncio.sleep(sleep_time)
                    
        except asyncio.CancelledError:
            logger.debug("波形发送任务被取消")
        except Exception as e:
            logger.error(f"波形发送任务中发生错误: {e}")

    async def _send_multiple_pulse_data(self, count: int) -> None:
        """批量发送多个脉冲数据包 - 支持强度同步发送"""
        if not self._client:
            return
        
        # 使用处理器批量获取数据
        batch_data = self._channel_handler.advance_buffer_for_send_batch(count)
        
        for channel, channel_frames in batch_data.items():
            pulses: List[PulseOperation] = []
            strength_commands: List[int] = []
            
            for frame in channel_frames:
                if frame.pulse_operation:
                    pulses.append(frame.pulse_operation)
                
                # 收集强度变化命令
                if frame.target_strength is not None:
                    strength_commands.append(frame.target_strength)
            
            # 先发送强度命令
            for strength in strength_commands:
                await self._client.set_strength(channel, StrengthOperationType.SET_TO, strength)
            
            # 再发送脉冲数据
            if pulses:
                try:
                    await self._client.add_pulses(channel, *pulses)
                except PulseDataTooLong:
                    logger.warning(f"通道 {channel} 波形数据过长，发送失败")

    async def _send_pulse_data(self) -> None:
        """发送所有通道的波形数据 - 支持强度同步发送"""
        if not self._client:
            return
        
        # 获取所有通道的帧数据
        frame_data = self._channel_handler.advance_buffer_for_send()
            
        for channel in Channel:
            frame = frame_data[channel]
            
            # 先发送强度命令（如果有）
            if frame.target_strength is not None:
                await self._client.set_strength(channel, StrengthOperationType.SET_TO, frame.target_strength)
            
            # 再发送波形数据
            if frame.pulse_operation:
                try:
                    await self._client.add_pulses(channel, frame.pulse_operation)
                except PulseDataTooLong:
                    logger.warning(f"通道 {channel} 波形数据过长，发送失败")
    
    def _notify_data_sync(self) -> None:
        """通知数据同步"""
        if self._on_data_sync:
            self._on_data_sync()

    def _notify_frames_event(self, event_type: FramesEventType) -> None:
        """通知帧事件"""
        if self._on_frames_event:
            try:
                self._on_frames_event(event_type)
            except Exception as e:
                logger.error(f"Frames event callback failed: {e}")

    def _notify_playback_mode_changed(self, old_mode: PlaybackMode, new_mode: PlaybackMode) -> None:
        """通知播放模式变更"""
        if self._on_playback_mode_changed:
            try:
                self._on_playback_mode_changed(old_mode, new_mode)
            except Exception as e:
                logger.error(f"Playback mode changed callback failed: {e}")

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
