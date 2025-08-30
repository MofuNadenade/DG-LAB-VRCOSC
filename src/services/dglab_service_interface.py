"""
设备服务抽象接口

定义了DG-LAB设备的纯硬件通信接口，只负责设备连接和基础操作，
不包含任何业务逻辑。业务逻辑统一由OSCActionService处理。
"""

from typing import Optional, Protocol

from core.dglab_pulse import Pulse
from models import Channel, StrengthData, StrengthOperationType
from services.service_interface import IService


class IDGLabDeviceService(IService, Protocol):
    """DG-LAB设备服务抽象接口
    
    纯粹的设备硬件通信接口，只定义设备连接和基础操作功能。
    不同的连接方式（WebSocket、蓝牙等）都需要实现这个接口。
    所有业务逻辑（如动骨模式、开火模式等）由OSCActionService统一处理。
    """

    # ============ 连接管理 ============

    async def start_service(self) -> bool:
        """启动设备连接服务
            
        Returns:
            bool: 启动是否成功
        """
        ...

    async def stop_service(self) -> None:
        """停止设备连接服务"""
        ...

    def is_service_running(self) -> bool:
        """检查设备连接服务运行状态
        
        Returns:
            bool: 服务是否运行中
        """
        ...

    def get_connection_type(self) -> str:
        """获取连接类型标识
        
        Returns:
            str: 连接类型 ("websocket", "bluetooth", 等)
        """
        ...

    async def wait_for_server_stop(self) -> None:
        """等待服务停止事件（用于替代轮询）"""
        ...

    # ============ 基础强度操作 ============

    async def set_float_output(self, value: float, channel: Channel) -> None:
        """设置浮点输出强度（原始设备操作）"""
        ...

    async def adjust_strength(self, operation_type: StrengthOperationType, value: int, channel: Channel) -> None:
        """调整通道强度（原始设备操作）"""
        ...

    async def reset_strength(self, value: bool, channel: Channel) -> None:
        """重置通道强度为0（原始设备操作）"""
        ...

    async def increase_strength(self, value: bool, channel: Channel) -> None:
        """增加通道强度（原始设备操作）"""
        ...

    async def decrease_strength(self, value: bool, channel: Channel) -> None:
        """减少通道强度（原始设备操作）"""
        ...

    # ============ 波形数据操作 ============

    async def update_pulse_data(self) -> None:
        """更新设备上的波形数据"""
        ...

    async def set_pulse_data(self, channel: Channel, pulse_index: int, update_ui: bool = True) -> None:
        """设置指定通道的波形数据"""
        ...

    async def set_test_pulse(self, channel: Channel, pulse: Pulse) -> None:
        """在指定通道播放测试波形"""
        ...

    # ============ 数据访问 ============

    def get_last_strength(self) -> Optional[StrengthData]:
        """获取最后的强度数据"""
        ...

    def update_strength_data(self, strength_data: StrengthData) -> None:
        """更新强度数据（通常由连接层调用）"""
        ...
