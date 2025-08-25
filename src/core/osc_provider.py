"""
OSC选项提供模块

为UI组件提供OSC相关的选项数据。
"""

from typing import List

from core.registries import Registries

from .osc_common import OSCActionType


class OSCOptionsProvider:
    """OSC选项数据提供者"""
    
    def __init__(self, registries: Registries) -> None:
        super().__init__()
        self.registries = registries
    
    def get_address_name_options(self) -> List[str]:
        """获取地址名称选项"""
        return [addr.name for addr in self.registries.address_registry.addresses]
    
    def get_action_name_options(self) -> List[str]:
        """获取动作名称选项"""
        return [action.name for action in self.registries.action_registry.actions]
    
    def get_action_name_options_by_type(self, action_type: OSCActionType) -> List[str]:
        """根据类型获取动作名称选项"""
        actions = self.registries.action_registry.get_actions_by_type(action_type)
        return [action.name for action in actions]
    
    def get_osc_code_options(self) -> List[str]:
        """获取OSC代码选项"""
        # 从模板获取预定义选项
        template_options = self.registries.template_registry.get_template_options()
        
        # 从已注册的地址获取选项
        registered_options = [addr.code for addr in self.registries.address_registry.addresses]
        
        # 合并并去重
        all_options = list(set(template_options + registered_options))
        all_options.sort()
        return all_options
    
    def get_osc_code_options_by_prefix(self, prefix: str) -> List[str]:
        """根据前缀获取OSC代码选项"""
        templates = self.registries.template_registry.get_templates_by_prefix(prefix)
        return [template.code for template in templates]
