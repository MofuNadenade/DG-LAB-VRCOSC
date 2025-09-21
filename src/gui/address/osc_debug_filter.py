"""
OSC调试显示过滤器模块
"""
import re
import logging
from typing import Optional, Pattern

from models import OSCDebugFilterMode

logger = logging.getLogger(__name__)


class OSCDebugFilter:
    """OSC调试显示过滤器"""
    
    def __init__(self) -> None:
        super().__init__()
        self.enabled: bool = False
        self.filter_text: str = ""
        self.filter_mode: OSCDebugFilterMode = OSCDebugFilterMode.PARTIAL_MATCH
        self.case_sensitive: bool = False
        self._compiled_regex: Optional[Pattern[str]] = None
        self._regex_error: Optional[str] = None
    
    def set_filter_text(self, text: str) -> bool:
        """设置过滤文本，返回是否有效"""
        self.filter_text = text.strip()
        
        # 如果是正则表达式模式，预编译正则
        if self.filter_mode == OSCDebugFilterMode.REGEX:
            return self._compile_regex()
        
        return True
    
    def set_filter_mode(self, mode: OSCDebugFilterMode) -> bool:
        """设置过滤模式，返回是否有效"""
        self.filter_mode = mode
        
        # 如果切换到正则模式，需要重新编译
        if mode == OSCDebugFilterMode.REGEX:
            return self._compile_regex()
        
        self._compiled_regex = None
        self._regex_error = None
        return True
    
    def set_case_sensitive(self, sensitive: bool) -> None:
        """设置大小写敏感"""
        if self.case_sensitive != sensitive:
            self.case_sensitive = sensitive
            # 如果是正则模式，需要重新编译
            if self.filter_mode == OSCDebugFilterMode.REGEX:
                self._compile_regex()
    
    def _compile_regex(self) -> bool:
        """编译正则表达式"""
        if not self.filter_text:
            self._compiled_regex = None
            self._regex_error = None
            return True
            
        try:
            flags = 0 if self.case_sensitive else re.IGNORECASE
            self._compiled_regex = re.compile(self.filter_text, flags)
            self._regex_error = None
            return True
        except re.error as e:
            self._compiled_regex = None
            self._regex_error = str(e)
            logger.warning(f"正则表达式编译失败: {e}")
            return False
    
    def matches(self, address: str) -> bool:
        """检查地址是否匹配过滤条件"""
        if not self.enabled or not self.filter_text:
            return True
        
        if self.filter_mode == OSCDebugFilterMode.PARTIAL_MATCH:
            if self.case_sensitive:
                return self.filter_text in address
            else:
                return self.filter_text.lower() in address.lower()
                
        elif self.filter_mode == OSCDebugFilterMode.REGEX:
            if self._compiled_regex is None:
                return True  # 正则无效时显示所有项
            try:
                return bool(self._compiled_regex.search(address))
            except Exception as e:
                logger.error(f"正则匹配失败: {e}")
                return True
        
        return True
    
    def get_regex_error(self) -> Optional[str]:
        """获取正则表达式错误信息"""
        return self._regex_error
    
    def is_valid(self) -> bool:
        """检查过滤器配置是否有效"""
        if not self.enabled or not self.filter_text:
            return True
        
        if self.filter_mode == OSCDebugFilterMode.REGEX:
            return self._regex_error is None
        
        return True
