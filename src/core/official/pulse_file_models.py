"""
官方.pulse文件数据模型

定义解析郊狼App的.pulse波形文件格式所需的数据结构和类型
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Final


class FrequencyMode(IntEnum):
    """频率模式枚举
    
    根据郊狼App波形格式文档定义的四种频率模式：
    - 固定模式：本小节的全部持续时间内频率恒定为频率A
    - 节内渐变：本小节的全部持续时间内频率逐渐从频率A渐变到频率B
    - 元内渐变：每个脉冲元内频率从频率A渐变到频率B（周期性变化）
    - 元间渐变：脉冲元内部频率固定，但不同脉冲元之间频率从A渐变到B
    """
    FIXED = 1                    # 固定模式
    SECTION_GRADIENT = 2         # 节内渐变模式
    ELEMENT_GRADIENT = 3         # 元内渐变模式
    ELEMENT_INTER_GRADIENT = 4   # 元间渐变模式


class PulseFileConstants:
    """脉冲文件常量定义
    
    包含.pulse文件格式中使用的各种映射表和常量值
    """
    
    # 频率滑块值映射表 (滑块值0-83对应的实际输入值10-1000)
    FREQ_SLIDER_VALUE_MAP: Final[List[int]] = [
        10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 
        30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49,
        50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78,
        80, 85, 90, 95,
        100, 110, 120, 130, 140, 150, 160, 170, 180, 190,
        200, 233, 266, 300, 333, 366,
        400, 450, 500, 550,
        600, 700, 800, 900, 1000
    ]
    
    # 小节时长滑块值映射表 (滑块值0-99对应的实际时长秒数)
    SECTION_TIME_MAP: Final[List[float]] = [
        0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 
        1.7, 1.8, 1.9, 2, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 3, 3.1, 3.2, 3.3, 
        3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 4, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9,
        5, 5.2, 5.4, 5.6, 5.8, 6, 6.2, 6.4, 6.6, 6.8, 7, 7.2, 7.4, 7.6, 7.8,
        8, 8.5, 9, 9.5,
        10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
        20, 23.4, 26.6, 30, 33.4, 36.6,
        40, 45, 50, 55,
        60, 70, 80, 90,
        100, 120, 140, 160, 180,
        200, 250, 300
    ]
    
    # 协议频率范围限制
    PROTOCOL_FREQ_MIN: Final[int] = 10
    PROTOCOL_FREQ_MAX: Final[int] = 240
    
    # 强度范围限制
    INTENSITY_MIN: Final[int] = 0
    INTENSITY_MAX: Final[int] = 100
    
    # 脉冲元最小长度（秒）
    MIN_PULSE_ELEMENT_DURATION: Final[float] = 0.2
    
    # 基础时间单位（秒）- 每个脉冲数据项在正常速度下的时长
    BASE_TIME_PER_ITEM: Final[float] = 0.1
    
    # 支持的速度倍率
    VALID_SPEED_MULTIPLIERS: Final[List[int]] = [1, 2, 4]
    
    # 文件格式标识符
    FILE_FORMAT_PREFIX: Final[str] = "Dungeonlab+pulse:"
    
    # 小节分隔符
    SECTION_SEPARATOR: Final[str] = "+section+"
    
    # 脉冲数据分隔符
    PULSE_DATA_SEPARATOR: Final[str] = "/"
    
    # 脉冲数据项分隔符
    PULSE_ITEM_SEPARATOR: Final[str] = ","
    
    # 脉冲数据项内部分隔符（强度-脉冲类型）
    PULSE_ITEM_INTERNAL_SEPARATOR: Final[str] = "-"


@dataclass
class PulseDataItem:
    """脉冲数据项
    
    表示.pulse文件中的单个脉冲数据项，包含强度和脉冲类型信息
    """
    intensity: int      # 强度值 (0-100)
    pulse_type: int     # 脉冲类型


@dataclass
class PulseFileHeader:
    """脉冲文件头部信息
    
    包含.pulse文件的全局配置参数
    """
    rest_duration: float    # 休息时长（秒）
    speed_multiplier: int   # 速度倍率 (1, 2, 4)
    unknown_param: int      # 未知参数（通常为16）


@dataclass
class PulseSection:
    """脉冲小节信息
    
    表示.pulse文件中的单个小节，包含频率设置、时长、模式和脉冲数据
    """
    freq_a: int                         # 频率A滑块值 (0-83)
    freq_b: int                         # 频率B滑块值 (0-83)
    section_duration: float             # 小节时长（秒）
    frequency_mode: FrequencyMode       # 频率模式
    enabled: bool                       # 小节开关
    pulse_data: List[PulseDataItem]     # 脉冲数据列表


@dataclass
class PulseFileData:
    """脉冲文件完整数据
    
    包含解析后的完整.pulse文件内容
    """
    header: PulseFileHeader         # 文件头部信息
    sections: List[PulseSection]    # 小节列表


@dataclass
class ParseError:
    """解析错误信息
    
    用于记录解析过程中遇到的错误和警告
    """
    message: str  # 错误消息


class ParserContext:
    """解析器上下文
    
    用于在解析过程中收集错误、警告和中间结果
    """
    
    def __init__(self) -> None:
        """初始化解析器上下文"""
        super().__init__()
        self.errors: List[ParseError] = []
        self.warnings: List[ParseError] = []
    
    def add_error(self, message: str) -> None:
        """添加错误"""
        self.errors.append(ParseError(message))
    
    def add_warning(self, message: str) -> None:
        """添加警告"""
        self.warnings.append(ParseError(message))
    
    def has_errors(self) -> bool:
        """是否有错误"""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """是否有警告"""
        return len(self.warnings) > 0
    
    def clear(self) -> None:
        """清空错误和警告"""
        self.errors.clear()
        self.warnings.clear()


@dataclass
class ParseResult:
    """解析结果
    
    包含解析后的数据以及可能的错误和警告信息
    """
    success: bool                   # 是否解析成功
    data: PulseFileData | None      # 解析后的数据（成功时）
    errors: List[ParseError]        # 错误列表
    warnings: List[ParseError]      # 警告列表
    
    @classmethod
    def from_context(cls, context: 'ParserContext', data: PulseFileData | None = None) -> 'ParseResult':
        """从解析器上下文创建解析结果"""
        return cls(
            success=not context.has_errors() and data is not None,
            data=data,
            errors=context.errors.copy(),
            warnings=context.warnings.copy()
        )


# 类型别名，用于提高代码可读性
FrequencySliderValue = int      # 频率滑块值 (0-83)
FrequencyInputValue = int       # 频率输入值 (10-1000ms)
ProtocolFrequencyValue = int    # 协议频率值 (10-240)
SectionTimeSliderValue = int    # 小节时长滑块值 (0-99)
SpeedMultiplier = int           # 速度倍率 (1, 2, 4)
IntensityValue = int            # 强度值 (0-100)
