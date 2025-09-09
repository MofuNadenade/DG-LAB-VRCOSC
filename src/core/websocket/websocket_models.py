"""
WebSocket数据模型

定义WebSocket连接状态和数据结构
"""

from dataclasses import dataclass
from enum import Enum
from typing import Union, Optional, List, Protocol, Awaitable

from pydglab_ws import FeedbackButton, PulseOperation, RetCode, StrengthData

from core.recording.recording_models import ChannelSnapshot


class PlaybackMode(Enum):
    """播放模式"""
    ONCE = "once"       # 播放一次后停止
    LOOP = "loop"       # 循环播放


class FramesEventType(Enum):
    """帧事件类型"""
    COMPLETED = "completed"  # 单次播放完成
    LOOPED = "looped"        # 循环播放重新开始


# ============ 协议层回调Protocol定义 ============

class QRCodeCallback(Protocol):
    """二维码回调协议"""
    def __call__(self, qr_code: str) -> Awaitable[None]: ...

class ConnectionStateCallback(Protocol):
    """连接状态回调协议"""
    def __call__(self) -> Awaitable[None]: ...

class StrengthDataCallback(Protocol):
    """强度数据回调协议"""
    def __call__(self, data: StrengthData) -> Awaitable[None]: ...

class FeedbackButtonCallback(Protocol):
    """反馈按钮回调协议"""
    def __call__(self, button: FeedbackButton) -> Awaitable[None]: ...

class RetCodeCallback(Protocol):
    """返回码回调协议"""  
    def __call__(self, ret_code: RetCode) -> Awaitable[None]: ...

class DataSyncCallback(Protocol):
    """数据同步回调协议"""
    def __call__(self) -> None: ...

class ProgressChangedCallback(Protocol):
    """进度变化回调协议"""
    def __call__(self) -> None: ...

class FramesEventCallback(Protocol):
    """帧事件回调协议"""
    def __call__(self, event_type: FramesEventType) -> None: ...

class PlaybackModeChangedCallback(Protocol):
    """播放模式变更回调协议"""
    def __call__(self, old_mode: PlaybackMode, new_mode: PlaybackMode) -> None: ...


# WebSocket服务可处理的数据类型
WebSocketData = Union[StrengthData, FeedbackButton, RetCode]


@dataclass
class WebSocketFrame:
    """WebSocket内部帧数据，包含脉冲操作和强度信息"""
    pulse_operation: PulseOperation           # 脉冲操作数据
    target_strength: Optional[int] = None     # 目标强度（None表示不改变强度）
    
    def has_strength_change(self) -> bool:
        """检查是否包含强度变化"""
        return self.target_strength is not None


class WebSocketChannelState:
    """WebSocket通道状态 - 仅存储帧数据"""

    def __init__(self) -> None:
        super().__init__()
        self._frame_data: List[WebSocketFrame] = []
    
    def set_pulse_data(self, pulses: List[PulseOperation]) -> None:
        """从脉冲操作列表设置帧数据"""
        self._frame_data = [WebSocketFrame(pulse, None) for pulse in pulses]

    def set_snapshot_data(self, snapshots: List[ChannelSnapshot]) -> None:
        """从快照列表设置帧数据"""
        frames: List[WebSocketFrame] = []
        for snapshot in snapshots:
            if snapshot.pulse_operation:
                frame = WebSocketFrame(snapshot.pulse_operation, snapshot.current_strength)
                frames.append(frame)
        self._frame_data = frames

    def clear_frame_data(self) -> None:
        """清除波形数据"""
        self._frame_data.clear()

    @property
    def frame_data(self) -> List[WebSocketFrame]:
        """获取帧数据（只读）"""
        return self._frame_data

    def get_looped_frame_data(self, index: int) -> Optional[WebSocketFrame]:
        """获取循环的帧数据
        
        当通道数据长度不同时，使用模运算循环获取已结束通道的数据
        
        Args:
            index: 要获取的帧索引
            
        Returns:
            对应索引的帧数据，如果无数据则返回None
        """
        if not self._frame_data:
            return None
        
        # 使用模运算实现循环
        looped_index = index % len(self._frame_data)
        return self._frame_data[looped_index]