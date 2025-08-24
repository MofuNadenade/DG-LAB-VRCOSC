"""
OSC模板管理模块

提供OSC代码模板和绑定模板的管理功能。
"""

import logging
from typing import Optional, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from models import OSCTemplateDict

logger = logging.getLogger(__name__)


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
        self._templates: List[OSCTemplate] = []
        self._templates_by_name: Dict[str, OSCTemplate] = {}
    
    @property
    def templates(self) -> List[OSCTemplate]:
        """获取所有模板列表（只读）"""
        return self._templates.copy()
    
    @property
    def templates_by_name(self) -> Dict[str, OSCTemplate]:
        """获取按名称索引的模板字典（只读）"""
        return self._templates_by_name.copy()
    
    def get_template_count(self) -> int:
        """获取模板总数"""
        return len(self._templates)

    def register_template(self, name: str, code: str, description: str = "") -> OSCTemplate:
        """注册模板"""
        template = OSCTemplate(name, code, description)
        self._templates.append(template)
        self._templates_by_name[name] = template
        return template
    
    def get_template_options(self) -> List[str]:
        """获取所有模板选项"""
        return [template.code for template in self._templates]
    
    def get_template_by_name(self, name: str) -> Optional[OSCTemplate]:
        """根据名称获取模板"""
        return self._templates_by_name.get(name)
    
    def get_templates_by_prefix(self, prefix: str) -> List[OSCTemplate]:
        """根据前缀获取模板"""
        return [t for t in self._templates if t.code.startswith(prefix)]
    
    def load_from_config(self, templates_config: List['OSCTemplateDict']) -> None:
        """从配置加载模板"""
        self._templates.clear()
        self._templates_by_name.clear()
        
        for template_config in templates_config:
            try:
                name = template_config.get('name', '')
                pattern = template_config.get('pattern', '')
                description = template_config.get('description', '')
                if name and pattern:
                    self.register_template(name, pattern, description)
                    logger.debug(f"Loaded template: {name}")
            except Exception as e:
                logger.error(f"Failed to load template: {e}")
        
        logger.info(f"Loaded {len(self._templates)} templates from config")
    
    def export_to_config(self) -> List[Dict[str, str]]:
        """导出所有模板到配置格式"""
        return [{
            'name': template.name,
            'pattern': template.code,
            'description': template.description
        } for template in self._templates]



