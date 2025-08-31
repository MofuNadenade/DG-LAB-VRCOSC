from typing import Optional, Protocol

from core import OSCOptionsProvider
from core.core_interface import CoreInterface
from core.service_controller import ServiceController
from models import SettingsDict


class UIInterface(CoreInterface, Protocol):
    """统一的UI操作接口协议"""
    # 数据访问属性
    settings: SettingsDict
    service_controller: Optional[ServiceController]
    options_provider: OSCOptionsProvider

    def set_service_controller(self, service_controller: Optional[ServiceController]) -> None: ...
