"""
OSC通用模块

包含OSC系统的通用类型、枚举、协议和验证器。
"""

from typing import Protocol, Optional, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from .osc_address import OSCAddress
    from .osc_action import OSCAction


class OSCActionType(Enum):
    """OSC动作类型枚举"""
    CHANNEL_CONTROL = "channel_control"      # 通道控制
    STRENGTH_CONTROL = "strength_control"    # 强度控制  
    PANEL_CONTROL = "panel_control"          # 面板控制
    PULSE_CONTROL = "pulse_control"          # 波形控制
    CHATBOX_CONTROL = "chatbox_control"      # ChatBox控制
    CUSTOM = "custom"


class OSCRegistryObserver(Protocol):
    """注册表观察者接口"""
    def on_address_added(self, address: 'OSCAddress') -> None: ...
    def on_address_removed(self, address: 'OSCAddress') -> None: ...
    def on_action_added(self, action: 'OSCAction') -> None: ...
    def on_action_removed(self, action: 'OSCAction') -> None: ...
    def on_binding_changed(self, address: 'OSCAddress', action: Optional['OSCAction']) -> None: ...


class OSCAddressValidator:
    """OSC地址验证器"""
    
    @staticmethod
    def validate_address_name(name: str) -> tuple[bool, str]:
        """验证地址名称"""
        if not name or not name.strip():
            return False, "地址名称不能为空"
        
        if len(name) > 50:
            return False, "地址名称过长（最多50字符）"
            
        # 检查保留字符
        reserved_keywords = ["[手动输入...]", "---", "[自定义]"]
        if any(keyword in name for keyword in reserved_keywords):
            return False, "地址名称不能包含保留关键字"
            
        return True, ""
    
    @staticmethod
    def validate_osc_code(code: str) -> tuple[bool, str]:
        """验证OSC代码"""
        if not code or not code.strip():
            return False, "OSC代码不能为空"
            
        # 只支持完整OSC路径（必须以 / 开头）
        if not code.startswith('/'):
            return False, "OSC代码必须是完整的OSC路径，应以 '/' 开头"
            
        # 检查特殊字符
        invalid_chars = [' ', '#', '*', ',', '?', '[', ']', '{', '}']
        for char in invalid_chars:
            if char in code:
                return False, f"OSC代码不能包含字符: {char}"
                
        # 检查长度
        if len(code) > 200:
            return False, "OSC代码过长（最多200字符）"
                
        return True, ""
    
    @staticmethod
    def validate_action_name(name: str) -> tuple[bool, str]:
        """验证动作名称"""
        if not name or not name.strip():
            return False, "动作名称不能为空"
            
        if len(name) > 50:
            return False, "动作名称过长（最多50字符）"

        # 自定义动作
        return True, ""
