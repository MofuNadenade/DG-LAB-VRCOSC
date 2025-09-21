from abc import ABC, abstractmethod
from typing import Optional



from core.dglab_pulse import Pulse
from core.registries import Registries
from models import ConnectionState, StrengthData, Channel, UIFeature


class CoreInterface(ABC):
    """统一的核心操作接口协议"""
    # 数据访问属性
    registries: Registries

    # 连接状态管理
    @abstractmethod
    def set_connection_state(self, state: ConnectionState, message: str = "") -> None: ...

    @abstractmethod
    def get_connection_state(self) -> ConnectionState: ...

    # 当前波形管理
    @abstractmethod
    def set_current_pulse(self, channel: Channel, pulse: Optional[Pulse]) -> None: ...

    @abstractmethod
    def get_current_pulse(self, channel: Channel) -> str: ...

    # 功能开关管理
    @abstractmethod
    def set_feature_state(self, feature: UIFeature, enabled: bool) -> None: ...

    @abstractmethod
    def get_feature_state(self, feature: UIFeature) -> bool: ...

    # 数值控制管理
    @abstractmethod
    def set_fire_mode_strength_step(self, value: int) -> None: ...

    @abstractmethod
    def get_fire_mode_strength_step(self) -> int: ...

    # 配置文件管理
    @abstractmethod
    def save_settings(self) -> None: ...

    # 日志管理
    @abstractmethod
    def log_info(self, message: str) -> None: ...

    @abstractmethod
    def log_warning(self, message: str) -> None: ...

    @abstractmethod
    def log_error(self, message: str) -> None: ...

    @abstractmethod
    def clear_logs(self) -> None: ...

    # 连接状态通知回调
    @abstractmethod
    def on_client_connected(self) -> None: ...

    @abstractmethod
    def on_client_disconnected(self) -> None: ...

    @abstractmethod
    def on_client_reconnected(self) -> None: ...

    # 状态更新回调
    @abstractmethod
    def on_current_channel_updated(self, channel: Channel) -> None: ...

    @abstractmethod
    def on_strength_data_updated(self, strength_data: StrengthData) -> None: ...
