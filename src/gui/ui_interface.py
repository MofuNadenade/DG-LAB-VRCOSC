from typing import Optional, Protocol

from core.core_interface import CoreInterface
from core.service_controller import ServiceController
from models import SettingsDict


class UIInterface(CoreInterface, Protocol):
    """统一的UI操作接口协议"""
    # 数据访问属性
    controller: Optional[ServiceController]
    settings: SettingsDict

    def set_controller(self, controller: Optional[ServiceController]) -> None: ...
