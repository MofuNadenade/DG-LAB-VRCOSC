"""
OSC地址管理模块

提供OSC地址的定义和注册管理功能。
"""

import logging
from typing import Any, Optional, List, Dict

from .osc_common import OSCAddressValidator, OSCRegistryObserver

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
        self._custom_addresses: List[OSCAddress] = []  # 存储自定义地址

        self.register_default_addresses()

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
    
    def register_custom_address(self, name: str, code: str) -> OSCAddress:
        """注册自定义地址（用于UI添加的地址）"""
        address = self.register_address(name, code)
        self._custom_addresses.append(address)
        return address
    
    def remove_address(self, address: OSCAddress) -> None:
        """移除地址"""
        if address in self.addresses:
            self.addresses.remove(address)
            del self.addresses_by_name[address.name]
            del self.addresses_by_code[address.code]
            
            # 从自定义地址列表中移除
            if address in self._custom_addresses:
                self._custom_addresses.remove(address)
            
            # 重新索引
            for i, a in enumerate(self.addresses):
                a.index = i
            
            # 通知观察者
            self.notify_address_removed(address)
    
    def load_custom_addresses(self, custom_addresses_config: List[Dict[str, str]]) -> None:
        """从配置加载自定义地址"""
        for addr_config in custom_addresses_config:
            try:
                name = addr_config.get('name', '')
                code = addr_config.get('code', '')
                if name and code:
                    # 检查是否已存在
                    if name not in self.addresses_by_name and code not in self.addresses_by_code:
                        self.register_custom_address(name, code)
                        logger.info(f"Loaded custom address: {name} -> {code}")
                    else:
                        logger.warning(f"Custom address already exists: {name} -> {code}")
            except Exception as e:
                logger.error(f"Failed to load custom address: {e}")
    
    def export_custom_addresses(self) -> List[Dict[str, str]]:
        """导出自定义地址到配置格式"""
        custom_addrs = []
        for addr in self._custom_addresses:
            custom_addrs.append({
                'name': addr.name,
                'code': addr.code
            })
        return custom_addrs
    
    def get_custom_addresses(self) -> List[OSCAddress]:
        """获取所有自定义地址"""
        return self._custom_addresses.copy()

    def register_default_addresses(self) -> None:
        """注册默认地址"""
        # VRChat Avatar地址（完整OSC路径）
        self.register_address("碰左小腿", "/avatar/parameters/DG-LAB/UpperLeg_L")
        self.register_address("碰右小腿", "/avatar/parameters/DG-LAB/UpperLeg_R")
        self.register_address("拉尾巴", "/avatar/parameters/DG-LAB/Tail_Stretch")

        # SoundPad地址（完整OSC路径）
        self.register_address("按钮面板控制", "/avatar/parameters/SoundPad/PanelControl")
        self.register_address("按钮数值调节", "/avatar/parameters/SoundPad/Volume")
        self.register_address("按钮通道调节", "/avatar/parameters/SoundPad/Page")

        # SoundPad按钮1-15（完整OSC路径）
        for i in range(1, 16):
            self.register_address(f"按钮{i}", f"/avatar/parameters/SoundPad/Button/{i}")
