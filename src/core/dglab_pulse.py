import logging
from typing import Dict, List, Optional

from models import PulseOperation

logger = logging.getLogger(__name__)


class Pulse:
    def __init__(self, index: int, name: str, data: List[PulseOperation]) -> None:
        super().__init__()
        self.index: int = index
        self.name: str = name
        self.data: List[PulseOperation] = data


class PulseRegistry:
    def __init__(self) -> None:
        super().__init__()
        self._pulses: List[Pulse] = []
        self._pulses_by_name: Dict[str, Pulse] = {}

    @property
    def pulses(self) -> List[Pulse]:
        """获取所有波形列表（只读）"""
        return self._pulses.copy()

    @property
    def pulses_by_name(self) -> Dict[str, Pulse]:
        """获取按名称索引的波形字典（只读）"""
        return self._pulses_by_name.copy()

    def get_pulse_by_name(self, name: str) -> Optional[Pulse]:
        """根据名称获取波形"""
        return self._pulses_by_name.get(name)

    def has_pulse_name(self, name: str) -> bool:
        """检查是否存在指定名称的波形"""
        return name in self._pulses_by_name

    def get_pulse_count(self) -> int:
        """获取波形总数"""
        return len(self._pulses)

    def get_pulse_by_index(self, index: int) -> Optional[Pulse]:
        """安全获取指定索引的波形"""
        if 0 <= index < len(self._pulses):
            return self._pulses[index]
        return None

    def get_pulse_name_by_index(self, index: int) -> str:
        """安全获取指定索引的波形名称"""
        pulse = self.get_pulse_by_index(index)
        return pulse.name if pulse else "未知波形"

    def get_valid_index(self, index: int) -> int:
        """获取有效的索引，无效时返回0"""
        if 0 <= index < len(self._pulses):
            return index
        return 0 if self._pulses else -1

    def is_valid_index(self, index: int) -> bool:
        """检查索引是否有效"""
        return 0 <= index < len(self._pulses)

    def unregister_pulse(self, pulse: Pulse) -> None:
        """移除波形"""
        if pulse in self._pulses:
            self._pulses.remove(pulse)
            if pulse.name in self._pulses_by_name:
                del self._pulses_by_name[pulse.name]

            # 重新索引
            for i, p in enumerate(self._pulses):
                p.index = i

    def register_pulse(self, name: str, data: List[PulseOperation]) -> Pulse:
        pulse = Pulse(len(self._pulses), name, data)
        self._pulses.append(pulse)
        self._pulses_by_name[pulse.name] = pulse
        return pulse

    def load_from_config(self, pulses_config: Dict[str, List[PulseOperation]]) -> None:
        """从配置加载波形"""
        self._pulses.clear()
        self._pulses_by_name.clear()

        for name, data in pulses_config.items():
            try:
                self.register_pulse(name, data)
                logger.debug(f"Loaded pulse: {name}")
            except Exception as e:
                logger.error(f"Failed to load pulse {name}: {e}")

        logger.info(f"Loaded {len(self._pulses)} pulses from config")

    def export_to_config(self) -> Dict[str, List[PulseOperation]]:
        """导出所有波形到配置格式"""
        return {pulse.name: list(pulse.data) for pulse in self._pulses}
