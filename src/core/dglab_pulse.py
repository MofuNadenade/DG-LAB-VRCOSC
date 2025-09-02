import logging
from typing import Dict, List, Optional

from core.osc_common import OSCRegistryObserver, Pulse
from models import PulseOperation

logger = logging.getLogger(__name__)


class PulseRegistry:
    def __init__(self) -> None:
        super().__init__()
        self._pulses: List[Pulse] = []
        self._pulses_by_name: Dict[str, Pulse] = {}
        self._pulses_by_id: Dict[int, Pulse] = {}
        self._observers: List[OSCRegistryObserver] = []

    @property
    def pulses(self) -> List[Pulse]:
        """获取所有波形列表（只读）"""
        return self._pulses.copy()

    @property
    def pulses_by_name(self) -> Dict[str, Pulse]:
        """获取按名称索引的波形字典（只读）"""
        return self._pulses_by_name.copy()

    @property
    def pulses_by_id(self) -> Dict[int, Pulse]:
        """获取按ID索引的波形字典（只读）"""
        return self._pulses_by_id.copy()

    def get_pulse_by_name(self, name: str) -> Optional[Pulse]:
        """根据名称获取波形
        
        Args:
            name: 波形名称
            
        Returns:
            Optional[Pulse]: 找到的波形实例，如果不存在返回None
        """
        return self._pulses_by_name.get(name)

    def get_pulse_by_id(self, pulse_id: int) -> Optional[Pulse]:
        """根据ID获取波形
        
        Args:
            pulse_id: 波形ID
            
        Returns:
            Optional[Pulse]: 找到的波形实例，如果不存在返回None
        """
        return self._pulses_by_id.get(pulse_id)

    def has_pulse_name(self, name: str) -> bool:
        """检查是否存在指定名称的波形
        
        Args:
            name: 波形名称
            
        Returns:
            bool: 存在返回True，否则返回False
        """
        return name in self._pulses_by_name

    def has_pulse_id(self, pulse_id: int) -> bool:
        """检查是否存在指定ID的波形
        
        Args:
            pulse_id: 波形ID
            
        Returns:
            bool: 存在返回True，否则返回False
        """
        return pulse_id in self._pulses_by_id

    def get_pulse_count(self) -> int:
        """获取波形总数
        
        Returns:
            int: 当前注册的波形数量
        """
        return len(self._pulses)

    def is_valid_id(self, pulse_id: int) -> bool:
        """检查波形ID是否有效
        
        Args:
            pulse_id: 要检查的波形ID
            
        Returns:
            bool: ID有效返回True，否则返回False
        """
        return pulse_id in self._pulses_by_id

    def add_observer(self, observer: OSCRegistryObserver) -> None:
        """添加观察者
        
        Args:
            observer: 要添加的观察者实例
        """
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: OSCRegistryObserver) -> None:
        """移除观察者
        
        Args:
            observer: 要移除的观察者实例
        """
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_pulse_added(self, pulse: Pulse) -> None:
        """通知观察者波形已添加
        
        Args:
            pulse: 新添加的波形实例
        """
        for observer in self._observers:
            observer.on_pulse_added(pulse)

    def notify_pulse_removed(self, pulse: Pulse) -> None:
        """通知观察者波形已移除
        
        Args:
            pulse: 被移除的波形实例
        """
        for observer in self._observers:
            observer.on_pulse_removed(pulse)

    def register_pulse(self, name: str, data: List[PulseOperation]) -> Pulse:
        """注册波形
        
        Args:
            name: 波形名称
            data: 波形操作数据列表
            
        Returns:
            Pulse: 注册的波形实例
        """
        pulse = Pulse(len(self._pulses), name, data)
        self._pulses.append(pulse)
        self._pulses_by_name[pulse.name] = pulse
        self._pulses_by_id[pulse.id] = pulse

        # 通知观察者
        self.notify_pulse_added(pulse)

        return pulse

    def unregister_pulse(self, pulse_id: int) -> bool:
        """通过ID注销波形
        
        Args:
            pulse_id: 要注销的波形ID
            
        Returns:
            bool: 注销成功返回True，如果ID不存在返回False
        """
        pulse = self._pulses_by_id.get(pulse_id)
        if not pulse:
            return False
            
        # 从所有索引中移除
        self._pulses.remove(pulse)
        self._pulses_by_name.pop(pulse.name, None)
        self._pulses_by_id.pop(pulse_id, None)
        
        # 通知观察者
        self.notify_pulse_removed(pulse)
        
        return True

    def unregister_pulse_by_instance(self, pulse: Pulse) -> bool:
        """通过波形实例来注销波形
        
        Args:
            pulse: 要注销的波形实例
            
        Returns:
            bool: 注销成功返回True，如果波形不存在返回False
        """
        return self.unregister_pulse(pulse.id)

    def load_from_config(self, pulses_config: Dict[str, List[PulseOperation]]) -> None:
        """从配置加载波形
        
        Args:
            pulses_config: 波形配置字典，键为波形名称，值为波形操作数据列表
        """
        self._pulses.clear()
        self._pulses_by_name.clear()
        self._pulses_by_id.clear()

        for name, data in pulses_config.items():
            try:
                self.register_pulse(name, data)
                logger.debug(f"Loaded pulse: {name}")
            except Exception as e:
                logger.error(f"Failed to load pulse {name}: {e}")

        logger.info(f"Loaded {len(self._pulses)} pulses from config")

    def export_to_config(self) -> Dict[str, List[PulseOperation]]:
        """导出所有波形到配置格式
        
        Returns:
            Dict[str, List[PulseOperation]]: 波形配置字典，键为波形名称，值为波形操作数据列表
        """
        return {pulse.name: list(pulse.data) for pulse in self._pulses}
