"""
OSC绑定管理模块

提供OSC地址和动作的绑定管理功能。
"""

import logging
from typing import Optional, List, Dict, Union

from models import OSCBindingDict, OSCValue
from .osc_action import OSCAction
from .osc_address import OSCAddress
from .osc_common import OSCRegistryObserver

logger = logging.getLogger(__name__)


class OSCBindingTemplate:
    """OSC绑定模板"""

    def __init__(self, address_name: str, action_name: str) -> None:
        super().__init__()
        self.address_name: str = address_name
        self.action_name: str = action_name

    def to_dict(self) -> Dict[str, str]:
        """转换为字典格式"""
        return {
            'address_name': self.address_name,
            'action_name': self.action_name
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OSCBindingTemplate):
            return False
        return self.address_name == other.address_name and self.action_name == other.action_name

    def __hash__(self) -> int:
        return hash((self.address_name, self.action_name))

    def __str__(self) -> str:
        return f"OSCBindingTemplate({self.address_name} -> {self.action_name})"


class OSCBindingRegistry:
    """OSC绑定注册表"""

    def __init__(self) -> None:
        super().__init__()
        self._bindings: Dict[OSCAddress, OSCAction] = {}
        self._observers: List[OSCRegistryObserver] = []

    @property
    def bindings(self) -> Dict[OSCAddress, OSCAction]:
        """获取所有绑定字典（只读）"""
        return self._bindings.copy()

    def get_binding(self, address: OSCAddress) -> Optional[OSCAction]:
        """获取指定地址的绑定动作"""
        return self._bindings.get(address)

    def has_binding(self, address: OSCAddress) -> bool:
        """检查是否存在指定地址的绑定"""
        return address in self._bindings

    def get_binding_count(self) -> int:
        """获取绑定总数"""
        return len(self._bindings)

    def get_all_addresses(self) -> List[OSCAddress]:
        """获取所有已绑定的地址"""
        return list(self._bindings.keys())

    def get_all_actions(self) -> List[OSCAction]:
        """获取所有已绑定的动作"""
        return list(self._bindings.values())

    def add_observer(self, observer: OSCRegistryObserver) -> None:
        """添加观察者"""
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: OSCRegistryObserver) -> None:
        """移除观察者"""
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_binding_changed(self, address: OSCAddress, action: Optional[OSCAction]) -> None:
        """通知观察者绑定已变化"""
        for observer in self._observers:
            observer.on_binding_changed(address, action)

    def register_binding(self, address: OSCAddress, action: OSCAction) -> None:
        """注册绑定"""
        self._bindings[address] = action
        # 通知观察者
        self.notify_binding_changed(address, action)

    def unregister_binding(self, address: OSCAddress) -> None:
        """取消注册绑定"""
        if address in self._bindings:
            del self._bindings[address]
            # 通知观察者
            self.notify_binding_changed(address, None)

    async def handle(self, address: OSCAddress, *args: OSCValue) -> None:
        """处理OSC消息"""
        action = self._bindings.get(address)
        if action:
            await action.handle(*args)

    def export_to_config(self) -> List[OSCBindingDict]:
        """导出所有绑定到配置格式"""
        return [{
            'address_name': address.name,
            'action_name': action.name
        } for address, action in self._bindings.items()]

    def validate_binding_data(self, binding: Dict[str, Union[str, int, bool]]) -> bool:
        """验证绑定数据的完整性"""
        required_keys = ['address_name', 'action_name']
        for key in required_keys:
            if key not in binding:
                return False
            value = binding[key]
            if not isinstance(value, str):
                return False
            if not value.strip():
                return False

        return True
