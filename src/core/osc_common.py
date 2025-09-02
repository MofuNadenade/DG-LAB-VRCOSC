"""
OSC通用模块

包含OSC系统的通用类型、枚举、协议和验证器。
"""

from enum import Enum
from typing import Awaitable, List, Protocol, Optional, Set

from models import OSCValue, PulseOperation


class OSCActionType(Enum):
    """OSC动作类型枚举"""
    CHANNEL_CONTROL = "channel_control"  # 通道控制
    STRENGTH_CONTROL = "strength_control"  # 强度控制
    PANEL_CONTROL = "panel_control"  # 面板控制
    PULSE_CONTROL = "pulse_control"  # 波形控制
    CHATBOX_CONTROL = "chatbox_control"  # ChatBox控制
    CUSTOM = "custom"


class OSCActionCallback(Protocol):
    """OSC动作回调协议"""

    def __call__(self, *args: OSCValue) -> Awaitable[None]:
        ...


class OSCAction:
    """OSC动作"""

    def __init__(self, action_id: int, name: str, callback: OSCActionCallback,
                 action_type: OSCActionType = OSCActionType.CUSTOM,
                 tags: Optional[Set[str]] = None) -> None:
        super().__init__()
        # 验证输入
        name_valid, name_error = OSCAddressValidator.validate_action_name(name)
        if not name_valid:
            raise ValueError(f"无效的动作名称: {name_error}")

        self.id: int = action_id
        self.name: str = name.strip()
        self.callback: OSCActionCallback = callback
        self.action_type: OSCActionType = action_type
        self.tags: Set[str] = tags or set()

    async def handle(self, *args: OSCValue) -> None:
        await self.callback(*args)

    def __str__(self) -> str:
        return f"OSCAction(id={self.id}, name='{self.name}', type='{self.action_type.value}')"

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OSCAction):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return self.id


class OSCAddress:
    """OSC地址"""

    def __init__(self, address_id: int, name: str, code: str) -> None:
        super().__init__()
        # 验证输入
        name_valid, name_error = OSCAddressValidator.validate_address_name(name)
        if not name_valid:
            raise ValueError(f"无效的地址名称: {name_error}")

        code_valid, code_error = OSCAddressValidator.validate_osc_code(code)
        if not code_valid:
            raise ValueError(f"无效的OSC代码: {code_error}")

        self.id: int = address_id
        self.name: str = name.strip()
        self.code: str = code.strip()

    def __str__(self) -> str:
        return f"OSCAddress(id={self.id}, name='{self.name}', code='{self.code}')"

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OSCAddress):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return self.id


class OSCBinding:
    """OSC绑定"""

    def __init__(self, binding_id: int, address: OSCAddress, action: OSCAction) -> None:
        super().__init__()
        self.id: int = binding_id
        self.address: OSCAddress = address
        self.action: OSCAction = action

    def __str__(self) -> str:
        return f"OSCBinding(id={self.id}, address='{self.address.name}', action='{self.action.name}')"

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OSCBinding):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return self.id


class Pulse:
    def __init__(self, pulse_id: int, name: str, data: List[PulseOperation]) -> None:
        super().__init__()
        self.id: int = pulse_id
        self.name: str = name
        self.data: List[PulseOperation] = data
    
    def __str__(self) -> str:
        return f"Pulse(id={self.id}, name={self.name}, data={self.data})"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Pulse):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        return self.id


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


class OSCRegistryObserver(Protocol):
    """注册表观察者接口"""

    def on_address_added(self, address: OSCAddress) -> None: ...

    def on_address_removed(self, address: OSCAddress) -> None: ...

    def on_action_added(self, action: OSCAction) -> None: ...

    def on_action_removed(self, action: OSCAction) -> None: ...

    def on_binding_changed(self, address: OSCAddress, action: Optional[OSCAction]) -> None: ...

    def on_pulse_added(self, pulse: Pulse) -> None: ...

    def on_pulse_removed(self, pulse: Pulse) -> None: ...
