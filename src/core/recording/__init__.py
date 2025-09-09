"""
录制功能模块

提供DG-LAB设备的原始波形录制功能
"""

from .recording_models import (
    RecordingState,
    ChannelSnapshot,
    RecordingSnapshot,
    RecordingMetadata,
    RecordingSession
)
from .recording_handler import IPulseRecordHandler
from .base_record_handler import BaseRecordHandler
from .playback_handler import IPulsePlaybackHandler, PlaybackState, PlaybackProgressCallback
from .base_playback_handler import BasePlaybackHandler
from .dgr_file_manager import DGRFileManager

__all__ = [
    'RecordingState',
    'ChannelSnapshot', 
    'RecordingSnapshot',
    'RecordingMetadata',
    'RecordingSession',
    'IPulseRecordHandler',
    'BaseRecordHandler',
    'IPulsePlaybackHandler',
    'PlaybackState',
    'PlaybackProgressCallback',
    'BasePlaybackHandler',
    'DGRFileManager'
]