"""
录制数据模型

定义录制原始波形功能所需的所有数据结构
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Protocol

from models import Channel, PulseOperation, PlaybackMode, FramesEventType


class PlaybackState(Enum):
    """回放状态"""
    IDLE = "idle"           # 空闲状态
    PLAYING = "playing"     # 回放中
    PAUSED = "paused"       # 已暂停


class RecordingState(Enum):
    """录制状态"""
    IDLE = "idle"           # 空闲状态
    RECORDING = "recording" # 录制中
    PAUSED = "paused"       # 已暂停


@dataclass
class ChannelSnapshot:
    """单个通道在某个时间片的数据"""
    pulse_operation: PulseOperation    # 波形操作数据
    current_strength: int             # 当前实时强度 [0-200]


@dataclass
class RecordingSnapshot:
    """单个100ms时间片的完整数据快照"""
    channels: Dict[Channel, ChannelSnapshot]  # 通道数据字典


@dataclass
class RecordingMetadata:
    """录制元数据"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None


@dataclass
class RecordingSession:
    """录制会话"""
    metadata: RecordingMetadata
    snapshots: List[RecordingSnapshot]  # 按时间顺序的所有快照数据
    
    def get_duration_ms(self) -> int:
        """计算录制持续时间（毫秒）"""
        # 只基于快照数量计算（每快照100ms）
        return len(self.snapshots) * 100
    
    def get_total_snapshots(self) -> int:
        """获取快照总数"""
        return len(self.snapshots)


class ProgressChangedCallback(Protocol):
    """进度回调协议"""
    def __call__(self, current: int, total: int, percentage: float) -> None: ...


class StateChangedCallback(Protocol):
    """状态变化回调协议"""
    def __call__(self, old_state: PlaybackState, new_state: PlaybackState) -> None: ...


class ErrorCallback(Protocol):
    """错误回调协议"""
    def __call__(self, error_type: str, message: str) -> None: ...


class FramesEventNotificationCallback(Protocol):
    """帧事件通知回调协议（用于内部处理器事件转发）"""
    def __call__(self, event_type: FramesEventType) -> None: ...


class PlaybackModeNotificationCallback(Protocol):
    """播放模式变更通知回调协议（用于内部处理器事件转发）"""
    def __call__(self, old_mode: PlaybackMode, new_mode: PlaybackMode) -> None: ...