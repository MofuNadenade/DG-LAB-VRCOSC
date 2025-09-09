"""
设备服务抽象接口

定义了DG-LAB设备的纯硬件通信接口，只负责设备连接和基础操作，
不包含任何业务逻辑。业务逻辑统一由OSCActionService处理。
"""

from abc import abstractmethod
from typing import Optional, List

from core.dglab_pulse import Pulse
from core.recording import IPulseRecordHandler
from core.recording.playback_handler import IPulsePlaybackHandler
from core.recording.recording_models import RecordingSnapshot
from models import Channel, PulseOperation, StrengthData, StrengthOperationType, PlaybackMode
from services.service_interface import IService


class IDGLabDeviceService(IService):
    """DG-LAB设备服务抽象接口
    
    纯粹的设备硬件通信接口，只定义设备连接和基础操作功能。
    不同的连接方式（WebSocket、蓝牙等）都需要实现这个接口。
    所有业务逻辑（如动骨模式、开火模式等）由OSCActionService统一处理。
    """

    # ============ 连接管理 ============

    @abstractmethod
    async def start_service(self) -> bool:
        """启动设备连接服务
            
        Returns:
            bool: 启动是否成功
        """
        ...

    @abstractmethod
    async def stop_service(self) -> None:
        """停止设备连接服务"""
        ...

    @abstractmethod
    def is_service_running(self) -> bool:
        """检查设备连接服务运行状态
        
        Returns:
            bool: 服务是否运行中
        """
        ...

    @abstractmethod
    def get_connection_type(self) -> str:
        """获取连接类型标识
        
        Returns:
            str: 连接类型 ("websocket", "bluetooth", 等)
        """
        ...

    @abstractmethod
    async def wait_for_server_stop(self) -> None:
        """等待服务停止事件（用于替代轮询）"""
        ...

    # ============ 基础强度操作 ============

    @abstractmethod
    async def set_float_output(self, value: float, channel: Channel) -> None:
        """设置浮点输出强度（原始设备操作）"""
        ...

    @abstractmethod
    async def adjust_strength(self, operation_type: StrengthOperationType, value: int, channel: Channel) -> None:
        """调整通道强度（原始设备操作）"""
        ...

    @abstractmethod
    async def reset_strength(self, channel: Channel) -> None:
        """重置通道强度为0（原始设备操作）"""
        ...

    @abstractmethod
    async def increase_strength(self, channel: Channel) -> None:
        """增加通道强度（原始设备操作）"""
        ...

    @abstractmethod
    async def decrease_strength(self, channel: Channel) -> None:
        """减少通道强度（原始设备操作）"""
        ...

    # ============ 波形数据操作 ============

    @abstractmethod
    async def set_pulse_data(self, channel: Channel, pulse: Optional[Pulse]) -> None:
        """设置指定通道的波形数据"""
        ...

    @abstractmethod
    async def set_snapshots(self, snapshots: Optional[List[RecordingSnapshot]]) -> None:
        """设置录制快照列表"""
        ...

    @abstractmethod
    async def pause_frames(self) -> None:
        """暂停波形数据"""
        ...

    @abstractmethod
    async def resume_frames(self) -> None:
        """继续波形数据"""
        ...

    @abstractmethod
    def get_frames_position(self) -> int:
        """获取播放位置"""
        ...

    @abstractmethod
    async def seek_frames_to_position(self, position: int) -> None:
        """跳转到指定位置"""
        ...

    @abstractmethod
    def get_current_pulse_data(self, channel: Channel) -> Optional[PulseOperation]:
        """获取指定通道当前的脉冲操作数据"""
        ...

    # ============ 播放模式控制 ============

    @abstractmethod
    def set_playback_mode(self, mode: PlaybackMode) -> None:
        """设置播放模式（服务层接口）
        
        Args:
            mode: 播放模式（ONCE或LOOP）
        """
        ...

    @abstractmethod
    def get_playback_mode(self) -> PlaybackMode:
        """获取当前播放模式（服务层接口）
        
        Returns:
            PlaybackMode: 当前播放模式
        """
        ...

    # ============ 数据访问 ============

    @abstractmethod
    def get_last_strength(self) -> Optional[StrengthData]:
        """获取最后的强度数据"""
        ...

    @abstractmethod
    def update_strength_data(self, strength_data: StrengthData) -> None:
        """更新强度数据（通常由连接层调用）"""
        ...

    # ============ 录制功能 ============

    @abstractmethod
    def get_record_handler(self) -> IPulseRecordHandler:
        """获取脉冲录制处理器
        
        获取一个录制处理器实例，用于录制设备的原始波形数据。
        
        Returns:
            IPulseRecordHandler: 录制处理器实例
            
        Raises:
            RuntimeError: 如果设备未连接或不支持录制功能
        """
        ...
    
    @abstractmethod
    def get_playback_handler(self) -> IPulsePlaybackHandler:
        """获取脉冲回放处理器
        
        获取一个回放处理器实例，用于回放录制的波形数据。
        
        Returns:
            IPulsePlaybackHandler: 回放处理器实例
            
        Raises:
            RuntimeError: 如果设备未连接或不支持回放功能
        """
        ...
