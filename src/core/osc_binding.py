"""
OSC绑定管理模块

提供OSC地址和动作的绑定管理功能。
"""

from typing import Any, Optional, List, Dict

from .osc_common import OSCRegistryObserver
from .osc_address import OSCAddress
from .osc_action import OSCAction
from .osc_template import OSCBindingTemplateRegistry


class OSCBindingRegistry:
    """OSC绑定注册表"""
    
    def __init__(self) -> None:
        self.bindings: Dict[OSCAddress, OSCAction] = {}
        self.observers: List[OSCRegistryObserver] = []
        self.binding_template_registry: OSCBindingTemplateRegistry = OSCBindingTemplateRegistry()

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
    
    def get_binding_templates(self) -> List[Dict[str, str]]:
        """获取绑定模板配置"""
        return self.binding_template_registry.get_binding_templates()
    
    def is_binding_template(self, binding: Dict[str, str]) -> bool:
        """检查绑定是否为模板绑定"""
        return self.binding_template_registry.is_binding_template(binding)
    
    def filter_non_binding_templates(self, bindings: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """过滤掉模板绑定，只返回用户自定义的绑定"""
        return self.binding_template_registry.filter_non_binding_templates(bindings)
