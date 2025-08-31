"""
OSC绑定管理模块

提供OSC地址和动作的绑定管理功能。
"""

import logging
from typing import Optional, List, Dict, Union

from models import OSCBindingDict, OSCValue
from .osc_action import OSCAction
from .osc_address import OSCAddress
from .osc_common import OSCRegistryObserver, OSCBinding

logger = logging.getLogger(__name__)


class OSCBindingRegistry:
    """OSC绑定注册表"""

    def __init__(self) -> None:
        super().__init__()
        self._bindings: List[OSCBinding] = []
        self._bindings_by_address: Dict[OSCAddress, OSCBinding] = {}
        self._bindings_by_action: Dict[OSCAction, List[OSCBinding]] = {}
        self._bindings_by_id: Dict[int, OSCBinding] = {}
        self._observers: List[OSCRegistryObserver] = []
        self._next_binding_id: int = 1

    @property
    def bindings(self) -> List[OSCBinding]:
        """获取所有绑定列表（只读）"""
        return self._bindings.copy()

    @property
    def bindings_by_address(self) -> Dict[OSCAddress, OSCBinding]:
        """获取按地址索引的绑定字典（只读）"""
        return self._bindings_by_address.copy()

    @property
    def bindings_by_action(self) -> Dict[OSCAction, List[OSCBinding]]:
        """获取按动作索引的绑定字典（只读）"""
        return {action: bindings.copy() for action, bindings in self._bindings_by_action.items()}

    @property
    def bindings_by_id(self) -> Dict[int, OSCBinding]:
        """获取按ID索引的绑定字典（只读）"""
        return self._bindings_by_id.copy()

    def get_binding(self, address: OSCAddress) -> Optional[OSCAction]:
        """根据地址获取绑定的动作"""
        binding = self._bindings_by_address.get(address)
        return binding.action if binding else None

    def get_binding_by_id(self, binding_id: int) -> Optional[OSCBinding]:
        """根据绑定ID获取绑定"""
        return self._bindings_by_id.get(binding_id)

    def get_bindings_by_action(self, action: OSCAction) -> List[OSCBinding]:
        """根据动作获取所有相关的绑定"""
        return self._bindings_by_action.get(action, []).copy()

    def get_binding_count(self) -> int:
        """获取绑定总数"""
        return len(self._bindings)

    def has_binding(self, address: OSCAddress) -> bool:
        """检查指定地址是否存在绑定"""
        return address in self._bindings_by_address

    def has_binding_id(self, binding_id: int) -> bool:
        """检查指定ID的绑定是否存在"""
        return binding_id in self._bindings_by_id

    def has_action_binding(self, action: OSCAction) -> bool:
        """检查指定动作是否存在绑定"""
        return action in self._bindings_by_action and len(self._bindings_by_action[action]) > 0

    def is_address_bound(self, address: OSCAddress) -> bool:
        """检查指定地址是否已被绑定（别名方法）"""
        return self.has_binding(address)

    def is_action_bound(self, action: OSCAction) -> bool:
        """检查指定动作是否已被绑定（别名方法）"""
        return self.has_action_binding(action)

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

    def _get_next_binding_id(self) -> int:
        """获取下一个可用的绑定ID"""
        current_id = self._next_binding_id
        self._next_binding_id += 1
        return current_id

    def register_binding(self, address: OSCAddress, action: OSCAction) -> OSCBinding:
        """注册绑定"""
        # 如果地址已存在绑定，先移除
        if address in self._bindings_by_address:
            self.unregister_binding(address)
        
        binding_id = self._get_next_binding_id()
        binding = OSCBinding(binding_id, address, action)
        
        self._bindings.append(binding)
        self._bindings_by_address[address] = binding
        self._bindings_by_id[binding_id] = binding
        
        # 添加到动作索引（支持一个动作被多个地址绑定）
        if action not in self._bindings_by_action:
            self._bindings_by_action[action] = []
        self._bindings_by_action[action].append(binding)
        
        # 通知观察者
        self.notify_binding_changed(address, action)
        
        return binding

    def unregister_binding(self, address: OSCAddress) -> None:
        """取消注册绑定"""
        binding = self._bindings_by_address.get(address)
        if binding:
            self._bindings.remove(binding)
            self._bindings_by_address.pop(address, None)
            self._bindings_by_id.pop(binding.id, None)
            
            # 从动作索引中移除
            if binding.action in self._bindings_by_action:
                self._bindings_by_action[binding.action].remove(binding)
                if not self._bindings_by_action[binding.action]:
                    del self._bindings_by_action[binding.action]
            
            # 通知观察者
            self.notify_binding_changed(address, None)

    def clear_bindings(self) -> None:
        """清空所有绑定"""
        self._bindings.clear()
        self._bindings_by_address.clear()
        self._bindings_by_action.clear()
        self._bindings_by_id.clear()

    async def handle(self, address: OSCAddress, *args: OSCValue) -> None:
        """处理OSC消息"""
        action = self.get_binding(address)
        if action:
            await action.handle(*args)

    def export_to_config(self) -> List[OSCBindingDict]:
        """导出所有绑定到配置格式"""
        return [{
            'address_name': binding.address.name,
            'action_name': binding.action.name
        } for binding in self._bindings]

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

    def update_binding_address(self, binding_id: int, new_address: OSCAddress) -> bool:
        """通过ID更新绑定的地址
        
        Args:
            binding_id: 要更新的绑定ID
            new_address: 新的地址对象
            
        Returns:
            bool: 更新成功返回True，如果ID不存在返回False
        """
        binding = self._bindings_by_id.get(binding_id)
        if not binding:
            return False
            
        old_address = binding.address
        binding.address = new_address
        
        # 更新地址索引
        self._bindings_by_address.pop(old_address, None)
        self._bindings_by_address[new_address] = binding
        
        return True

    def update_binding_action(self, binding_id: int, new_action: OSCAction) -> bool:
        """通过ID更新绑定的动作
        
        Args:
            binding_id: 要更新的绑定ID
            new_action: 新的动作对象
            
        Returns:
            bool: 更新成功返回True，如果ID不存在返回False
        """
        binding = self._bindings_by_id.get(binding_id)
        if not binding:
            return False
            
        old_action = binding.action
        binding.action = new_action
        
        # 更新动作索引
        if old_action in self._bindings_by_action:
            self._bindings_by_action[old_action].remove(binding)
            if not self._bindings_by_action[old_action]:
                del self._bindings_by_action[old_action]
        
        if new_action not in self._bindings_by_action:
            self._bindings_by_action[new_action] = []
        self._bindings_by_action[new_action].append(binding)
        
        return True
