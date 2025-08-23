"""
本地类型定义模块

重新创建pydglab_ws中的关键类型，以减少对外部依赖的耦合
"""
from enum import IntEnum
from typing import Tuple
from pydantic import BaseModel

__all__ = (
    "Channel",
    "StrengthData", 
    "PulseOperation",
    "WaveformFrequency",
    "WaveformStrength", 
    "WaveformFrequencyOperation",
    "WaveformStrengthOperation",
    "StrengthOperationType",
    "FeedbackButton",
    "RetCode"
)

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
