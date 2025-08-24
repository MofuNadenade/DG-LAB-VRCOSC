"""
OSC绑定管理模块

提供OSC地址和动作的绑定管理功能。
"""

import logging
from typing import Optional, List, Dict, TYPE_CHECKING, Union

from .osc_common import OSCRegistryObserver
from models import OSCValue

from .osc_address import OSCAddress
from .osc_action import OSCAction

if TYPE_CHECKING:
    from models import OSCBindingDict
    from .osc_address import OSCAddressRegistry
    from .osc_action import OSCActionRegistry

logger = logging.getLogger(__name__)

 
class OSCBindingTemplate:
    """OSC绑定模板"""
    
    def __init__(self, address_name: str, action_name: str) -> None:
        self.address_name: str = address_name
        self.action_name: str = action_name
    
    def to_dict(self) -> Dict[str, str]:
        """转换为字典格式"""
        return {
            'address_name': self.address_name,
            'action_name': self.action_name
        }
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (OSCBindingTemplate, dict)):
            return False
        if isinstance(other, dict):
            return (self.address_name == other.get('address_name') and 
                    self.action_name == other.get('action_name'))
        return (self.address_name == other.address_name and 
                self.action_name == other.action_name)
    
    def __hash__(self) -> int:
        return hash((self.address_name, self.action_name))
    
    def __str__(self) -> str:
        return f"OSCBindingTemplate({self.address_name} -> {self.action_name})"


class OSCBindingRegistry:
    """OSC绑定注册表"""
    
    def __init__(self) -> None:
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
    
    def export_to_config(self) -> List['OSCBindingDict']:
        """导出所有绑定到配置格式"""
        return [{
            'address_name': address.name,
            'action_name': action.name
        } for address, action in self._bindings.items()]
    
    def validate_binding_data(self, binding: Dict[str, Union[str, int, bool]]) -> bool:
        """验证绑定数据的完整性"""
        if not isinstance(binding, dict):
            return False  # type: ignore[unreachable]
        
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
    
    def validate_binding(self, address: OSCAddress, action: OSCAction, 
                        address_registry: Optional['OSCAddressRegistry'] = None, 
                        action_registry: Optional['OSCActionRegistry'] = None) -> tuple[bool, str]:
        """验证绑定的有效性
        
        Args:
            address: OSC地址对象
            action: OSC动作对象  
            address_registry: 地址注册表（可选，用于检查地址是否仍然存在）
            action_registry: 动作注册表（可选，用于检查动作是否仍然存在）
            
        Returns:
            tuple[bool, str]: (是否有效, 错误信息)
        """
        # 基本对象验证
        if not address or not action:
            return False, "地址或动作对象为空"
        
        # 验证地址对象的有效性
        try:
            if not address.name or not address.name.strip():
                return False, "地址名称为空"
            if not address.code or not address.code.strip():
                return False, "OSC代码为空"
        except AttributeError:
            return False, "地址对象缺少必要属性"
        
        # 验证动作对象的有效性
        try:
            if not action.name or not action.name.strip():
                return False, "动作名称为空"
        except AttributeError:
            return False, "动作对象缺少必要属性"
        
        # 如果提供了注册表，检查对象是否仍然在注册表中
        if address_registry:
            if not address_registry.has_address_name(address.name):
                return False, f"地址'{address.name}'不存在于注册表中"
            # 检查地址对象是否一致
            registered_address = address_registry.get_address_by_name(address.name)
            if registered_address and registered_address.code != address.code:
                return False, f"地址'{address.name}'的OSC代码已变更"
                
        if action_registry:
            if not action_registry.has_action_name(action.name):
                return False, f"动作'{action.name}'不存在于注册表中"
        
        return True, ""
    
    def get_invalid_bindings(self, address_registry: Optional['OSCAddressRegistry'] = None, 
                           action_registry: Optional['OSCActionRegistry'] = None) -> List[tuple[OSCAddress, OSCAction, str]]:
        """获取所有无效的绑定
        
        Args:
            address_registry: 地址注册表
            action_registry: 动作注册表
            
        Returns:
            List[tuple[OSCAddress, OSCAction, str]]: 无效绑定列表，每个元素包含(地址, 动作, 错误信息)
        """
        invalid_bindings = []
        
        for address, action in self._bindings.items():
            is_valid, error_msg = self.validate_binding(address, action, address_registry, action_registry)
            if not is_valid:
                invalid_bindings.append((address, action, error_msg))
        
        return invalid_bindings
    

