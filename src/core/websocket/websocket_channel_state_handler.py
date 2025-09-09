"""
WebSocket通道状态处理器

统一管理WebSocket连接的AB通道状态，提供统一的播放进度和数据管理接口
"""

from typing import Dict, List, Optional
from pydglab_ws import Channel, PulseOperation

from core.recording.recording_models import ChannelSnapshot, RecordingSnapshot
import models
from .websocket_models import WebSocketChannelState, WebSocketFrame, PlaybackMode


class WebSocketChannelStateHandler:
    """WebSocket通道状态处理器
    
    统一管理A/B通道的状态，提供：
    1. 统一的播放进度管理
    2. 双通道数据同步操作
    3. 简化的接口封装
    4. 播放状态协调
    
    设计原理：
    - buffer_index: 用于数据预发送，防止网络波动，可以超出logical范围
    - logical_index: 严格限定在有效数据范围内，用于UI显示和进度查询
    """

    def __init__(self) -> None:
        """初始化通道状态处理器"""
        super().__init__()
        self._channel_states: Dict[Channel, WebSocketChannelState] = {
            Channel.A: WebSocketChannelState(),
            Channel.B: WebSocketChannelState()
        }
        
        # 帧进度管理（AB通道同步）
        self._frame_buffer_index: int = 0   # 缓冲发送位置，可以超出范围
        self._frame_logical_index: int = 0  # 逻辑播放位置，严格限定在[0, max_length-1]
        
        # 播放模式
        self._playback_mode: PlaybackMode = PlaybackMode.ONCE
        
    # ============ 数据设置接口 ============
    
    def set_pulse_data(self, channel: Channel, pulses: List[PulseOperation]) -> None:
        """设置指定通道的波形数据"""
        self._channel_states[channel].set_pulse_data(pulses)
        self.reset_frame_progress()
    
    def set_snapshot_data(self, channel: Channel, snapshots: List[ChannelSnapshot]) -> None:
        """设置指定通道的快照数据"""
        self._channel_states[channel].set_snapshot_data(snapshots)
        self.reset_frame_progress()
    
    def set_snapshots(self, snapshots: List[RecordingSnapshot]) -> None:
        """设置录制快照列表，自动分配到对应通道"""
        channel_a_snapshots: List[ChannelSnapshot] = []
        channel_b_snapshots: List[ChannelSnapshot] = []

        for snapshot in snapshots:
            if models.Channel.A in snapshot.channels:
                channel_a_snapshots.append(snapshot.channels[models.Channel.A])
            if models.Channel.B in snapshot.channels:
                channel_b_snapshots.append(snapshot.channels[models.Channel.B])

        # 分别设置两个通道的快照数据
        if channel_a_snapshots:
            self.set_snapshot_data(Channel.A, channel_a_snapshots)
        if channel_b_snapshots:
            self.set_snapshot_data(Channel.B, channel_b_snapshots)
    
    def clear_frame_data(self, channel: Channel) -> None:
        """清除指定通道的波形数据"""
        self._channel_states[channel].clear_frame_data()
        self.reset_frame_progress()
    
    def clear_all_frames(self) -> None:
        """清除所有通道的波形数据"""
        for channel in Channel:
            self._channel_states[channel].clear_frame_data()
        self.reset_frame_progress()
    
    def set_playback_mode(self, mode: PlaybackMode) -> None:
        """设置播放模式，同时调整相关状态"""
        old_mode = self._playback_mode
        self._playback_mode = mode
        
        # 模式切换时的状态调整
        if old_mode != mode and self.has_any_frame_data():
            max_length = self._get_max_frames()
            if max_length > 0:
                # 确保logical_index在新模式下的有效性
                if mode == PlaybackMode.LOOP:
                    # 切换到循环模式：限制在有效范围内
                    self._frame_logical_index = self._frame_logical_index % max_length
                else:
                    # 切换到单次模式：限制在[0, max_length-1]
                    self._frame_logical_index = min(self._frame_logical_index, max_length - 1)
    
    def get_playback_mode(self) -> PlaybackMode:
        """获取当前播放模式"""
        return self._playback_mode
    
    # ============ 播放控制接口 ============
    
    def advance_buffer_for_send(self) -> Dict[Channel, WebSocketFrame]:
        """推进统一缓冲区并返回所有通道要发送的数据
        
        buffer_index用于数据预发送，防止网络波动，可以超出logical范围
        支持不同长度通道的独立循环播放
        """
        results: Dict[Channel, WebSocketFrame] = {}
        
        for channel in Channel:
            channel_state = self._channel_states[channel]
            frame_data = channel_state.frame_data
            
            if not frame_data:
                # 无数据：发送静默帧
                results[channel] = WebSocketFrame(((10, 10, 10, 10), (0, 0, 0, 0)), None)
            else:
                data_length = len(frame_data)
                
                if self._playback_mode == PlaybackMode.LOOP:
                    # 循环模式：每个通道独立循环
                    looped_frame = channel_state.get_looped_frame_data(self._frame_buffer_index)
                    results[channel] = looped_frame if looped_frame else WebSocketFrame(((10, 10, 10, 10), (0, 0, 0, 0)), None)
                else:
                    # 单次模式：检查边界，短通道循环播放直到最长通道结束
                    if self._frame_buffer_index < data_length:
                        results[channel] = frame_data[self._frame_buffer_index]
                    else:
                        # 超出该通道范围：循环播放该通道数据，直到所有通道都结束
                        max_frames = self._get_max_frames()
                        if self._frame_buffer_index < max_frames:
                            # 还有其他通道未结束，循环播放当前通道
                            looped_frame = channel_state.get_looped_frame_data(self._frame_buffer_index)
                            results[channel] = looped_frame if looped_frame else WebSocketFrame(((10, 10, 10, 10), (0, 0, 0, 0)), None)
                        else:
                            # 所有通道都结束：发送静默帧
                            results[channel] = WebSocketFrame(((10, 10, 10, 10), (0, 0, 0, 0)), None)
        
        # 推进缓冲区索引（可以无限递增）
        self._frame_buffer_index += 1
        return results
    
    def advance_logical_frame(self) -> None:
        """推进逻辑播放位置
        
        logical_index严格限定在有效数据范围内，用于UI显示和进度查询
        """
        if not self.has_any_frame_data():
            return
            
        max_length = self._get_max_frames()
        if max_length == 0:
            return
            
        if self._playback_mode == PlaybackMode.LOOP:
            # 循环模式：到达末尾时重置为0
            self._frame_logical_index = (self._frame_logical_index + 1) % max_length
        else:
            # 单次模式：严格限制在[0, max_length-1]范围内
            if self._frame_logical_index < max_length - 1:
                self._frame_logical_index += 1
            # 到达末尾时不再递增，保持在最后一个有效位置
    
    def advance_buffer_for_send_batch(self, count: int) -> Dict[Channel, List[WebSocketFrame]]:
        """批量推进统一缓冲区，返回所有通道的多帧数据"""
        results: Dict[Channel, List[WebSocketFrame]] = {
            Channel.A: [],
            Channel.B: []
        }
        
        for _ in range(count):
            frame_data = self.advance_buffer_for_send()
            for channel, frame in frame_data.items():
                results[channel].append(frame)
        
        return results
    
    # ============ 状态查询接口 ============
    
    def get_current_pulse_data(self, channel: Channel) -> Optional[PulseOperation]:
        """获取指定通道当前逻辑播放位置的脉冲数据
        
        支持不同长度通道的独立循环查询
        """
        channel_state = self._channel_states[channel]
        
        # 检查是否有数据且在全局播放范围内
        if not channel_state.frame_data or self._frame_logical_index >= self._get_max_frames():
            return None
        
        # 使用循环获取方法，自动处理范围内/外的情况
        looped_frame = channel_state.get_looped_frame_data(self._frame_logical_index)
        return looped_frame.pulse_operation if looped_frame else None
    
    def get_frame_position(self) -> int:
        """获取逻辑帧播放位置"""
        return self._frame_logical_index
    
    def set_frame_position(self, position: int) -> None:
        """设置帧播放位置，确保在有效范围内"""
        if position < 0:
            position = 0
            
        max_length = self._get_max_frames()
        if max_length > 0:
            # 限制在有效数据范围内
            position = min(position, max_length - 1)
        else:
            position = 0
            
        self._frame_logical_index = position
        # 缓冲区位置可以适当领先logical位置，但不超过太多
        self._frame_buffer_index = position

    def get_buffer_position(self) -> int:
        """获取缓冲区位置（帧进度）"""
        return self._frame_buffer_index

    def has_frame_data(self, channel: Channel) -> bool:
        """检查指定通道是否有波形数据"""
        return len(self._channel_states[channel].frame_data) > 0
    
    def has_any_frame_data(self) -> bool:
        """检查是否有任何通道有波形数据"""
        return any(self.has_frame_data(channel) for channel in Channel)
    
    def is_frame_sequence_finished(self) -> bool:
        """检查帧序列是否已完成"""
        if not self.has_any_frame_data():
            return True
        
        # 循环模式永远不会完成
        if self._playback_mode == PlaybackMode.LOOP:
            return False
        
        # 单次模式：检查是否到达最后一帧
        max_length = self._get_max_frames()
        if max_length == 0:
            return True
            
        # 当logical_index到达最后一个有效位置时，视为完成
        return self._frame_logical_index >= max_length - 1
    
    # ============ 高级管理接口 ============
    
    def reset_frame_progress(self) -> None:
        """重置帧进度"""
        self._frame_buffer_index = 0
        self._frame_logical_index = 0
    
    # ============ 内部访问接口 ============
    
    def get_channel_state(self, channel: Channel) -> WebSocketChannelState:
        """获取原始通道状态对象（用于兼容现有代码）"""
        return self._channel_states[channel]
    
    def get_all_channel_states(self) -> Dict[Channel, WebSocketChannelState]:
        """获取所有原始通道状态对象"""
        return self._channel_states.copy()
    
    # ============ 内部辅助方法 ============
    
    def _get_max_frames(self) -> int:
        """获取所有通道中最长的数据长度"""
        max_frames = 0
        for channel in Channel:
            frame_data = self._channel_states[channel].frame_data
            if frame_data:
                max_frames = max(max_frames, len(frame_data))
        return max_frames