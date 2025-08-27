"""
OSC核心模块

按功能拆分的OSC系统模块集合。
"""

from .dglab_controller import DGLabController
# DGLab 相关
from .dglab_pulse import Pulse, PulseRegistry
# 动作管理
from .osc_action import OSCActionRegistry, OSCActionCallback
# 地址管理
from .osc_address import OSCAddressRegistry
# 绑定管理
from .osc_binding import OSCBindingRegistry
# 通用类型和枚举
from .osc_common import OSCAction, OSCAddress, OSCActionType, OSCRegistryObserver, OSCAddressValidator
# 选项提供
from .osc_provider import OSCOptionsProvider
# 模板管理
from .osc_template import OSCTemplate, OSCTemplateRegistry

__all__ = [
    # 通用
    'OSCAction',
    'OSCAddress',
    'OSCActionType',
    'OSCRegistryObserver',
    'OSCAddressValidator',

    # 地址
    'OSCAddressRegistry',

    # 动作
    'OSCActionRegistry',
    'OSCActionCallback',

    # 模板
    'OSCTemplate',
    'OSCTemplateRegistry',

    # 绑定
    'OSCBindingRegistry',

    # 提供者
    'OSCOptionsProvider',

    # DGLab
    'Pulse',
    'PulseRegistry',
    'DGLabController',
]
