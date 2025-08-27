"""
OSC地址管理模块

提供OSC地址的定义和注册管理功能。
"""

import logging
from typing import Optional, List, Dict

from models import OSCAddressDict
from .osc_common import OSCAddress, OSCRegistryObserver

logger = logging.getLogger(__name__)


class OSCAddressRegistry:
    """OSC地址注册表"""

    def __init__(self) -> None:
        super().__init__()
        self._addresses: List[OSCAddress] = []
        self._addresses_by_name: Dict[str, OSCAddress] = {}
        self._addresses_by_code: Dict[str, OSCAddress] = {}
        self._observers: List[OSCRegistryObserver] = []

    @property
    def addresses(self) -> List[OSCAddress]:
        """获取所有地址列表（只读）"""
        return self._addresses.copy()

    @property
    def addresses_by_name(self) -> Dict[str, OSCAddress]:
        """获取按名称索引的地址字典（只读）"""
        return self._addresses_by_name.copy()

    @property
    def addresses_by_code(self) -> Dict[str, OSCAddress]:
        """获取按代码索引的地址字典（只读）"""
        return self._addresses_by_code.copy()

    def get_address_by_name(self, name: str) -> Optional[OSCAddress]:
        """根据名称获取地址"""
        return self._addresses_by_name.get(name)

    def get_address_by_code(self, code: str) -> Optional[OSCAddress]:
        """根据代码获取地址"""
        return self._addresses_by_code.get(code)

    def has_address_name(self, name: str) -> bool:
        """检查是否存在指定名称的地址"""
        return name in self._addresses_by_name

    def has_address_code(self, code: str) -> bool:
        """检查是否存在指定代码的地址"""
        return code in self._addresses_by_code

    def get_address_count(self) -> int:
        """获取地址总数"""
        return len(self._addresses)

    def add_observer(self, observer: OSCRegistryObserver) -> None:
        """添加观察者"""
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: OSCRegistryObserver) -> None:
        """移除观察者"""
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_address_added(self, address: OSCAddress) -> None:
        """通知观察者地址已添加"""
        for observer in self._observers:
            observer.on_address_added(address)

    def notify_address_removed(self, address: OSCAddress) -> None:
        """通知观察者地址已移除"""
        for observer in self._observers:
            observer.on_address_removed(address)

    def register_address(self, name: str, code: str) -> OSCAddress:
        """注册地址"""
        address = OSCAddress(name, code)
        self._addresses.append(address)
        self._addresses_by_name[name] = address
        self._addresses_by_code[code] = address

        # 通知观察者
        self.notify_address_added(address)

        return address

    def unregister_address(self, address: OSCAddress) -> None:
        """移除地址"""
        if address in self._addresses:
            self._addresses.remove(address)
            del self._addresses_by_name[address.name]
            del self._addresses_by_code[address.code]

            # 通知观察者
            self.notify_address_removed(address)

    def clear_addresses(self) -> None:
        """清空所有地址"""
        self._addresses.clear()
        self._addresses_by_name.clear()
        self._addresses_by_code.clear()

    def load_from_config(self, addresses_config: List['OSCAddressDict']) -> None:
        """从配置加载地址"""
        self._addresses.clear()
        self._addresses_by_name.clear()
        self._addresses_by_code.clear()

        for addr_config in addresses_config:
            try:
                name = addr_config.get('name', '')
                code = addr_config.get('code', '')
                if name and code:
                    self.register_address(name, code)
                    logger.debug(f"Loaded address: {name} -> {code}")
            except Exception as e:
                logger.error(f"Failed to load address: {e}")

        logger.info(f"Loaded {len(self._addresses)} addresses from config")

    def export_to_config(self) -> List[OSCAddressDict]:
        """导出所有地址到配置格式"""
        return [{'name': addr.name, 'code': addr.code} for addr in self._addresses]
