"""
OSC核心模块

按功能拆分的OSC系统模块集合。
"""

# 通用类型和枚举
from .osc_common import OSCActionType, OSCAddressCallback, OSCRegistryObserver, OSCAddressValidator

# 地址管理
from .osc_address import OSCAddress, OSCAddressRegistry

# 动作管理  
from .osc_action import OSCAction, OSCActionRegistry

# 模板管理
from .osc_template import OSCTemplate, OSCTemplateRegistry, OSCBindingTemplate, OSCBindingTemplateRegistry

# 绑定管理
from .osc_binding import OSCBindingRegistry

# 选项提供
from .osc_provider import OSCOptionsProvider

# DGLab 相关
from .dglab_pulse import Pulse, PulseRegistry
from .dglab_controller import DGLabController, run_server

__all__ = [
    # 通用
    'OSCActionType',
    'OSCAddressCallback', 
    'OSCRegistryObserver',
    'OSCAddressValidator',
    
    # 地址
    'OSCAddress',
    'OSCAddressRegistry',
    
    # 动作
    'OSCAction', 
    'OSCActionRegistry',
    
    # 模板
    'OSCTemplate',
    'OSCTemplateRegistry',
    'OSCBindingTemplate',
    'OSCBindingTemplateRegistry',
    
    # 绑定
    'OSCBindingRegistry',
    
    # 提供者
    'OSCOptionsProvider',
    
    # DGLab
    'Pulse',
    'PulseRegistry',
    'DGLabController',
    'run_server',
]
