"""
设备服务抽象接口

定义了DG-LAB设备控制的统一接口，支持多种连接方式的实现。
"""

from typing import Optional, Union, Protocol

from PySide6.QtGui import QPixmap

from core.dglab_pulse import Pulse
from models import Channel, ConnectionState, StrengthData, StrengthOperationType


class IDGLabService(Protocol):
    """DG-LAB设备服务抽象接口
    
    定义了所有设备控制功能的统一接口，不同的连接方式（WebSocket、蓝牙等）
    都需要实现这个接口以确保功能的一致性。
    """

    # ============ 连接管理 ============

    async def start_service(self, ip: str, port: int, remote_address: Optional[str] = None) -> bool:
        """启动WebSocket服务器
        
        Args:
            ip: 监听IP地址
            port: WebSocket端口
            remote_address: 远程地址（可选）
            
        Returns:
            bool: 启动是否成功
        """
        ...

    async def stop_service(self) -> None:
        """停止WebSocket服务器"""
        ...

    def is_server_running(self) -> bool:
        """检查服务器运行状态
        
        Returns:
            bool: 服务器是否运行中
        """
        ...

    def get_qrcode_image(self) -> Optional[QPixmap]:
        """获取二维码图像
        
        Returns:
            Optional[QPixmap]: 二维码图像，如果未生成则为None
        """
        ...

    def get_connection_state(self) -> ConnectionState:
        """获取当前连接状态
        
        Returns:
            ConnectionState: 当前连接状态
        """
        ...

    async def connect(self) -> bool:
        """连接设备
        
        Returns:
            bool: 连接是否成功
        """
        ...

    async def disconnect(self) -> None:
        """断开设备连接"""
        ...

    def is_connected(self) -> bool:
        """检查设备连接状态
        
        Returns:
            bool: 是否已连接
        """
        ...

    def get_connection_type(self) -> str:
        """获取连接类型标识
        
        Returns:
            str: 连接类型 ("websocket", "bluetooth", 等)
        """
        ...

    async def wait_for_server_stop(self) -> None:
        """等待服务器停止事件（用于替代轮询）"""
        ...

    # ============ 属性访问 ============

    @property
    def fire_mode_strength_step(self) -> int:
        """开火模式强度步进"""
        ...

    @fire_mode_strength_step.setter
    def fire_mode_strength_step(self, value: int) -> None:
        ...

    @property
    def fire_mode_disabled(self) -> bool:
        """开火模式是否禁用"""
        ...

    @fire_mode_disabled.setter
    def fire_mode_disabled(self, value: bool) -> None:
        ...

    @property
    def enable_panel_control(self) -> bool:
        """面板控制是否启用"""
        ...

    @enable_panel_control.setter
    def enable_panel_control(self, value: bool) -> None:
        ...

    # ============ 状态查询 ============

    def get_current_channel(self) -> Channel:
        """获取当前选中的通道"""
        ...

    def get_last_strength(self) -> Optional[StrengthData]:
        """获取最后的强度数据"""
        ...

    def is_dynamic_bone_enabled(self, channel: Channel) -> bool:
        """检查指定通道的动骨模式是否启用"""
        ...

    def get_pulse_mode(self, channel: Channel) -> int:
        """获取指定通道的波形模式索引"""
        ...

    def get_current_pulse_name(self, channel: Channel) -> str:
        """获取指定通道当前波形的名称"""
        ...

    # ============ 通道控制 ============

    async def set_channel(self, value: Union[int, float]) -> Optional[Channel]:
        """设置当前活动通道"""
        ...

    # ============ 强度控制 ============

    async def set_float_output(self, value: float, channel: Channel) -> None:
        """设置浮点输出强度（用于动骨模式）"""
        ...

    async def adjust_strength(self, operation_type: StrengthOperationType, value: int, channel: Channel) -> None:
        """调整通道强度"""
        ...

    async def reset_strength(self, value: bool, channel: Channel) -> None:
        """重置通道强度为0"""
        ...

    async def increase_strength(self, value: bool, channel: Channel) -> None:
        """增加通道强度"""
        ...

    async def decrease_strength(self, value: bool, channel: Channel) -> None:
        """减少通道强度"""
        ...

    # ============ 波形控制 ============

    async def update_pulse_data(self) -> None:
        """更新设备上的波形数据"""
        ...

    async def set_pulse_data(self, _: bool, channel: Channel, pulse_index: int, update_ui: bool = True) -> None:
        """设置指定通道的波形数据"""
        ...

    async def set_test_pulse(self, channel: Channel, pulse: Pulse) -> None:
        """在指定通道播放测试波形"""
        ...

    def set_pulse_mode(self, channel: Channel, value: int) -> None:
        """设置指定通道的波形模式"""
        ...

    # ============ 模式控制 ============

    def set_dynamic_bone_mode(self, channel: Channel, enabled: bool) -> None:
        """设置指定通道的动骨模式"""
        ...

    async def set_mode(self, value: int, channel: Channel) -> None:
        """切换工作模式（延时触发）"""
        ...

    async def set_panel_control(self, value: float) -> None:
        """设置面板控制功能开关"""
        ...

    async def set_strength_step(self, value: float) -> None:
        """设置开火模式步进值"""
        ...

    # ============ 开火模式 ============

    async def strength_fire_mode(self, value: bool, channel: Channel, fire_strength: int,
                                 last_strength: Optional[StrengthData]) -> None:
        """一键开火模式"""
        ...

    # ============ 数据更新 ============

    def update_strength_data(self, strength_data: StrengthData) -> None:
        """更新强度数据（通常由连接层调用）"""
        ...
