import logging
from typing import Dict, List
from pydglab_ws.typing import PulseOperation

logger = logging.getLogger(__name__)

class Pulse:
    def __init__(self, index: int, name: str, data: List[PulseOperation]) -> None:
        self.index: int = index
        self.name: str = name
        self.data: List[PulseOperation] = data

class PulseRegistry:
    def __init__(self) -> None:
        self.pulses: List[Pulse] = []
        self.pulses_by_name: Dict[str, Pulse] = {}

    def register_pulse(self, name: str, data: List[PulseOperation]) -> Pulse:
        pulse = Pulse(len(self.pulses), name, data)
        self.pulses.append(pulse)
        self.pulses_by_name[pulse.name] = pulse
        return pulse

    def load_from_config(self, pulses_config: Dict[str, List[PulseOperation]]) -> None:
        """从配置加载脉冲"""
        self.pulses.clear()
        self.pulses_by_name.clear()
        
        for name, data in pulses_config.items():
            try:
                self.register_pulse(name, data)
                logger.debug(f"Loaded pulse: {name}")
            except Exception as e:
                logger.error(f"Failed to load pulse {name}: {e}")
        
        logger.info(f"Loaded {len(self.pulses)} pulses from config")
    
    def export_to_config(self) -> Dict[str, List[PulseOperation]]:
        """导出所有脉冲到配置格式"""
        return {pulse.name: list(pulse.data) for pulse in self.pulses}