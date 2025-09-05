"""
基础回放处理器

提供回放功能的抽象基类，遵循DRY原则
"""

import asyncio
import logging
from abc import abstractmethod
from typing import Optional

from models import Channel
from .playback_handler import IPulsePlaybackHandler, PlaybackState, PlaybackProgressCallback
from .recording_models import RecordingSession, RecordingSnapshot, ChannelSnapshot

logger = logging.getLogger(__name__)


class BasePlaybackHandler(IPulsePlaybackHandler):
    """基础回放处理器抽象类
    
    通过IDGLabDeviceService接口回放录制的会话数据，
    按100ms间隔精确回放每个数据快照
    """
    
    def __init__(self) -> None:
        super().__init__()
        self._state: PlaybackState = PlaybackState.IDLE
        self._session: Optional[RecordingSession] = None
        self._current_position: int = 0
        self._playback_task: Optional[asyncio.Task[None]] = None
        self._progress_callback: Optional[PlaybackProgressCallback] = None
        
    # ============ 公共接口实现 ============
    
    async def load_session(self, session: RecordingSession) -> bool:
        """加载录制会话用于回放"""
        if self._state != PlaybackState.IDLE:
            logger.warning("回放器不在空闲状态，无法加载新会话")
            return False
        
        try:
            if not session.snapshots:
                logger.warning("录制会话没有快照数据")
                return False
            
            self._session = session
            self._current_position = 0
            
            logger.info(f"已加载录制会话: {session.metadata.session_id}, 共{len(session.snapshots)}个快照")
            return True
            
        except Exception as e:
            logger.error(f"加载录制会话失败: {e}")
            return False
    
    async def start_playback(self) -> bool:
        """开始回放"""
        if self._state != PlaybackState.IDLE:
            logger.warning("回放器不在空闲状态，无法开始回放")
            return False
            
        if not self._session:
            logger.warning("没有加载录制会话，无法开始回放")
            return False
        
        try:
            self._state = PlaybackState.PLAYING
            self._current_position = 0
            
            # 启动回放任务
            self._playback_task = asyncio.create_task(self._playback_loop())
            
            logger.info(f"开始回放录制会话: {self._session.metadata.session_id}")
            return True
            
        except Exception as e:
            logger.error(f"开始回放失败: {e}")
            self._state = PlaybackState.IDLE
            return False
    
    async def pause_playback(self) -> bool:
        """暂停回放"""
        if self._state != PlaybackState.PLAYING:
            logger.warning("当前不在回放状态，无法暂停")
            return False
            
        self._state = PlaybackState.PAUSED
        logger.info("回放已暂停")
        return True
    
    async def resume_playback(self) -> bool:
        """继续回放"""
        if self._state != PlaybackState.PAUSED:
            logger.warning("当前不在暂停状态，无法继续")
            return False
            
        self._state = PlaybackState.PLAYING
        logger.info("回放已继续")
        return True
    
    async def stop_playback(self) -> bool:
        """停止回放"""
        if self._state == PlaybackState.IDLE:
            logger.warning("回放器未开始，无法停止")
            return False
        
        try:
            # 设置停止状态
            self._state = PlaybackState.IDLE
            
            # 停止回放任务
            if self._playback_task:
                self._playback_task.cancel()
                try:
                    await self._playback_task
                except asyncio.CancelledError:
                    pass
                self._playback_task = None
            
            # 清理设备状态
            await self._cleanup_device_state()
            
            self._current_position = 0
            
            logger.info("回放已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止回放失败: {e}")
            return False
    
    async def seek_to_position(self, position: int) -> bool:
        """跳转到指定位置"""
        if not self._session:
            logger.warning("没有加载录制会话，无法跳转")
            return False
        
        if not (0 <= position < len(self._session.snapshots)):
            logger.warning(f"跳转位置超出范围: {position}")
            return False
        
        self._current_position = position
        
        # 如果正在播放，应用当前位置的数据
        if self._state == PlaybackState.PLAYING:
            snapshot = self._session.snapshots[position]
            await self._apply_snapshot(snapshot)
        
        logger.debug(f"跳转到位置: {position}")
        return True
    
    def get_playback_state(self) -> PlaybackState:
        """获取当前回放状态"""
        return self._state
    
    def get_current_position(self) -> int:
        """获取当前播放位置"""
        return self._current_position
    
    def get_total_snapshots(self) -> int:
        """获取总快照数量"""
        return len(self._session.snapshots) if self._session else 0
    
    def get_loaded_session(self) -> Optional[RecordingSession]:
        """获取已加载的录制会话"""
        return self._session
    
    def set_progress_callback(self, callback: Optional[PlaybackProgressCallback]) -> None:
        """设置进度回调函数"""
        self._progress_callback = callback
    
    # ============ 内部回放逻辑 ============
    
    async def _playback_loop(self) -> None:
        """回放主循环 - 100ms精确时序"""
        try:
            while (self._state in (PlaybackState.PLAYING, PlaybackState.PAUSED) and 
                   self._session and self._current_position < len(self._session.snapshots)):
                
                if self._state == PlaybackState.PLAYING:
                    # 获取并应用当前快照
                    snapshot = self._session.snapshots[self._current_position]
                    await self._apply_snapshot(snapshot)
                    
                    # 更新进度
                    if self._progress_callback:
                        self._progress_callback(self._current_position, len(self._session.snapshots))
                    
                    # 移动到下一位置
                    self._current_position += 1
                    
                    # 检查是否播放完成
                    if self._current_position >= len(self._session.snapshots):
                        self._state = PlaybackState.IDLE
                        logger.info("回放完成")
                        break
                
                # 等待100ms（与录制间隔同步）
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            logger.debug("回放循环已取消")
            raise
        except Exception as e:
            logger.error(f"回放循环出错: {e}")
            self._state = PlaybackState.IDLE
            raise
    
    async def _apply_snapshot(self, snapshot: RecordingSnapshot) -> None:
        """应用数据快照到设备"""
        try:
            # 遍历所有通道数据
            for channel, channel_data in snapshot.channels.items():
                await self._apply_channel_data(channel, channel_data)
                
        except Exception as e:
            logger.error(f"应用快照数据失败: {e}")
    
    @abstractmethod
    async def _apply_channel_data(self, channel: Channel, data: ChannelSnapshot) -> None:
        """应用通道数据到设备（子类实现）
        
        Args:
            channel: 目标通道
            data: 通道快照数据
        """
        ...
    
    @abstractmethod
    async def _cleanup_device_state(self) -> None:
        """清理设备状态"""
        ...