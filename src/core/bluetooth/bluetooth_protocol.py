"""
DG-LAB V3协议层实现

纯协议层，只负责V3协议的数据处理：
1. B0指令构建和解析 - 控制通道强度和波形参数
2. BF指令构建和解析 - 设置强度上限和平衡参数  
3. B1回应解析 - 处理设备状态回应
4. 强度解读方式处理 - A/B通道解读模式管理
5. 协议数据验证 - 参数范围和格式验证
"""

import logging
from typing import Optional, Tuple
import struct

from .bluetooth_models import (
    B0Command, BFCommand, B1Response, StrengthParsingMethod, ProtocolConstants, WaveformFrequencyOperation, WaveformStrengthOperation
)

logger = logging.getLogger(__name__)


class BluetoothProtocol:
    """DG-LAB V3协议处理器
    
    纯协议层实现，只负责协议数据的处理和转换：
    - 不包含业务逻辑
    - 不管理连接状态
    - 不处理回调
    - 只处理协议数据格式转换
    
    支持的协议功能：
    - B0指令：控制强度(0-200)和波形参数(频率10-240，强度0-100)
    - BF指令：设置强度软上限(0-200)和频率/强度平衡参数(0-255)
    - B1回应：解析设备状态回应(序列号，A/B通道强度)
    - 强度解读方式：管理A/B通道的4种解读模式
    """
    
    def __init__(self) -> None:
        """初始化协议处理器"""
        super().__init__()
    
    # ============ B0指令处理 ============
    
    def build_b0_command(self, sequence_no: int, strength_parsing_method: int, strength_a: int, strength_b: int,
                         pulse_freq_a: WaveformFrequencyOperation, pulse_strength_a: WaveformStrengthOperation,
                         pulse_freq_b: WaveformFrequencyOperation, pulse_strength_b: WaveformStrengthOperation) -> Optional[bytes]:
        """构建B0指令数据
        
        Args:
            sequence_no: 序列号 (0-15)
            strength_parsing_method: 强度解读方式 (4bits)
            strength_a: A通道强度设定值 (0-200)
            strength_b: B通道强度设定值 (0-200)
            pulse_freq_a: A通道波形频率4条 (10-240 相对值)
            pulse_strength_a: A通道波形强度4条 (0-100)
            pulse_freq_b: B通道波形频率4条 (10-240 相对值)
            pulse_strength_b: B通道波形强度4条 (0-100)
            
        Returns:
            20字节的B0指令数据，验证失败返回None
        """
        # 验证参数
        if not self._validate_b0_params(sequence_no, strength_parsing_method,strength_a, strength_b, pulse_freq_a, pulse_strength_a, pulse_freq_b, pulse_strength_b):
            return None
        
        # 构建B0指令
        command: B0Command = {
            'sequence_no': sequence_no,
            'strength_parsing_method': strength_parsing_method,
            'strength_a': strength_a,
            'strength_b': strength_b,
            'pulse_freq_a': pulse_freq_a,
            'pulse_strength_a': pulse_strength_a,
            'pulse_freq_b': pulse_freq_b,
            'pulse_strength_b': pulse_strength_b
        }
        
        return self.b0_command_to_bytes(command)
    
    def parse_b0_command(self, data: bytes) -> Optional[B0Command]:
        """解析B0指令数据"""
        try:
            return self.b0_command_from_bytes(data)
        except Exception:
            return None

    def b0_command_to_bytes(self, command: B0Command) -> bytes:
        """转换B0指令为20字节数据"""
        # 合并序列号和强度解读方式
        seq_and_method = (command['sequence_no'] << 4) | command['strength_parsing_method']

        # 构建数据包
        data = struct.pack(
            'BBBB4B4B4B4B',
            0xB0,
            seq_and_method,
            command['strength_a'],
            command['strength_b'],
            *command['pulse_freq_a'],
            *command['pulse_strength_a'],
            *command['pulse_freq_b'],
            *command['pulse_strength_b']
        )

        return data


    def b0_command_from_bytes(self, data: bytes) -> B0Command:
        """从字节数据创建B0指令"""
        if len(data) != 20:
            raise ValueError(f"B0指令数据长度必须为20字节，实际: {len(data)}")

        unpacked = struct.unpack('BBBB4B4B4B4B', data)

        seq_and_method = unpacked[1]
        sequence_no = (seq_and_method >> 4) & 0x0F
        strength_parsing_method = seq_and_method & 0x0F

        return {
            'sequence_no': sequence_no,
            'strength_parsing_method': strength_parsing_method,
            'strength_a': unpacked[2],
            'strength_b': unpacked[3],
            'pulse_freq_a': tuple(unpacked[4:8]),
            'pulse_strength_a': tuple(unpacked[8:12]),
            'pulse_freq_b': tuple(unpacked[12:16]),
            'pulse_strength_b': tuple(unpacked[16:20])
        }
    
    # ============ BF指令处理 ============
    
    def build_bf_command(self, strength_limit_a: int, strength_limit_b: int, freq_balance_a: int, freq_balance_b: int,
                         strength_balance_a: int, strength_balance_b: int) -> Optional[bytes]:
        """构建BF指令数据
        
        BF指令用于设置设备的输出限制和平衡调节参数：
        - 强度软上限：限制B0指令中强度值的实际输出上限
        - 平衡参数：微调A/B通道的频率和强度输出特性
        
        Args:
            strength_limit_a: A通道强度软上限 (0-200) - 限制A通道最大输出强度
            strength_limit_b: B通道强度软上限 (0-200) - 限制B通道最大输出强度  
            freq_balance_a: A通道频率平衡参数 (0-255) - 调节A通道频率输出特性
            freq_balance_b: B通道频率平衡参数 (0-255) - 调节B通道频率输出特性
            strength_balance_a: A通道强度平衡参数 (0-255) - 调节A通道强度输出特性
            strength_balance_b: B通道强度平衡参数 (0-255) - 调节B通道强度输出特性
            
        Returns:
            7字节的BF指令数据，验证失败返回None
        """
        # 验证参数
        if not self._validate_bf_params(strength_limit_a, strength_limit_b,
                                      freq_balance_a, freq_balance_b,
                                      strength_balance_a, strength_balance_b):
            return None
        
        # 构建BF指令
        command: BFCommand = {
            'strength_limit_a': strength_limit_a,
            'strength_limit_b': strength_limit_b,
            'freq_balance_a': freq_balance_a,
            'freq_balance_b': freq_balance_b,
            'strength_balance_a': strength_balance_a,
            'strength_balance_b': strength_balance_b
        }
        
        return self.bf_command_to_bytes(command)
    
    def parse_bf_command(self, data: bytes) -> Optional[BFCommand]:
        """解析BF指令数据"""
        try:
            return self.bf_command_from_bytes(data)
        except Exception:
            return None

    def bf_command_to_bytes(self, command: BFCommand) -> bytes:
        """转换BF指令为7字节数据"""
        return struct.pack(
            'BBBBBBB',
            0xBF,
            command['strength_limit_a'],
            command['strength_limit_b'],
            command['freq_balance_a'],
            command['freq_balance_b'],
            command['strength_balance_a'],
            command['strength_balance_b']
        )


    def bf_command_from_bytes(self, data: bytes) -> BFCommand:
        """从字节数据创建BF指令"""
        if len(data) != 7:
            raise ValueError(f"BF指令数据长度必须为7字节，实际: {len(data)}")

        unpacked = struct.unpack('BBBBBBB', data)
        return {
            'strength_limit_a': unpacked[1],
            'strength_limit_b': unpacked[2],
            'freq_balance_a': unpacked[3],
            'freq_balance_b': unpacked[4],
            'strength_balance_a': unpacked[5],
            'strength_balance_b': unpacked[6]
        }
    
    # ============ B1回应处理 ============
    
    def parse_b1_response(self, data: bytes) -> Optional[B1Response]:
        """解析B1回应消息
        
        Args:
            data: B1回应数据
            
        Returns:
            解析后的B1回应对象，失败返回None
        """
        try:
            if len(data) < 4 or data[0] != 0xB1:
                return None
            
            return self.b1_response_from_bytes(data)
            
        except Exception:
            return None

    def b1_response_from_bytes(self, data: bytes) -> B1Response:
        """从字节数据创建B1回应"""
        if len(data) < 4:
            raise ValueError(f"B1回应数据长度至少为4字节，实际: {len(data)}")

        unpacked = struct.unpack('BBBB', data[:4])
        return {
            'sequence_no': unpacked[1],
            'strength_a': unpacked[2],
            'strength_b': unpacked[3]
        }
    
    # ============ 强度解读方式处理 ============
    # 管理A/B通道的强度解读模式，每个通道支持4种解读方式(0-3)
    
    def build_strength_parsing_method(self, method_a: StrengthParsingMethod, method_b: StrengthParsingMethod) -> int:
        """构建强度解读方式字段
        
        Args:
            method_a: A通道解读方式
            method_b: B通道解读方式
            
        Returns:
            4位强度解读方式字段
        """
        return (method_a << 2) | method_b
    
    def parse_strength_parsing_method(self, method: int) -> Tuple[StrengthParsingMethod, StrengthParsingMethod]:
        """解析强度解读方式字段
        
        Args:
            method: 4位强度解读方式字段
            
        Returns:
            (A通道解读方式, B通道解读方式)
        """
        method_a = StrengthParsingMethod((method >> 2) & 0x03)
        method_b = StrengthParsingMethod(method & 0x03)
        return method_a, method_b
    
    # ============ 数据验证 ============
    
    def validate_strength(self, strength: int) -> bool:
        """验证强度值"""
        return ProtocolConstants.STRENGTH_MIN <= strength <= ProtocolConstants.STRENGTH_MAX
    
    def validate_pulse_frequency(self, frequency: int) -> bool:
        """验证波形频率"""
        return ProtocolConstants.WAVE_FREQUENCY_MIN <= frequency <= ProtocolConstants.WAVE_FREQUENCY_MAX
    
    def validate_pulse_strength(self, strength: int) -> bool:
        """验证波形强度"""
        return ProtocolConstants.WAVE_STRENGTH_MIN <= strength <= ProtocolConstants.WAVE_STRENGTH_MAX
    
    def validate_sequence_no(self, sequence_no: int) -> bool:
        """验证序列号"""
        return ProtocolConstants.SEQUENCE_NO_MIN <= sequence_no <= ProtocolConstants.SEQUENCE_NO_MAX
    
    def validate_balance_param(self, param: int) -> bool:
        """验证平衡参数"""
        return ProtocolConstants.BALANCE_PARAM_MIN <= param <= ProtocolConstants.BALANCE_PARAM_MAX
    
    # ============ 内部验证方法 ============
    
    def _validate_b0_params(self, sequence_no: int, strength_parsing_method: int, strength_a: int, strength_b: int,
                            pulse_freq_a: WaveformFrequencyOperation, pulse_strength_a: WaveformStrengthOperation,
                            pulse_freq_b: WaveformFrequencyOperation, pulse_strength_b: WaveformStrengthOperation) -> bool:
        """验证B0指令参数"""
        # 验证序列号
        if not self.validate_sequence_no(sequence_no):
            return False
        
        # 验证强度解读方式
        if not (0 <= strength_parsing_method <= 0x0F):
            return False
        
        # 验证强度值
        if not (self.validate_strength(strength_a) and self.validate_strength(strength_b)):
            return False
        
        # 验证A通道波形
        if not self._validate_pulse_frequency(pulse_freq_a, pulse_strength_a):
            return False
        
        # 验证B通道波形
        if not self._validate_pulse_frequency(pulse_freq_b, pulse_strength_b):
            return False

        return True
    
    def _validate_bf_params(self, strength_limit_a: int, strength_limit_b: int,
                           freq_balance_a: int, freq_balance_b: int,
                           strength_balance_a: int, strength_balance_b: int) -> bool:
        """验证BF指令参数"""
        # 验证强度上限
        if not (self.validate_strength(strength_limit_a) and self.validate_strength(strength_limit_b)):
            return False
        
        # 验证平衡参数
        balance_params = [freq_balance_a, freq_balance_b, strength_balance_a, strength_balance_b]
        for param in balance_params:
            if not self.validate_balance_param(param):
                return False
        
        return True

    def _validate_pulse_frequency(self, freq: WaveformFrequencyOperation, strength: WaveformStrengthOperation) -> bool:
        """验证波形数据"""
        # 验证频率范围
        for data in freq:
            if not self.validate_pulse_frequency(data):
                return False
        
        # 验证强度范围
        for data in strength:
            if not self.validate_pulse_strength(data):
                return False
        
        return True