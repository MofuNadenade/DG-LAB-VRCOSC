"""
官方波形文件支持模块

提供对郊狼App官方.pulse波形文件的解析和转换支持。
"""

from core.official.pulse_file_models import (
    FrequencyMode,
    PulseFileConstants,
    PulseDataItem,
    PulseFileHeader,
    PulseSection,
    PulseFileData,
    ParseError,
    ParserContext,
    ParseResult,
    FrequencySliderValue,
    FrequencyInputValue,
    ProtocolFrequencyValue,
    SectionTimeSliderValue,
    SpeedMultiplier,
    IntensityValue,
)

from core.official.pulse_file_parser import (
    PulseFileParser,
)

__all__ = [
    # 数据模型
    "FrequencyMode",
    "PulseFileConstants", 
    "PulseDataItem",
    "PulseFileHeader",
    "PulseSection",
    "PulseFileData",
    "ParseError",
    "ParserContext",
    "ParseResult",
    
    # 类型别名
    "FrequencySliderValue",
    "FrequencyInputValue", 
    "ProtocolFrequencyValue",
    "SectionTimeSliderValue",
    "SpeedMultiplier",
    "IntensityValue",
    
    # 解析器
    "PulseFileParser",
]
