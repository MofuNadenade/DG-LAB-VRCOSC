from typing import Optional, Protocol
from core.core_interface import CoreInterface
from core.dglab_controller import DGLabController
from models import SettingsDict


class UIInterface(CoreInterface, Protocol):
    """统一的UI操作接口协议"""
    # 数据访问属性
    controller: Optional['DGLabController']
    settings: SettingsDict

    def set_controller(self, controller: Optional['DGLabController']) -> None: ...
