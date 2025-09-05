"""
WebSocket数据模型

定义WebSocket连接状态和数据结构
"""

from typing import Union, Optional, List

from pydglab_ws import FeedbackButton, PulseOperation, RetCode, StrengthData


# WebSocket服务可处理的数据类型
WebSocketData = Union[StrengthData, FeedbackButton, RetCode]


class WebSocketChannelState:
    """通道状态"""

    def __init__(self) -> None:
        super().__init__()
        self._pulse_data: List[PulseOperation] = []
        self._buffer_index: int = 0  # 缓冲区位置（已发送给设备的数据位置）
        self._logical_index: int = 0  # 逻辑播放位置（当前实际播放的位置）

    def set_pulse_data(self, pulses: List[PulseOperation]) -> None:
        """设置波形数据"""
        self._pulse_data = pulses.copy()
        self._buffer_index = 0
        self._logical_index = 0

    def clear_pulse_data(self) -> None:
        """清除波形数据"""
        self._pulse_data.clear()
        self._buffer_index = 0
        self._logical_index = 0

    def get_pulse_data(self) -> List[PulseOperation]:
        """获取波形数据"""
        return self._pulse_data.copy()

    def get_current_playing_pulse(self) -> Optional[PulseOperation]:
        """获取当前逻辑播放的脉冲数据（不递增索引）"""
        if not self._pulse_data:
            return None
        if 0 <= self._logical_index < len(self._pulse_data):
            return self._pulse_data[self._logical_index]
        return None

    def get_buffer_head_pulse(self) -> Optional[PulseOperation]:
        """获取缓冲区头部的脉冲数据（已发送但可能未播放）"""
        if not self._pulse_data:
            return None
        if 0 <= self._buffer_index < len(self._pulse_data):
            return self._pulse_data[self._buffer_index]
        return None

    def advance_buffer_for_send(self) -> PulseOperation:
        """推进缓冲区并返回要发送的脉冲数据"""
        if not self._pulse_data:
            return ((10, 10, 10, 10), (0, 0, 0, 0))
        
        current_pulse = self._pulse_data[self._buffer_index]
        self._buffer_index = (self._buffer_index + 1) % len(self._pulse_data)
        return current_pulse

    def advance_logical_playback(self) -> None:
        """推进逻辑播放位置（模拟设备播放进度）"""
        if self._pulse_data:
            self._logical_index = (self._logical_index + 1) % len(self._pulse_data)

    def get_buffer_index(self) -> int:
        """获取缓冲区索引"""
        return self._buffer_index

    def get_logical_index(self) -> int:
        """获取逻辑播放索引"""
        return self._logical_index