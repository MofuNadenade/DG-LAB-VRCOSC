"""
OSC模板管理模块

提供OSC代码模板和绑定模板的管理功能。
"""

from typing import Optional, List, Dict


class OSCTemplate:
    """OSC代码模板"""
    
    def __init__(self, name: str, code: str, description: str = "") -> None:
        self.name: str = name
        self.code: str = code
        self.description: str = description
    
    def __str__(self) -> str:
        return f"OSCTemplate(name='{self.name}', code='{self.code}')"
    
    def __repr__(self) -> str:
        return self.__str__()


class OSCTemplateRegistry:
    """OSC代码模板注册表"""
    
    def __init__(self) -> None:
        self.templates: List[OSCTemplate] = []
        self.templates_by_name: Dict[str, OSCTemplate] = {}
        self.register_default_templates()
    
    def register_template(self, name: str, code: str, description: str = "") -> OSCTemplate:
        """注册模板"""
        template = OSCTemplate(name, code, description)
        self.templates.append(template)
        self.templates_by_name[name] = template
        return template
    
    def get_template_options(self) -> List[str]:
        """获取所有模板选项"""
        return [template.code for template in self.templates]
    
    def get_template_by_name(self, name: str) -> Optional[OSCTemplate]:
        """根据名称获取模板"""
        return self.templates_by_name.get(name)
    
    def get_templates_by_prefix(self, prefix: str) -> List[OSCTemplate]:
        """根据前缀获取模板"""
        return [t for t in self.templates if t.code.startswith(prefix)]
    
    def register_default_templates(self) -> None:
        """注册默认模板"""
        # VRChat OSC路径模板
        self.register_template("Avatar参数地址", "/avatar/parameters/", "VRChat Avatar参数地址路径")
        self.register_template("输入地址", "/input/", "输入控制地址路径")
        self.register_template("Chatbox地址", "/chatbox/", "聊天框地址路径")
        self.register_template("追踪地址", "/tracking/", "追踪数据地址路径")
        
        # 常用完整路径示例
        self.register_template("DG-LAB触碰", "/avatar/parameters/DG-LAB/", "DG-LAB触碰地址前缀")
        self.register_template("SoundPad按钮", "/avatar/parameters/SoundPad/Button/", "SoundPad按钮地址前缀")
        
        # 游戏集成模板
        self.register_template("游戏伤害事件", "/game/damage", "游戏伤害事件地址")
        self.register_template("游戏状态变化", "/game/state", "游戏状态变化地址")
        self.register_template("游戏触发器", "/game/trigger", "游戏触发器地址")


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


class OSCBindingTemplateRegistry:
    """OSC绑定模板注册表"""
    
    def __init__(self) -> None:
        self.binding_templates: List[OSCBindingTemplate] = []
        self.binding_templates_by_address: Dict[str, OSCBindingTemplate] = {}
        self.register_binding_templates()
    
    def register_binding(self, address_name: str, action_name: str) -> OSCBindingTemplate:
        """注册绑定模板"""
        binding = OSCBindingTemplate(address_name, action_name)
        self.binding_templates.append(binding)
        self.binding_templates_by_address[address_name] = binding
        return binding
    
    def get_binding_templates(self) -> List[Dict[str, str]]:
        """获取所有绑定模板的字典格式"""
        return [binding.to_dict() for binding in self.binding_templates]
    
    def is_binding_template(self, binding: Dict[str, str]) -> bool:
        """检查是否为绑定模板"""
        return any(binding_template == binding for binding_template in self.binding_templates)
    
    def filter_non_binding_templates(self, bindings: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """过滤掉绑定模板，只返回用户自定义的绑定"""
        return [binding for binding in bindings if not self.is_binding_template(binding)]
    
    def register_binding_templates(self) -> None:
        """注册所有绑定模板"""
        # VRChat触碰相关
        self.register_binding('碰左小腿', 'A通道触碰')
        self.register_binding('碰右小腿', 'B通道触碰')
        self.register_binding('拉尾巴', '当前通道触碰')
        
        # SoundPad控制相关
        self.register_binding('按钮面板控制', '面板控制')
        self.register_binding('按钮数值调节', '数值调节')
        self.register_binding('按钮通道调节', '通道调节')
        
        # SoundPad按钮1-15
        self.register_binding('按钮1', '设置模式')
        self.register_binding('按钮2', '重置强度')
        self.register_binding('按钮3', '降低强度')
        self.register_binding('按钮4', '增加强度')
        self.register_binding('按钮5', '一键开火')
        self.register_binding('按钮6', 'ChatBox状态开关')
        self.register_binding('按钮7', '设置波形为(连击)')
        self.register_binding('按钮8', '设置波形为(挑逗1)')
        self.register_binding('按钮9', '设置波形为(按捏渐强)')
        self.register_binding('按钮10', '设置波形为(心跳节奏)')
        self.register_binding('按钮11', '设置波形为(压缩)')
        self.register_binding('按钮12', '设置波形为(节奏步伐)')
        self.register_binding('按钮13', '设置波形为(颗粒摩擦)')
        self.register_binding('按钮14', '设置波形为(渐变弹跳)')
        self.register_binding('按钮15', '设置波形为(潮汐)')
