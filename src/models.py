"""
本地类型定义模块

重新创建pydglab_ws中的关键类型，以减少对外部依赖的耦合
"""
from datetime import datetime
from enum import Enum, IntEnum
from typing import Set, Tuple, Union, Dict, List, TypedDict

from pydantic import BaseModel


class FrequencyMode(Enum):
    """
    频率模式枚举
    """
    FIXED = "fixed"
    INDIVIDUAL = "individual"


class ConnectionState(Enum):
    """连接状态枚举"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    WAITING = "waiting"
    CONNECTED = "connected"
    FAILED = "failed"
    ERROR = "error"


class UIFeature(Enum):
    """UI功能开关枚举"""
    PANEL_CONTROL = "panel_control"
    CHATBOX_STATUS = "chatbox_status"
    DYNAMIC_BONE_A = "dynamic_bone_a"
    DYNAMIC_BONE_B = "dynamic_bone_b"
    FIRE_MODE = "fire_mode"


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


class Channel(IntEnum):
    """
    通道枚举
    
    :ivar A: A 通道
    :ivar B: B 通道
    """
    A = 1
    B = 2


class StrengthOperationType(IntEnum):
    """
    强度变化模式
    
    :ivar DECREASE: 通道强度减少
    :ivar INCREASE: 通道强度增加
    :ivar SET_TO: 通道强度变化为指定数值
    """
    DECREASE = 0
    INCREASE = 1
    SET_TO = 2


class FeedbackButton(IntEnum):
    """
    App 反馈按钮
    
    * A 通道 5 个按钮（从左至右）的角标为 0,1,2,3,4
    * B 通道 5 个按钮（从左至右）的角标为 5,6,7,8,9
    """
    A1 = 0
    A2 = 1
    A3 = 2
    A4 = 3
    A5 = 4
    B1 = 5
    B2 = 6
    B3 = 7
    B4 = 8
    B5 = 9


class RetCode(IntEnum):
    """
    WebSocket 消息错误码枚举
    
    :ivar SUCCESS: 成功
    :ivar CLIENT_DISCONNECTED: 对方客户端已断开
    :ivar INVALID_CLIENT_ID: 二维码中没有有效的 clientId
    :ivar SERVER_DELAY: Socket 连接上了，但服务器迟迟不下发 App 端的 ID 来绑定
    :ivar ID_ALREADY_BOUND: 此 ID 已被其他客户端绑定关系
    :ivar TARGET_CLIENT_NOT_FOUND: 要绑定的目标客户端不存在
    :ivar INCOMPATIBLE_RELATIONSHIP: 收信方和寄信方不是绑定关系
    :ivar NON_JSON_CONTENT: 发送的内容不是标准 JSON 对象
    :ivar RECIPIENT_NOT_FOUND: 未找到收信人（离线）
    :ivar MESSAGE_TOO_LONG: 下发的 message 长度大于 1950
    :ivar SERVER_INTERNAL_ERROR: 服务器内部异常
    """
    SUCCESS = 200
    CLIENT_DISCONNECTED = 209
    INVALID_CLIENT_ID = 210
    SERVER_DELAY = 211
    ID_ALREADY_BOUND = 400
    TARGET_CLIENT_NOT_FOUND = 401
    INCOMPATIBLE_RELATIONSHIP = 402
    NON_JSON_CONTENT = 403
    RECIPIENT_NOT_FOUND = 404
    MESSAGE_TOO_LONG = 405
    SERVER_INTERNAL_ERROR = 500


class StrengthData(BaseModel):
    """
    强度数据模型
    
    :ivar a: A 通道强度
    :ivar b: B 通道强度
    :ivar a_limit: A 通道强度上限
    :ivar b_limit: B 通道强度上限
    """
    a: int
    b: int
    a_limit: int
    b_limit: int


# OSC 相关类型
MidiPacket = Tuple[int, int, int, int]
"""MIDI消息包类型 - (port_id, status_byte, data1, data2)"""

OSCValue = Union[int, float, str, bool, bytes, None, MidiPacket, Tuple[datetime, int], List['OSCValue']]
"""OSC 消息参数类型 - 支持所有OSC协议类型："""

class OSCValueType(Enum):
    """OSC消息参数类型枚举"""
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    BOOL = "bool"
    BYTES = "bytes"
    NONE = "none"
    MIDI_PACKET = "midi_packet"
    TIME_TAG = "time_tag"
    LIST = "list"

class OSCAddressInfo(TypedDict):
    address: str
    types: Set[OSCValueType]
    last_value: OSCValue


# OSC相关的具体类型定义
class OSCAddressDict(TypedDict):
    """OSC地址配置项类型"""
    name: str
    code: str


class OSCTemplateDict(TypedDict):
    """OSC模板配置项类型"""
    name: str
    pattern: str
    description: str


class OSCBindingDict(TypedDict):
    """OSC绑定配置项类型"""
    address_name: str
    action_name: str


# 配置设置类型定义
class SettingsDict(TypedDict, total=False):
    """应用程序设置配置类型定义"""
    # 网络设置
    interface: str
    ip: str
    port: int
    osc_port: int
    language: str
    enable_remote: bool
    remote_address: str

    # 控制器设置
    enable_chatbox_status: bool
    fire_mode_strength_step: int
    fire_mode_disabled: bool
    enable_panel_control: bool
    dynamic_bone_mode_a: bool
    dynamic_bone_mode_b: bool
    current_pulse_a: str
    current_pulse_b: str

    # 配置数据 - 使用具体的TypedDict类型
    addresses: List[OSCAddressDict]
    pulses: Dict[str, List[PulseOperation]]
    templates: List[OSCTemplateDict]
    bindings: List[OSCBindingDict]


# 波形相关类型
class IntegrityReportStats(TypedDict):
    """完整性报告统计信息"""
    steps: int
    max_frequency: int
    max_intensity: int
    duration_ms: int


class IntegrityReport(TypedDict):
    """数据完整性检查报告类型"""
    valid: bool
    issues: List[str]
    warnings: List[str]
    stats: IntegrityReportStats


class PulseDict(TypedDict):
    """导入波形项的数据结构"""
    name: str
    data: List[PulseOperation]
    integrity: IntegrityReport
