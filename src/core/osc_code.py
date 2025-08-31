"""
OSC地址代码管理模块

提供OSC地址代码的定义和注册管理功能。
"""
import logging
from typing import List

logger = logging.getLogger(__name__)


class OSCCodeRegistry:
    """OSC地址代码注册表"""

    def __init__(self) -> None:
        super().__init__()
        self._codes: List[str] = []

    @property
    def codes(self) -> List[str]:
        """获取所有地址代码列表（只读）"""
        return self._codes.copy()

    def get_code_count(self) -> int:
        """获取地址代码总数"""
        return len(self._codes)

    def has_code(self, code: str) -> bool:
        """检查是否存在指定代码"""
        return code in self._codes

    def register_code(self, code: str) -> None:
        """注册地址代码"""
        if code in self._codes:
            logger.warning(f"地址代码 {code} 已存在")
            return
        self._codes.append(code)
        logger.info(f"注册地址代码: {code}")

    def unregister_code(self, code: str) -> None:
        """取消注册地址代码"""
        if code in self._codes:
            self._codes.remove(code)
            logger.info(f"取消注册地址代码: {code}")
        else:
            logger.warning(f"地址代码 {code} 不存在")
