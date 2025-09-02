import logging
from typing import Dict, List, Optional

from core.osc_common import Pulse, PulseCallback
from models import PulseOperation

logger = logging.getLogger(__name__)


class PulseRegistry:
    def __init__(self) -> None:
        super().__init__()
        self._pulses: List[Pulse] = []
        self._pulses_by_name: Dict[str, Pulse] = {}
        self._pulses_by_id: Dict[int, Pulse] = {}
        self._pulse_added_callbacks: List[PulseCallback] = []
        self._pulse_removed_callbacks: List[PulseCallback] = []

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

    def add_pulse_added_callback(self, callback: PulseCallback) -> None:
        if callback not in self._pulse_added_callbacks:
            self._pulse_added_callbacks.append(callback)

    def remove_pulse_added_callback(self, callback: PulseCallback) -> None:
        if callback in self._pulse_added_callbacks:
            self._pulse_added_callbacks.remove(callback)

    def add_pulse_removed_callback(self, callback: PulseCallback) -> None:
        if callback not in self._pulse_removed_callbacks:
            self._pulse_removed_callbacks.append(callback)

    def remove_pulse_removed_callback(self, callback: PulseCallback) -> None:
        if callback in self._pulse_removed_callbacks:
            self._pulse_removed_callbacks.remove(callback)

    def notify_pulse_added(self, pulse: Pulse) -> None:
        for callback in self._pulse_added_callbacks:
            callback(pulse)

    def notify_pulse_removed(self, pulse: Pulse) -> None:
        for callback in self._pulse_removed_callbacks:
            callback(pulse)

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
