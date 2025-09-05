"""
录制数据模型

定义录制原始波形功能所需的所有数据结构
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict

from models import Channel, PulseOperation


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
    duration_ms: int = 0              # 录制时长（毫秒）
    sample_count: int = 0             # 采样数量


@dataclass
class RecordingSession:
    """录制会话"""
    metadata: RecordingMetadata
    snapshots: List[RecordingSnapshot]  # 按时间顺序的所有快照数据