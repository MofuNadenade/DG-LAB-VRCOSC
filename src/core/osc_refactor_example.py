from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, List, Protocol, Tuple, Type, TypeAlias, Union

MidiPacket = Tuple[int, int, int, int]
TimeTag = Tuple[datetime, int]

OSCPrimitive: TypeAlias = Union[int, float, str, bool, bytes, None, MidiPacket, TimeTag, List['OSCValue']]

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

class OSCActionCallback(Protocol):
    """OSC动作回调协议"""
    def __call__(self, *args: Any) -> Awaitable[None]:
        ...

class OSCActionTypedCallback[T: OSCValue](OSCActionCallback, Protocol):
    """OSC动作回调协议"""
    def __call__(self, *args: T) -> Awaitable[None]:
        ...

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

# Example usage

def register_osc_action[T: OSCValue](name: str, callback: OSCActionTypedCallback[T], *types: Type[T]) -> None:
    # Test
    t = types[0].primitive_type()
    print(t)

async def foo(*args: OSCString | OSCInt | OSCBytes) -> None:
    pass

register_osc_action("test", foo, OSCString, OSCInt, OSCBytes)
