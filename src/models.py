"""
本地类型定义模块

重新创建pydglab_ws中的关键类型，以减少对外部依赖的耦合
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Awaitable, Optional, Protocol, Set, Tuple, Type, Union, Dict, List, TypedDict


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


class ConnectionMode(Enum):
    """连接模式枚举"""
    WEBSOCKET = "websocket"
    BLUETOOTH = "bluetooth"


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


class StrengthData(TypedDict):
    """
    强度数据模型
    
    :ivar a: A 通道强度
    :ivar b: B 通道强度
    :ivar a_limit: A 通道强度上限
    :ivar b_limit: B 通道强度上限
    """
    strength: Dict[Channel, int]
    strength_limit: Dict[Channel, int]


# OSC 相关类型
MidiPacket = Tuple[int, int, int, int]
"""MIDI消息包类型 - (port_id, status_byte, data1, data2)"""


TimeTag = Tuple[datetime, int]
"""时间戳类型 - (datetime, int)"""


OSCPrimitive = Union[int, float, str, bool, bytes, None, MidiPacket, TimeTag, List['OSCValue']]
"""OSC消息参数类型 - 支持所有OSC协议类型"""


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


class OSCValue(ABC):
    @classmethod
    @abstractmethod
    def value_type(cls) -> OSCValueType:
        ...

    @classmethod
    @abstractmethod
    def primitive_type(cls) -> Type[OSCPrimitive]:
        ...

    @property
    @abstractmethod
    def value(self) -> OSCPrimitive:
        ...

    @value.setter
    @abstractmethod
    def value(self, value: OSCPrimitive):
        ...


@dataclass
class OSCTypedValue[T: OSCPrimitive](OSCValue):
    _value: T

    def __init__(self, value: T):
        super().__init__()
        self._value = value
    
    @property
    def value(self) -> T:
        return self._value
    
    @value.setter
    def value(self, value: T):
        self._value = value


class OSCInt(OSCTypedValue[int]):
    def __init__(self, value: int):
        super().__init__(value)

    @classmethod
    def value_type(cls) -> OSCValueType:
        return OSCValueType.INT

    @classmethod
    def primitive_type(cls) -> Type[int]:
        return int


class OSCFloat(OSCTypedValue[float]):
    def __init__(self, value: float):
        super().__init__(value)

    @classmethod
    def value_type(cls) -> OSCValueType:
        return OSCValueType.FLOAT

    @classmethod
    def primitive_type(cls) -> Type[float]:
        return float


class OSCString(OSCTypedValue[str]):
    def __init__(self, value: str):
        super().__init__(value)

    @classmethod
    def value_type(cls) -> OSCValueType:
        return OSCValueType.STRING

    @classmethod
    def primitive_type(cls) -> Type[str]:
        return str


class OSCBool(OSCTypedValue[bool]):
    def __init__(self, value: bool):
        super().__init__(value)

    @classmethod
    def value_type(cls) -> OSCValueType:
        return OSCValueType.BOOL

    @classmethod
    def primitive_type(cls) -> Type[bool]:
        return bool


class OSCBytes(OSCTypedValue[bytes]):
    def __init__(self, value: bytes):
        super().__init__(value)

    @classmethod
    def value_type(cls) -> OSCValueType:
        return OSCValueType.BYTES

    @classmethod
    def primitive_type(cls) -> Type[bytes]:
        return bytes


class OSCNone(OSCTypedValue[None]):
    def __init__(self, value: None):
        super().__init__(value)

    @classmethod
    def value_type(cls) -> OSCValueType:
        return OSCValueType.NONE

    @classmethod
    def primitive_type(cls) -> Type[None]:
        return type(None)


class OSCMidiPacket(OSCTypedValue[MidiPacket]):
    def __init__(self, value: MidiPacket):
        super().__init__(value)
    
    @classmethod
    def value_type(cls) -> OSCValueType:
        return OSCValueType.MIDI_PACKET

    @classmethod
    def primitive_type(cls) -> Type[MidiPacket]:
        return MidiPacket


class OSCTimeTag(OSCTypedValue[TimeTag]):
    def __init__(self, value: TimeTag):
        super().__init__(value)
    
    @classmethod
    def value_type(cls) -> OSCValueType:
        return OSCValueType.TIME_TAG

    @classmethod
    def primitive_type(cls) -> Type[TimeTag]:
        return TimeTag


class OSCList(OSCTypedValue[List['OSCValue']]):
    def __init__(self, value: List['OSCValue']):
        super().__init__(value)
    
    @classmethod
    def value_type(cls) -> OSCValueType:
        return OSCValueType.LIST

    @classmethod
    def primitive_type(cls) -> Type[List['OSCValue']]:
        return List['OSCValue']


def get_osc_value(value: OSCPrimitive) -> OSCValue:
    if isinstance(value, bool):
        return OSCBool(value)
    elif isinstance(value, int):
        return OSCInt(value)
    elif isinstance(value, float):
        return OSCFloat(value)
    elif isinstance(value, str):
        return OSCString(value)
    elif isinstance(value, bytes):
        return OSCBytes(value)
    elif value is None:
        return OSCNone(value)
    elif isinstance(value, tuple):
        if len(value) == 4:
            return OSCMidiPacket(value)
        elif len(value) == 2:
            return OSCTimeTag(value)
    else:
        return OSCList(value)


class OSCActionCallback(Protocol):
    """OSC动作回调协议"""
    def __call__(self, *args: Any) -> Awaitable[None]:
        ...


class OSCActionTypedCallback[T: OSCValue](OSCActionCallback, Protocol):
    """OSC动作回调协议"""
    def __call__(self, *args: T) -> Awaitable[None]:
        ...


class OSCAddressInfo(TypedDict):
    address: str
    types: Set[OSCValueType]
    last_value: Optional[OSCValue]


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
class WebsocketSettingsDict(TypedDict, total=False):
    """WebSocket设置配置类型定义"""
    interface: str
    ip: str
    port: int
    enable_remote: bool
    remote_address: str


class BluetoothSettingsDict(TypedDict, total=False):
    """蓝牙设置配置类型定义"""
    strength_limit_a: int
    strength_limit_b: int
    freq_balance_a: int
    freq_balance_b: int
    strength_balance_a: int
    strength_balance_b: int


class ConnectionSettingsDict(TypedDict, total=False):
    """连接设置配置类型定义"""
    mode: str  # ConnectionMode的值
    websocket: WebsocketSettingsDict
    bluetooth: BluetoothSettingsDict


class ControllerSettingsDict(TypedDict, total=False):
    """控制器设置配置类型定义"""
    enable_chatbox_status: bool
    fire_mode_strength_step: int
    fire_mode_disabled: bool
    enable_panel_control: bool
    disable_panel_pulse_setting: bool
    dynamic_bone_mode_a: bool
    dynamic_bone_mode_b: bool
    current_pulse_a: str
    current_pulse_b: str
    # 动骨模式范围设置
    dynamic_bone_min_value_a: int
    dynamic_bone_max_value_a: int
    dynamic_bone_min_value_b: int
    dynamic_bone_max_value_b: int


class AutoUpdaterSettingsDict(TypedDict, total=False):
    """自动更新设置配置类型定义"""
    enabled: bool
    check_on_startup: bool
    github_repo: str
    auto_download: bool
    auto_install: bool


class SettingsDict(TypedDict, total=False):
    """应用程序设置配置类型定义"""
    # 全局设置
    osc_port: int
    language: str
    
    # 连接设置
    connection: ConnectionSettingsDict
    
    # 控制器设置
    controller: ControllerSettingsDict

    # 自动更新设置
    auto_updater: AutoUpdaterSettingsDict

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


class WebsocketDeviceParamsDict(TypedDict):
    """WebSocket设备参数数据结构"""
    strength_limit_a: int
    strength_limit_b: int
    freq_balance_a: int
    freq_balance_b: int
    strength_balance_a: int
    strength_balance_b: int
