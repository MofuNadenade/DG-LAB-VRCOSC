
import enum
from typing import Any, Coroutine, Protocol

import logging
logger = logging.getLogger(__name__)

class OSCButton:
    def __init__(self, name: str, index: int, code: str):
        self.name = name
        self.index = index
        self.code = code

class OSCButtonRegistry:
    def __init__(self):
        self.buttons: list[OSCButton] = []
        self.buttons_by_name: dict[str, OSCButton] = {}
        self.buttons_by_code: dict[str, OSCButton] = {}

        self.register_default_buttons()

    def register_button(self, name: str, code: str) -> OSCButton:
        button = OSCButton(name, len(self.buttons), code)
        self.buttons.append(button)
        self.buttons_by_name[name] = button
        self.buttons_by_code[code] = button
        return button

    def register_default_buttons(self):
        self.register_button("按钮1", "1")
        self.register_button("按钮2", "2")
        self.register_button("按钮3", "3")
        self.register_button("按钮4", "4")
        self.register_button("按钮5", "5")
        self.register_button("按钮6", "6")
        self.register_button("按钮7", "7")
        self.register_button("按钮8", "8")
        self.register_button("按钮9", "9")
        self.register_button("按钮10", "10")
        self.register_button("按钮11", "11")
        self.register_button("按钮12", "12")
        self.register_button("按钮13", "13")
        self.register_button("按钮14", "14")
        self.register_button("按钮15", "15")

class OSCButtonCallback(Protocol):
    def __call__(self, *args: Any) -> Coroutine[Any, Any, Any]:
        ...

class OSCAction:
    def __init__(self, index: int, name: str, callback: OSCButtonCallback):
        self.index = index
        self.name = name
        self.callback = callback
    
    async def handle(self, *args: Any):
        await self.callback(*args)

class OSCActionRegistry:
    def __init__(self):
        self.actions: list[OSCAction] = []
        self.actions_by_name: dict[str, OSCAction] = {}

    def register_action(self, name: str, callback: OSCButtonCallback) -> OSCAction:
        action = OSCAction(len(self.actions), name, callback)
        self.actions.append(action)
        self.actions_by_name[name] = action
        return action

class OSCButtonBindings:
    def __init__(self):
        self.bindings: dict[OSCButton, OSCAction] = {}

    def bind(self, button: OSCButton, action: OSCAction):
        self.bindings[button] = action

    def unbind(self, button: OSCButton):
        del self.bindings[button]

    async def handle(self, button: OSCButton, *args: Any):
        action = self.bindings.get(button)
        if action:
            await action.handle(*args)
