"""
DG-LAB蓝牙通信模块

包含DG-LAB V3协议的完整实现，提供强类型的蓝牙通信接口
"""

from .bluetooth_models import (
    # 基础类型定义
    WaveformFrequency, WaveformStrength, WaveformFrequencyOperation, 
    WaveformStrengthOperation, PulseOperation,
    # 枚举类型
    Channel, StrengthParsingMethod,
    # 数据模型
    DeviceInfo, ChannelState, DeviceState, B0Command, BFCommand, B1Response, 
    # 工具类
    FrequencyConverter, BluetoothUUIDs, ProtocolConstants
)

from .bluetooth_protocol import BluetoothProtocol

from .bluetooth_controller import BluetoothController

__all__ = [
    # 基础类型定义
    'WaveformFrequency', 'WaveformStrength', 'WaveformFrequencyOperation', 
    'WaveformStrengthOperation', 'PulseOperation',
    
    # 枚举类型
    'Channel', 'StrengthParsingMethod',
    
    # 数据模型
    'DeviceInfo', 'ChannelState', 'DeviceState', 'B0Command', 'BFCommand', 'B1Response', 
    
    # 工具类
    'FrequencyConverter', 'BluetoothUUIDs', 'ProtocolConstants',
    
    # 协议处理器
    'BluetoothProtocol',
    
    # 蓝牙处理器
    'BluetoothController'
]
