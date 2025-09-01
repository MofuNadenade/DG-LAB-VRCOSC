"""
DG-LAB V3协议数据模型

基于郊狼情趣脉冲主机V3协议文档实现的强类型数据模型
"""

from enum import Enum, IntEnum
from typing import List, Optional, TypedDict, Dict, Tuple


# 基础类型定义
WaveformFrequency = int
"""波形频率，范围在 [10, 240]"""

WaveformStrength = int
"""波形强度，范围在 [0, 100]"""

WaveformFrequencyOperation = Tuple[
    WaveformFrequency, WaveformFrequency, WaveformFrequency, WaveformFrequency
]
"""波形频率操作数据"""

WaveformStrengthOperation = Tuple[
    WaveformStrength, WaveformStrength, WaveformStrength, WaveformStrength
]
"""波形强度操作数据"""

PulseOperation = Tuple[
    WaveformFrequencyOperation,
    WaveformStrengthOperation
]
"""波形操作数据"""

class Channel(Enum):
    """通道枚举"""
    A = "A"
    B = "B"


class StrengthParsingMethod(IntEnum):
    """强度值解读方式"""
    NO_CHANGE = 0b00      # 不改变
    INCREASE = 0b01       # 相对增加
    DECREASE = 0b10       # 相对减少
    ABSOLUTE = 0b11       # 绝对设置


class DeviceInfo(TypedDict):
    """设备信息"""
    address: str
    rssi: int
    name: str


class ChannelState(TypedDict):
    """通道状态"""
    strength: int                                # 当前强度 (0-200)
    strength_limit: int                          # 强度软上限 (0-200)
    frequency_balance: int                       # 频率平衡参数1 (0-255)
    strength_balance: int                        # 强度平衡参数2 (0-255)
    pulses: List[PulseOperation]                 # 波形操作数据


class DeviceState(TypedDict):
    """设备状态"""
    channel_a: ChannelState
    channel_b: ChannelState
    is_connected: bool
    battery_level: int


class B0Command(TypedDict):
    """B0指令数据结构 (20字节)"""
    sequence_no: int                           # 序列号 (4bits)
    strength_parsing_method: int               # 强度值解读方式 (4bits)
    strength_a: int                            # A通道强度设定值 (1byte)
    strength_b: int                            # B通道强度设定值 (1byte)
    pulse_freq_a: WaveformFrequencyOperation   # A通道波形频率4条 (10-240 相对值)
    pulse_strength_a: WaveformStrengthOperation # A通道波形强度4条 (0-100)
    pulse_freq_b: WaveformFrequencyOperation   # B通道波形频率4条 (10-240 相对值)
    pulse_strength_b: WaveformStrengthOperation # B通道波形强度4条 (0-100)


class BFCommand(TypedDict):
    """BF指令数据结构 (7字节)"""
    strength_limit_a: int                # A通道强度软上限 (1byte)
    strength_limit_b: int                # B通道强度软上限 (1byte)
    freq_balance_a: int                  # A通道频率平衡参数 (1byte)
    freq_balance_b: int                  # B通道频率平衡参数 (1byte)
    strength_balance_a: int              # A通道强度平衡参数 (1byte)
    strength_balance_b: int              # B通道强度平衡参数 (1byte)


class B1Response(TypedDict):
    """B1回应消息数据结构 (4字节)"""
    sequence_no: int                     # 序列号 (1byte)
    strength_a: int                      # A通道当前实际强度 (1byte)
    strength_b: int                      # B通道当前实际强度 (1byte)


class SequenceState(TypedDict):
    """序列号状态管理"""
    current_no: int                         # 当前序列号 (1-15)
    pending_no: Optional[int]               # 等待回应的序列号
    is_input_allowed: bool                  # 是否允许输入强度
    accumulated_changes: Dict[Channel, int] # 累积的强度变化
    response_timeout: float                 # 回应超时时间(秒)
    last_send_time: Optional[float]         # 上次发送时间


class FrequencyConverter:
    """频率转换工具类 - 保留用于将来可能的Hz转换需求，当前API直接接受相对值"""
    
    @staticmethod
    def from_frequency(input_freq: int) -> int:
        """
        将输入频率(Hz)转换为协议频率(相对值) - 保留方法，当前未使用
        
        Args:
            input_freq: 输入频率值 (10-1000 Hz)
            
        Returns:
            协议频率值 (10-240 相对值)
        """
        if 10 <= input_freq <= 100:
            return input_freq
        elif 101 <= input_freq <= 600:
            return (input_freq - 100) // 5 + 100
        elif 601 <= input_freq <= 1000:
            return (input_freq - 600) // 10 + 200
        else:
            return 10
    
    @staticmethod
    def to_frequency(protocol_freq: int) -> int:
        """
        将协议频率(相对值)转换为输入频率(Hz) - 保留方法，当前未使用
        
        Args:
            protocol_freq: 协议频率值 (10-240 相对值)
            
        Returns:
            输入频率值 (10-1000 Hz)
        """
        if 10 <= protocol_freq <= 100:
            return protocol_freq
        elif 101 <= protocol_freq <= 200:
            return (protocol_freq - 100) * 5 + 100
        elif 201 <= protocol_freq <= 240:
            return (protocol_freq - 200) * 10 + 600
        else:
            return 10


# 蓝牙服务和特性UUID
class BluetoothUUIDs:
    """蓝牙UUID常量"""
    # V3设备名称
    DEVICE_NAME = "47L121000"
    WIRELESS_SENSOR_NAME = "47L120100"
    
    # 服务UUID
    SERVICE_WRITE = "0000180c-0000-1000-8000-00805f9b34fb"
    SERVICE_NOTIFY = "0000180c-0000-1000-8000-00805f9b34fb"
    SERVICE_BATTERY = "0000180a-0000-1000-8000-00805f9b34fb"
    
    # 特性UUID
    CHARACTERISTIC_WRITE = "0000150a-0000-1000-8000-00805f9b34fb"     # 写入特性
    CHARACTERISTIC_NOTIFY = "0000150b-0000-1000-8000-00805f9b34fb"    # 通知特性
    CHARACTERISTIC_BATTERY = "00001500-0000-1000-8000-00805f9b34fb"   # 电量特性


# 协议常量
class ProtocolConstants:
    """协议常量"""
    # 数据发送间隔
    DATA_SEND_INTERVAL = 0.1  # 100ms
    
    # 数据范围
    STRENGTH_MIN = 0
    STRENGTH_MAX = 200
    WAVE_FREQUENCY_MIN = 10      # 协议频率最小值 (相对值)
    WAVE_FREQUENCY_MAX = 240     # 协议频率最大值 (相对值)
    WAVE_STRENGTH_MIN = 0
    WAVE_STRENGTH_MAX = 100
    BALANCE_PARAM_MIN = 0
    BALANCE_PARAM_MAX = 255
    SEQUENCE_NO_MIN = 0
    SEQUENCE_NO_MAX = 15
    
    # 默认值
    DEFAULT_STRENGTH_LIMIT = 200
    DEFAULT_FREQUENCY_BALANCE = 100
    DEFAULT_STRENGTH_BALANCE = 100
