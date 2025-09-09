"""
基础回放处理器

提供回放功能的抽象基类，使用回调系统而非状态存储
"""

import logging
from abc import abstractmethod
from typing import Optional, List

from .playback_handler import IPulsePlaybackHandler
from models import FramesEventType, PlaybackMode
from .recording_models import (
    RecordingSession,
    RecordingSnapshot,
    PlaybackState,
    ProgressChangedCallback,
    StateChangedCallback,
    ErrorCallback
)

logger = logging.getLogger(__name__)



class BasePlaybackHandler(IPulsePlaybackHandler):
    """基础回放处理器抽象类
    
    使用回调系统获取状态，不存储位置信息
    """
    
    def __init__(self) -> None:
        super().__init__()
        self._session: Optional[RecordingSession] = None
        self._current_state: PlaybackState = PlaybackState.IDLE
        self._current_playback_mode: Optional[PlaybackMode] = None
        # 回调函数
        self._progress_changed_callback: Optional[ProgressChangedCallback] = None
        self._state_changed_callback: Optional[StateChangedCallback] = None
        self._error_callback: Optional[ErrorCallback] = None
        
    # ============ 回调管理 ============
    
    def set_progress_changed_callback(self, callback: Optional[ProgressChangedCallback]) -> None:
        """设置进度回调函数"""
        self._progress_changed_callback = callback
        
    def set_state_changed_callback(self, callback: Optional[StateChangedCallback]) -> None:
        """设置状态变化回调函数"""
        self._state_changed_callback = callback
        
    def set_error_callback(self, callback: Optional[ErrorCallback]) -> None:
        """设置错误回调函数"""
        self._error_callback = callback

    # ============ 公共接口实现 ============
    
    async def load_session(self, session: RecordingSession) -> bool:
        """加载录制会话用于回放"""
        if self._current_state != PlaybackState.IDLE:
            self._notify_error("load_error", "回放器不在空闲状态，无法加载新会话")
            return False
        
        if not session.snapshots:
            self._notify_error("load_error", "录制会话没有快照数据")
            return False
        
        self._session = session
        return True
    
    async def start_playback(self) -> bool:
        """开始回放"""
        if self._current_state != PlaybackState.IDLE:
            self._notify_error("playback_error", "回放器不在空闲状态，无法开始回放")
            return False
            
        if not self._session:
            self._notify_error("playback_error", "没有加载录制会话，无法开始回放")
            return False
        
        try:
            await self._start_playback(self._session.snapshots)
            self._transition_state(PlaybackState.PLAYING)
            return True
            
        except Exception as e:
            self._notify_error("playback_error", f"开始回放失败: {e}")
            return False
    
    async def pause_playback(self) -> bool:
        """暂停回放"""
        if self._current_state != PlaybackState.PLAYING:
            self._notify_error("playback_error", "当前不在回放状态，无法暂停")
            return False
        
        try:
            await self._pause_playback()
            self._transition_state(PlaybackState.PAUSED)
            return True
        except Exception as e:
            self._notify_error("playback_error", f"暂停回放失败: {e}")
            return False
    
    async def resume_playback(self) -> bool:
        """继续回放"""
        if self._current_state != PlaybackState.PAUSED:
            self._notify_error("playback_error", "当前不在暂停状态，无法继续")
            return False
        
        try:
            await self._resume_playback()
            self._transition_state(PlaybackState.PLAYING)
            return True
        except Exception as e:
            self._notify_error("playback_error", f"继续回放失败: {e}")
            return False
    
    async def stop_playback(self) -> bool:
        """停止回放"""
        if self._current_state == PlaybackState.IDLE:
            self._notify_error("playback_error", "回放器未开始，无法停止")
            return False
        
        try:
            await self._stop_playback()
            self._transition_state(PlaybackState.IDLE)
            return True
        except Exception as e:
            self._notify_error("playback_error", f"停止回放失败: {e}")
            return False
    
    def get_playback_state(self) -> PlaybackState:
        """获取当前回放状态"""
        return self._current_state
    
    def get_loaded_session(self) -> Optional[RecordingSession]:
        """获取已加载的录制会话"""
        return self._session
    
    async def seek_to_position(self, position: int) -> bool:
        """跳转到指定位置"""
        if self._current_state == PlaybackState.IDLE:
            self._notify_error("seek_error", "回放器未加载会话，无法跳转")
            return False
        
        if not self._session:
            self._notify_error("seek_error", "没有加载录制会话，无法跳转")
            return False
        
        if position < 0 or position >= len(self._session.snapshots):
            self._notify_error("seek_error", f"无效的位置: {position}")
            return False
        
        try:
            await self._seek_to_position(position)
            return True
        except Exception as e:
            self._notify_error("seek_error", f"跳转失败: {e}")
            return False
    
    def get_total_snapshots(self) -> int:
        """获取总快照数量"""
        return len(self._session.snapshots) if self._session else 0
    
    # ============ 内部事件处理 ============
    
    def _transition_state(self, new_state: PlaybackState) -> None:
        """状态转换"""
        old_state = self._current_state
        self._current_state = new_state
        self._notify_state_changed(old_state, new_state)
    
    def _notify_progress_changed(self, current: int, total: int, percentage: float) -> None:
        """通知进度变化"""
        if self._progress_changed_callback:
            try:
                self._progress_changed_callback(current, total, percentage)
            except Exception as e:
                logger.error(f"Progress callback failed: {e}")
    
    def _notify_state_changed(self, old_state: PlaybackState, new_state: PlaybackState) -> None:
        """通知状态变化"""
        if self._state_changed_callback:
            try:
                self._state_changed_callback(old_state, new_state)
            except Exception as e:
                logger.error(f"State callback failed: {e}")
    
    def _notify_error(self, error_type: str, message: str) -> None:
        """通知错误"""
        if self._error_callback:
            try:
                self._error_callback(error_type, message)
            except Exception as e:
                logger.error(f"Error callback failed: {e}")
    
    # ============ 抽象方法 ============
    
    @abstractmethod
    async def _start_playback(self, snapshots: List[RecordingSnapshot]) -> None:
        """启动回放"""
        ...
    
    @abstractmethod
    async def _stop_playback(self) -> None:
        """停止回放"""
        ...
    
    @abstractmethod
    async def _pause_playback(self) -> None:
        """暂停回放"""
        ...
    
    @abstractmethod
    async def _resume_playback(self) -> None:
        """继续回放"""
        ...
    
    @abstractmethod
    async def _seek_to_position(self, position: int) -> None:
        """跳转到指定位置"""
        ...
    
    @abstractmethod
    def get_current_position(self) -> int:
        """获取当前播放位置
        
        Returns:
            int: 当前位置 (0-based快照索引)
        """
        ...

    # ============ 服务层事件转发处理 ============
    
    def on_progress_changed(self) -> None:
        """处理播放进度变化通知（用于服务层事件转发）
        
        默认实现会触发进度回调。子类可以重写此方法来添加额外的进度处理逻辑。
        """
        # 只在播放状态下发送进度更新，避免IDLE状态下的重复更新
        if self._session and self._current_state == PlaybackState.PLAYING:
            current = self.get_current_position()
            total = self.get_total_snapshots()
            percentage = (current / total * 100.0) if total > 0 else 0.0
            
            self._notify_progress_changed(current, total, percentage)
    
    def on_frames_event(self, event_type: FramesEventType) -> None:
        """处理帧事件通知（用于服务层事件转发）
        
        Args:
            event_type: 帧事件类型（完成/循环）
            
        实现播放完成状态管理和事件分发：
        - COMPLETED: 单次播放完成，转换到IDLE状态
        - LOOPED: 循环播放重新开始，保持PLAYING状态
        """
        logger.debug(f"Frames event received: {event_type}")
        
        if event_type == FramesEventType.COMPLETED:
            # 单次播放完成 - 转换到IDLE状态
            if self._current_state == PlaybackState.PLAYING:
                logger.info("单次播放完成，转换到空闲状态")
                
                # 触发最终进度更新（100%）
                if self._session:
                    total = self.get_total_snapshots()
                    self._notify_progress_changed(total, total, 100.0)
                
                # 状态转换必须在进度更新之后，避免IDLE状态下继续接收更新
                self._transition_state(PlaybackState.IDLE)
                    
        elif event_type == FramesEventType.LOOPED:
            # 循环播放重新开始 - 保持PLAYING状态，重置进度
            if self._current_state == PlaybackState.PLAYING:
                logger.info("循环播放重新开始")
                
                # 触发进度重置更新（0%）
                if self._session:
                    total = self.get_total_snapshots()
                    self._notify_progress_changed(0, total, 0.0)
    
    def on_playback_mode_changed(self, old_mode: PlaybackMode, new_mode: PlaybackMode) -> None:
        """处理播放模式变更通知（用于服务层事件转发）
        
        Args:
            old_mode: 旧播放模式
            new_mode: 新播放模式
            
        实现播放模式同步和状态管理：
        - 记录模式变更日志
        - 存储当前播放模式用于状态查询
        - 根据模式变更调整播放行为预期
        """
        logger.info(f"播放模式变更: {old_mode.value} -> {new_mode.value}")
        
        # 存储当前播放模式
        self._current_playback_mode = new_mode
        
        # 模式变更时的特殊处理
        if old_mode != new_mode:
            if new_mode == PlaybackMode.ONCE:
                logger.debug("切换到单次播放模式 - 播放完成后将停止")
            elif new_mode == PlaybackMode.LOOP:
                logger.debug("切换到循环播放模式 - 播放完成后将重新开始")
                
            # 如果正在播放中，可以提供模式变更的即时反馈
            if self._current_state == PlaybackState.PLAYING:
                logger.debug(f"播放模式在播放中变更为: {new_mode.value}")
    
    def get_current_playback_mode(self) -> Optional[PlaybackMode]:
        """获取当前播放模式
        
        Returns:
            Optional[PlaybackMode]: 当前播放模式，如果未设置则返回None
        """
        return self._current_playback_mode
    
