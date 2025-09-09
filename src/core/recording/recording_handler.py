"""
录制处理器接口

定义脉冲录制处理器的抽象接口
"""

from abc import ABC, abstractmethod
from typing import Optional

from .recording_models import RecordingState, RecordingSession


class IPulseRecordHandler(ABC):
    """脉冲录制处理器抽象接口"""
    
    @abstractmethod
    async def start_recording(self) -> bool:
        """开始录制所有通道
        
        Returns:
            bool: 是否成功开始录制
        """
        ...
    
    @abstractmethod
    async def pause_recording(self) -> bool:
        """暂停录制
        
        Returns:
            bool: 是否成功暂停录制
        """
        ...
    
    @abstractmethod
    async def resume_recording(self) -> bool:
        """继续录制
        
        Returns:
            bool: 是否成功继续录制
        """
        ...
    
    @abstractmethod
    async def stop_recording(self) -> RecordingSession:
        """停止录制并返回会话数据
        
        Returns:
            RecordingSession: 录制会话数据
        """
        ...
    
    @abstractmethod
    def get_recording_state(self) -> RecordingState:
        """获取当前录制状态
        
        Returns:
            RecordingState: 当前录制状态
        """
        ...
    
    @abstractmethod
    def get_current_session(self) -> Optional[RecordingSession]:
        """获取当前录制会话
        
        Returns:
            Optional[RecordingSession]: 当前录制会话，如果没有则返回None
        """
        ...