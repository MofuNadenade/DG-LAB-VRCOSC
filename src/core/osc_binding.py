"""
OSC绑定管理模块

提供OSC地址和动作的绑定管理功能。
"""

import logging
from typing import Any, Optional, List, Dict, TYPE_CHECKING

from .osc_common import OSCRegistryObserver
from .osc_address import OSCAddress
from .osc_action import OSCAction

if TYPE_CHECKING:
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
        self.bindings: Dict[OSCAddress, OSCAction] = {}
        self.observers: List[OSCRegistryObserver] = []

    def add_observer(self, observer: OSCRegistryObserver) -> None:
        """添加观察者"""
        if observer not in self.observers:
            self.observers.append(observer)
    
    def remove_observer(self, observer: OSCRegistryObserver) -> None:
        """移除观察者"""
        if observer in self.observers:
            self.observers.remove(observer)
    
    def notify_binding_changed(self, address: OSCAddress, action: Optional[OSCAction]) -> None:
        """通知观察者绑定已变化"""
        for observer in self.observers:
            observer.on_binding_changed(address, action)

    def register_binding(self, address: OSCAddress, action: OSCAction) -> None:
        """注册绑定"""
        self.bindings[address] = action
        # 通知观察者
        self.notify_binding_changed(address, action)

    def unregister_binding(self, address: OSCAddress) -> None:
        """取消注册绑定"""
        if address in self.bindings:
            del self.bindings[address]
            # 通知观察者
            self.notify_binding_changed(address, None)

    async def handle(self, address: OSCAddress, *args: Any) -> None:
        """处理OSC消息"""
        action = self.bindings.get(address)
        if action:
            await action.handle(*args)
    
    def export_to_config(self) -> List[Dict[str, str]]:
        """导出所有绑定到配置格式"""
        return [{
            'address_name': address.name,
            'action_name': action.name
        } for address, action in self.bindings.items()]
    
    def validate_binding_data(self, binding: Dict[str, str]) -> bool:
        """验证绑定数据的完整性"""
        if not isinstance(binding, dict):
            return False
        
        required_keys = ['address_name', 'action_name']
        for key in required_keys:
            if key not in binding:
                return False
            if not isinstance(binding[key], str):
                return False
            if not binding[key].strip():
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
            if address.name not in address_registry.addresses_by_name:
                return False, f"地址'{address.name}'不存在于注册表中"
            # 检查地址对象是否一致
            registered_address = address_registry.addresses_by_name[address.name]
            if registered_address.code != address.code:
                return False, f"地址'{address.name}'的OSC代码已变更"
                
        if action_registry:
            if action.name not in action_registry.actions_by_name:
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
        
        for address, action in self.bindings.items():
            is_valid, error_msg = self.validate_binding(address, action, address_registry, action_registry)
            if not is_valid:
                invalid_bindings.append((address, action, error_msg))
        
        return invalid_bindings
    

