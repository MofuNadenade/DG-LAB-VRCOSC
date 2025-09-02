"""
OSC地址管理模块

提供OSC地址的定义和注册管理功能。
"""

import logging
from typing import Optional, List, Dict

from models import OSCAddressDict
from .osc_common import OSCAddress, AddressCallback

logger = logging.getLogger(__name__)


class OSCAddressRegistry:
    """OSC地址注册表"""

    def __init__(self) -> None:
        super().__init__()
        self._addresses: List[OSCAddress] = []
        self._addresses_by_name: Dict[str, OSCAddress] = {}
        self._addresses_by_code: Dict[str, OSCAddress] = {}
        self._addresses_by_id: Dict[int, OSCAddress] = {}  # 按ID索引
        self._next_address_id: int = 1
        self._address_added_callbacks: List[AddressCallback] = []
        self._address_removed_callbacks: List[AddressCallback] = []

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

    @property
    def addresses_by_id(self) -> Dict[int, OSCAddress]:
        """获取按ID索引的地址字典（只读）"""
        return self._addresses_by_id.copy()

    def get_address_by_name(self, name: str) -> Optional[OSCAddress]:
        """根据名称获取地址"""
        return self._addresses_by_name.get(name)

    def get_address_by_code(self, code: str) -> Optional[OSCAddress]:
        """根据代码获取地址"""
        return self._addresses_by_code.get(code)

    def get_address_by_id(self, address_id: int) -> Optional[OSCAddress]:
        """根据ID获取地址"""
        return self._addresses_by_id.get(address_id)

    def has_address_name(self, name: str) -> bool:
        """检查是否存在指定名称的地址"""
        return name in self._addresses_by_name

    def has_address_code(self, code: str) -> bool:
        """检查是否存在指定代码的地址"""
        return code in self._addresses_by_code

    def has_address_id(self, address_id: int) -> bool:
        """检查是否存在指定ID的地址"""
        return address_id in self._addresses_by_id

    def get_address_count(self) -> int:
        """获取地址总数"""
        return len(self._addresses)

    def _get_next_address_id(self) -> int:
        """获取下一个可用的地址ID"""
        current_id = self._next_address_id
        self._next_address_id += 1
        return current_id

    def add_address_added_callback(self, callback: AddressCallback) -> None:
        if callback not in self._address_added_callbacks:
            self._address_added_callbacks.append(callback)

    def remove_address_added_callback(self, callback: AddressCallback) -> None:
        if callback in self._address_added_callbacks:
            self._address_added_callbacks.remove(callback)

    def add_address_removed_callback(self, callback: AddressCallback) -> None:
        if callback not in self._address_removed_callbacks:
            self._address_removed_callbacks.append(callback)

    def remove_address_removed_callback(self, callback: AddressCallback) -> None:
        if callback in self._address_removed_callbacks:
            self._address_removed_callbacks.remove(callback)

    def notify_address_added(self, address: OSCAddress) -> None:
        for callback in self._address_added_callbacks:
            callback(address)

    def notify_address_removed(self, address: OSCAddress) -> None:
        for callback in self._address_removed_callbacks:
            callback(address)

    def register_address(self, name: str, code: str) -> OSCAddress:
        """注册地址"""
        address_id = self._get_next_address_id()
        address = OSCAddress(address_id, name, code)
        self._addresses.append(address)
        self._addresses_by_name[name] = address
        self._addresses_by_code[code] = address
        self._addresses_by_id[address_id] = address

        # 通知观察者
        self.notify_address_added(address)

        return address

    def unregister_address(self, address_id: int) -> bool:
        """通过ID注销地址
        
        Args:
            address_id: 要注销的地址ID
            
        Returns:
            bool: 注销成功返回True，如果ID不存在返回False
        """
        address = self._addresses_by_id.get(address_id)
        if not address:
            return False
            
        # 从所有索引中移除
        self._addresses.remove(address)
        self._addresses_by_name.pop(address.name, None)
        self._addresses_by_code.pop(address.code, None)
        self._addresses_by_id.pop(address_id, None)
        
        # 通知观察者
        self.notify_address_removed(address)
        
        return True

    def unregister_address_by_instance(self, address: OSCAddress) -> bool:
        """通过地址实例来注销地址
        
        Args:
            address: 要注销的地址实例
            
        Returns:
            bool: 注销成功返回True，如果地址不存在返回False
        """
        return self.unregister_address(address.id)

    def clear_addresses(self) -> None:
        """清空所有地址"""
        self._addresses.clear()
        self._addresses_by_name.clear()
        self._addresses_by_code.clear()
        self._addresses_by_id.clear()

    def load_from_config(self, addresses_config: List['OSCAddressDict']) -> None:
        """从配置加载地址"""
        self.clear_addresses()

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

    def update_address_name(self, address_id: int, new_name: str) -> bool:
        """通过ID更新地址名称
        
        Args:
            address_id: 要更新的地址ID
            new_name: 新的地址名称
            
        Returns:
            bool: 更新成功返回True，如果ID不存在返回False
        """
        address = self._addresses_by_id.get(address_id)
        if not address:
            return False
            
        old_name = address.name
        address.name = new_name.strip()
        
        # 更新名称索引
        self._addresses_by_name.pop(old_name, None)
        self._addresses_by_name[address.name] = address
        
        return True

    def update_address_code(self, address_id: int, new_code: str) -> bool:
        """通过ID更新地址代码
        
        Args:
            address_id: 要更新的地址ID
            new_code: 新的地址代码
            
        Returns:
            bool: 更新成功返回True，如果ID不存在返回False
        """
        address = self._addresses_by_id.get(address_id)
        if not address:
            return False
            
        old_code = address.code
        address.code = new_code.strip()
        
        # 更新代码索引
        self._addresses_by_code.pop(old_code, None)
        self._addresses_by_code[address.code] = address
        
        return True
