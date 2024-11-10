
import enum
from typing import Any, Coroutine, Protocol

import logging
logger = logging.getLogger(__name__)

class OSCParameter:
    def __init__(self, name: str, index: int, code: str):
        self.name = name
        self.index = index
        self.code = code

class OSCParameterRegistry:
    def __init__(self):
        self.parameters: list[OSCParameter] = []
        self.parameters_by_name: dict[str, OSCParameter] = {}
        self.parameters_by_code: dict[str, OSCParameter] = {}

        self.register_default_parameters()

    def register_parameter(self, name: str, code: str) -> OSCParameter:
        parameter = OSCParameter(name, len(self.parameters), code)
        self.parameters.append(parameter)
        self.parameters_by_name[name] = parameter
        self.parameters_by_code[code] = parameter
        return parameter

    def register_default_parameters(self):
        self.register_parameter("碰左小腿", "DG-LAB/UpperLeg_R")
        self.register_parameter("碰右小腿", "DG-LAB/UpperLeg_R")
        self.register_parameter("拉尾巴", "DG-LAB/Tail_Stretch")

        self.register_parameter("按钮面板控制", "SoundPad/PanelControl")
        self.register_parameter("按钮数值调节", "SoundPad/Volume")
        self.register_parameter("按钮通道调节", "SoundPad/Page")

        self.register_parameter("按钮1", "SoundPad/Button/1")
        self.register_parameter("按钮2", "SoundPad/Button/2")
        self.register_parameter("按钮3", "SoundPad/Button/3")
        self.register_parameter("按钮4", "SoundPad/Button/4")
        self.register_parameter("按钮5", "SoundPad/Button/5")
        self.register_parameter("按钮6", "SoundPad/Button/6")
        self.register_parameter("按钮7", "SoundPad/Button/7")
        self.register_parameter("按钮8", "SoundPad/Button/8")
        self.register_parameter("按钮9", "SoundPad/Button/9")
        self.register_parameter("按钮10", "SoundPad/Button/10")
        self.register_parameter("按钮11", "SoundPad/Button/11")
        self.register_parameter("按钮12", "SoundPad/Button/12")
        self.register_parameter("按钮13", "SoundPad/Button/13")
        self.register_parameter("按钮14", "SoundPad/Button/14")
        self.register_parameter("按钮15", "SoundPad/Button/15")

class OSCParameterCallback(Protocol):
    def __call__(self, *args: Any) -> Coroutine[Any, Any, Any]:
        ...

class OSCAction:
    def __init__(self, index: int, name: str, callback: OSCParameterCallback):
        self.index = index
        self.name = name
        self.callback = callback
    
    async def handle(self, *args: Any):
        await self.callback(*args)

class OSCActionRegistry:
    def __init__(self):
        self.actions: list[OSCAction] = []
        self.actions_by_name: dict[str, OSCAction] = {}

    def register_action(self, name: str, callback: OSCParameterCallback) -> OSCAction:
        action = OSCAction(len(self.actions), name, callback)
        self.actions.append(action)
        self.actions_by_name[name] = action
        return action

class OSCParameterBindings:
    def __init__(self):
        self.bindings: dict[OSCParameter, OSCAction] = {}

    def bind(self, parameter: OSCParameter, action: OSCAction):
        self.bindings[parameter] = action

    def unbind(self, parameter: OSCParameter):
        del self.bindings[parameter]

    async def handle(self, parameter: OSCParameter, *args: Any):
        action = self.bindings.get(parameter)
        if action:
            await action.handle(*args)
