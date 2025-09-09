"""
录制处理器基类

实现通用的录制逻辑，遵循DRY原则
"""

import logging
import uuid
from abc import abstractmethod
from datetime import datetime
from typing import Optional, Dict

from models import Channel, PulseOperation
from .recording_models import (
    RecordingState,
    ChannelSnapshot,
    RecordingSnapshot, 
    RecordingMetadata,
    RecordingSession
)
from .recording_handler import IPulseRecordHandler

logger = logging.getLogger(__name__)


class BaseRecordHandler(IPulseRecordHandler):
    """录制处理器基类
    
    实现通用录制逻辑，子类只需实现数据获取方法
    """
    
    def __init__(self) -> None:
        """初始化基类"""
        super().__init__()
        self._state: RecordingState = RecordingState.IDLE
        self._session: Optional[RecordingSession] = None
        
    # ============ 公共接口实现 ============
    
    async def start_recording(self) -> bool:
        """开始录制所有通道"""
        if self._state != RecordingState.IDLE:
            logger.warning("录制已在进行中，无法开始新的录制")
            return False
            
        # 创建新的录制会话
        session_id = str(uuid.uuid4())
        start_time = datetime.now()
        metadata = RecordingMetadata(
            session_id=session_id,
            start_time=start_time
        )
        self._session = RecordingSession(
            metadata=metadata,
            snapshots=[]
        )
        
        # 更新状态
        self._state = RecordingState.RECORDING
        
        logger.info(f"开始录制，会话ID: {session_id}")
        return True
    
    async def pause_recording(self) -> bool:
        """暂停录制"""
        if self._state != RecordingState.RECORDING:
            logger.warning("当前不在录制状态，无法暂停")
            return False
            
        self._state = RecordingState.PAUSED
        logger.info("录制已暂停")
        return True
    
    async def resume_recording(self) -> bool:
        """继续录制"""
        if self._state != RecordingState.PAUSED:
            logger.warning("当前不在暂停状态，无法继续")
            return False
            
        self._state = RecordingState.RECORDING
        logger.info("录制已继续")
        return True
    
    async def stop_recording(self) -> RecordingSession:
        """停止录制并返回会话数据"""
        if self._state == RecordingState.IDLE:
            raise RuntimeError("当前没有进行中的录制")
        
        # 完成会话数据
        if self._session:
            end_time = datetime.now()
            self._session.metadata.end_time = end_time

        # 保存会话并重置状态
        completed_session = self._session
        self._state = RecordingState.IDLE
        self._session = None
        
        total_snapshots = len(completed_session.snapshots) if completed_session else 0
        logger.info(f"录制已停止，快照数量: {total_snapshots}")
        
        if completed_session is None:
            raise RuntimeError("录制会话数据丢失")
            
        return completed_session
    
    def get_recording_state(self) -> RecordingState:
        """获取当前录制状态"""
        return self._state
    
    def get_current_session(self) -> Optional[RecordingSession]:
        """获取当前录制会话"""
        return self._session
    
    # ============ 内部录制逻辑 ============
    
    def on_data_sync(self) -> None:
        """数据同步通知（由服务调用）
        
        服务在内部数据更新时调用此方法，录制器根据当前状态决定是否记录数据。
        这样确保录制与服务的数据同步机制集成，而不是独立的定时循环。
        """
        if self._state == RecordingState.RECORDING:
            # 采集当前数据
            snapshot = self._capture_snapshot()
            if snapshot and self._session:
                self._session.snapshots.append(snapshot)
    
    def _capture_snapshot(self) -> Optional[RecordingSnapshot]:
        """捕获当前时刻的数据快照"""
        channels_data: Dict[Channel, ChannelSnapshot] = {}
        
        # 遍历所有通道
        for channel in [Channel.A, Channel.B]:
            # 获取通道数据
            pulse_operation = self._get_current_pulse_data(channel)
            current_strength = self._get_current_strength(channel)
        
            channels_data[channel] = ChannelSnapshot(
                pulse_operation=pulse_operation,
                current_strength=current_strength,
            )
        
        # 如果没有任何通道有数据，返回空快照（但仍然记录时间点）
        return RecordingSnapshot(channels=channels_data)
    
    # ============ 抽象方法 - 子类实现 ============
    
    @abstractmethod
    def _get_current_pulse_data(self, channel: Channel) -> PulseOperation:
        """获取指定通道当前的脉冲操作数据
        
        Args:
            channel: 通道标识
            
        Returns:
            Optional[PulseOperation]: 当前的脉冲操作数据，如果通道无数据返回None
        """
        ...
    
    @abstractmethod
    def _get_current_strength(self, channel: Channel) -> int:
        """获取指定通道当前的强度值
        
        Args:
            channel: 通道标识
            
        Returns:
            int: 当前强度值 [0-200]
        """
        ...
