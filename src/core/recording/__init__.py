"""
录制功能模块

提供DG-LAB设备的原始波形录制功能
"""

from .recording_models import (
    PlaybackState,
    RecordingState,
    ChannelSnapshot,
    RecordingSnapshot,
    RecordingMetadata,
    RecordingSession,
    ProgressChangedCallback,
    StateChangedCallback,
    ErrorCallback
)
from .recording_handler import IPulseRecordHandler
from .base_record_handler import BaseRecordHandler
from .playback_handler import IPulsePlaybackHandler
from .base_playback_handler import BasePlaybackHandler
from .dgr_file_manager import DGRFileManager

__all__ = [
    'PlaybackState',
    'RecordingState',
    'ChannelSnapshot', 
    'RecordingSnapshot',
    'RecordingMetadata',
    'RecordingSession',
    'ProgressChangedCallback',
    'StateChangedCallback',
    'ErrorCallback',
    'IPulseRecordHandler',
    'BaseRecordHandler',
    'IPulsePlaybackHandler',
    'BasePlaybackHandler',
    'DGRFileManager'
]