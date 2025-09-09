"""
回放处理器接口

定义脉冲回放处理器的抽象接口
"""

from abc import ABC, abstractmethod
from typing import Optional

from .recording_models import RecordingSession, PlaybackState, ProgressChangedCallback, StateChangedCallback, ErrorCallback


class IPulsePlaybackHandler(ABC):
    """脉冲回放处理器抽象接口"""

    @abstractmethod
    def set_progress_changed_callback(self, callback: Optional[ProgressChangedCallback]) -> None:
        """设置进度回调函数

        Args:
            callback: 进度回调函数，None表示移除回调
        """
        ...
    
    @abstractmethod
    def set_state_changed_callback(self, callback: Optional[StateChangedCallback]) -> None:
        """设置状态变化回调函数

        Args:
            callback: 状态变化回调函数，None表示移除回调
        """
        ...
    
    @abstractmethod
    def set_error_callback(self, callback: Optional[ErrorCallback]) -> None:
        """设置错误回调函数

        Args:
            callback: 错误回调函数，None表示移除回调
        """
        ...
    
    @abstractmethod
    async def load_session(self, session: RecordingSession) -> bool:
        """加载录制会话用于回放
        
        Args:
            session: 要回放的录制会话
            
        Returns:
            bool: 是否成功加载会话
        """
        ...
    
    @abstractmethod
    async def start_playback(self) -> bool:
        """开始回放
        
        Returns:
            bool: 是否成功开始回放
        """
        ...
    
    @abstractmethod
    async def pause_playback(self) -> bool:
        """暂停回放
        
        Returns:
            bool: 是否成功暂停回放
        """
        ...
    
    @abstractmethod
    async def resume_playback(self) -> bool:
        """继续回放
        
        Returns:
            bool: 是否成功继续回放
        """
        ...
    
    @abstractmethod
    async def stop_playback(self) -> bool:
        """停止回放
        
        Returns:
            bool: 是否成功停止回放
        """
        ...
    
    @abstractmethod
    async def seek_to_position(self, position: int) -> bool:
        """跳转到指定位置
        
        Args:
            position: 目标位置 (0-based快照索引)
            
        Returns:
            bool: 是否成功跳转
        """
        ...
    
    @abstractmethod
    def get_playback_state(self) -> PlaybackState:
        """获取当前回放状态
        
        Returns:
            PlaybackState: 当前回放状态
        """
        ...
    
    @abstractmethod
    def get_current_position(self) -> int:
        """获取当前播放位置
        
        Returns:
            int: 当前位置 (0-based快照索引)
        """
        ...
    
    @abstractmethod
    def get_total_snapshots(self) -> int:
        """获取总快照数量
        
        Returns:
            int: 总快照数量
        """
        ...
    
    @abstractmethod
    def get_loaded_session(self) -> Optional[RecordingSession]:
        """获取已加载的录制会话
        
        Returns:
            Optional[RecordingSession]: 已加载的会话，如果没有则返回None
        """
        ...