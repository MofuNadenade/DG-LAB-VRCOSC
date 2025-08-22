"""
OSC地址管理模块

提供OSC地址的定义和注册管理功能。
"""

import logging
from typing import Any, Optional, List, Dict

from .osc_common import OSCAddressValidator, OSCRegistryObserver
from .defaults import DEFAULT_ADDRESSES

logger = logging.getLogger(__name__)


class OSCAddress:
    """OSC地址"""
    
    def __init__(self, name: str, index: int, code: str) -> None:
        # 验证输入
        name_valid, name_error = OSCAddressValidator.validate_address_name(name)
        if not name_valid:
            raise ValueError(f"无效的地址名称: {name_error}")
            
        code_valid, code_error = OSCAddressValidator.validate_osc_code(code)
        if not code_valid:
            raise ValueError(f"无效的OSC代码: {code_error}")
            
        self.name: str = name.strip()
        self.index: int = index
        self.code: str = code.strip()
    
    def __str__(self) -> str:
        return f"OSCAddress(name='{self.name}', code='{self.code}')"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OSCAddress):
            return False
        return self.name == other.name and self.code == other.code
    
    def __hash__(self) -> int:
        return hash((self.name, self.code))


class OSCAddressRegistry:
    """OSC地址注册表"""
    
    def __init__(self) -> None:
        self.addresses: List[OSCAddress] = []
        self.addresses_by_name: Dict[str, OSCAddress] = {}
        self.addresses_by_code: Dict[str, OSCAddress] = {}
        self.observers: List[OSCRegistryObserver] = []

    def add_observer(self, observer: OSCRegistryObserver) -> None:
        """添加观察者"""
        if observer not in self.observers:
            self.observers.append(observer)
    
    def remove_observer(self, observer: OSCRegistryObserver) -> None:
        """移除观察者"""
        if observer in self.observers:
            self.observers.remove(observer)
    
    def notify_address_added(self, address: OSCAddress) -> None:
        """通知观察者地址已添加"""
        for observer in self.observers:
            observer.on_address_added(address)
    
    def notify_address_removed(self, address: OSCAddress) -> None:
        """通知观察者地址已移除"""
        for observer in self.observers:
            observer.on_address_removed(address)

    def register_address(self, name: str, code: str) -> OSCAddress:
        """注册地址"""
        address = OSCAddress(name, len(self.addresses), code)
        self.addresses.append(address)
        self.addresses_by_name[name] = address
        self.addresses_by_code[code] = address
        
        # 通知观察者
        self.notify_address_added(address)
        
        return address
    

    
    def unregister_address(self, address: OSCAddress) -> None:
        """移除地址"""
        if address in self.addresses:
            self.addresses.remove(address)
            del self.addresses_by_name[address.name]
            del self.addresses_by_code[address.code]
            
            # 重新索引
            for i, a in enumerate(self.addresses):
                a.index = i
            
            # 通知观察者
            self.notify_address_removed(address)
    
    def load_from_config(self, addresses_config: List[Dict[str, str]]) -> None:
        """从配置加载地址"""
        self.addresses.clear()
        self.addresses_by_name.clear()
        self.addresses_by_code.clear()
        
        for addr_config in addresses_config:
            try:
                name = addr_config.get('name', '')
                code = addr_config.get('code', '')
                if name and code:
                    self.register_address(name, code)
                    logger.debug(f"Loaded address: {name} -> {code}")
            except Exception as e:
                logger.error(f"Failed to load address: {e}")
        
        logger.info(f"Loaded {len(self.addresses)} addresses from config")
    
    def export_to_config(self) -> List[Dict[str, str]]:
        """导出所有地址到配置格式"""
        return [{'name': addr.name, 'code': addr.code} for addr in self.addresses]
    



