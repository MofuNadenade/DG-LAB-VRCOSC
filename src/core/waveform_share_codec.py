"""
波形分享编解码器

提供波形数据的编码和解码功能，支持"前缀|名称|BASE64|哈希"格式
"""

import base64
import hashlib
import logging
from datetime import datetime

from pydantic import ValidationError
from core.dglab_pulse import Pulse
from core.waveform_share_models import (
    WaveformShareData, WaveformMetadata, ShareCodeComponents,
    ShareCodeValidation, ParsedShareCode
)

logger = logging.getLogger(__name__)


class WaveformShareCodec:
    """波形分享编解码器 (Pydantic版本)"""
    
    PREFIX = "DGLAB-PULSE-V1"
    VERSION = "1.0"
    SEPARATOR = "|"
    
    @staticmethod
    def encode_pulse(pulse: Pulse) -> str:
        """将波形编码为分享码
        
        Args:
            pulse: 要编码的波形对象
            
        Returns:
            str: 分享码字符串
            
        Raises:
            ValueError: 编码失败时抛出
        """
        try:
            # 计算元数据
            intensities = [max(step[1]) for step in pulse.data]
            frequencies = [max(step[0]) for step in pulse.data]
            
            # 创建元数据模型
            metadata = WaveformMetadata(
                created=datetime.now(),
                steps=len(pulse.data),
                duration_ms=len(pulse.data) * 100,
                max_intensity=max(intensities) if intensities else 0,
                max_frequency=max(frequencies) if frequencies else 0
            )
            
            # 创建分享数据模型
            share_data = WaveformShareData(
                version=WaveformShareCodec.VERSION,
                name=pulse.name,
                data=list(pulse.data),
                metadata=metadata
            )
            
            # 序列化为JSON
            json_str = share_data.model_dump_json(by_alias=False)
            
            # BASE64编码
            base64_data = base64.b64encode(json_str.encode('utf-8')).decode('ascii')
            
            # 计算SHA256哈希
            hash_value = hashlib.sha256(base64_data.encode('ascii')).hexdigest()
            
            # 组装分享码
            share_code = WaveformShareCodec.SEPARATOR.join([
                WaveformShareCodec.PREFIX,
                pulse.name,
                base64_data,
                hash_value
            ])
            
            logger.info(f"Encoded pulse '{pulse.name}' to share code (length: {len(share_code)})")
            return share_code
            
        except ValidationError as e:
            logger.error(f"Validation error encoding pulse '{pulse.name}': {e}")
            raise ValueError(f"波形数据验证失败: {e}")
        except Exception as e:
            logger.error(f"Failed to encode pulse '{pulse.name}': {e}")
            raise ValueError(f"编码波形失败: {e}")
    
    @staticmethod
    def decode_share_code(share_code: str) -> ParsedShareCode:
        """解码分享码为波形数据
        
        Args:
            share_code: 分享码字符串
            
        Returns:
            ParsedShareCode: 解析结果
        """
        # 初始化默认结果
        validation = ShareCodeValidation(is_valid=False)
        
        try:
            # 拆分分享码
            parts = share_code.strip().split(WaveformShareCodec.SEPARATOR)
            if len(parts) != 4:
                validation.errors.append("分享码格式错误：应包含4个部分")
                return WaveformShareCodec._create_empty_result(validation)
            
            prefix, display_name, base64_data, hash_value = parts
            
            # 验证前缀
            if prefix != WaveformShareCodec.PREFIX:
                validation.errors.append(f"不支持的分享码版本: {prefix}")
            
            # 验证哈希格式
            if len(hash_value) != 64 or not all(c in '0123456789abcdef' for c in hash_value):
                validation.errors.append("无效的哈希格式")
            
            # 验证哈希完整性
            calculated_hash = hashlib.sha256(base64_data.encode('ascii')).hexdigest()
            if calculated_hash != hash_value:
                validation.errors.append("数据完整性校验失败")
            
            # 创建组件对象
            try:
                components = ShareCodeComponents(
                    prefix=prefix,
                    display_name=display_name,
                    base64_data=base64_data,
                    hash_value=hash_value
                )
            except ValidationError as e:
                validation.errors.append(f"组件验证失败: {e}")
                return WaveformShareCodec._create_empty_result(validation)
            
            # 如果基本验证失败，直接返回
            if validation.errors:
                return ParsedShareCode(
                    components=components,
                    pulse_data=WaveformShareCodec._create_empty_pulse_data(),
                    validation=validation
                )
            
            # 解码BASE64
            try:
                json_str = base64.b64decode(base64_data).decode('utf-8')
            except Exception as e:
                validation.errors.append(f"BASE64解码失败: {e}")
                return ParsedShareCode(
                    components=components,
                    pulse_data=WaveformShareCodec._create_empty_pulse_data(),
                    validation=validation
                )
            
            # 解析JSON并验证
            try:
                pulse_data = WaveformShareData.model_validate_json(json_str)
                validation.is_valid = True
                
                # 添加数据质量警告
                if len(pulse_data.data) > 100:
                    validation.warnings.append(f"波形步数较多({len(pulse_data.data)}步)，可能影响性能")
                
                if pulse_data.metadata.max_intensity > 150:
                    validation.warnings.append(f"最大强度较高({pulse_data.metadata.max_intensity})，请谨慎使用")
                
                if pulse_data.metadata.max_frequency > 150:
                    validation.warnings.append(f"最大频率较高({pulse_data.metadata.max_frequency})，请谨慎使用")
                
                logger.info(f"Successfully decoded share code for pulse '{pulse_data.name}'")
                
            except ValidationError as e:
                validation.errors.append(f"数据验证失败: {e}")
                pulse_data = WaveformShareCodec._create_empty_pulse_data()
            except Exception as e:
                validation.errors.append(f"JSON解析失败: {e}")
                pulse_data = WaveformShareCodec._create_empty_pulse_data()
            
            return ParsedShareCode(
                components=components,
                pulse_data=pulse_data,
                validation=validation
            )
            
        except Exception as e:
            logger.error(f"Unexpected error decoding share code: {e}")
            validation.errors.append(f"解码过程发生意外错误: {e}")
            return WaveformShareCodec._create_empty_result(validation)
    
    @staticmethod
    def _create_empty_result(validation: ShareCodeValidation) -> ParsedShareCode:
        """创建空的解析结果"""
        return ParsedShareCode(
            components=ShareCodeComponents(
                prefix="", display_name="", base64_data="", hash_value="0"*64
            ),
            pulse_data=WaveformShareCodec._create_empty_pulse_data(),
            validation=validation
        )
    
    @staticmethod
    def _create_empty_pulse_data() -> WaveformShareData:
        """创建空的波形数据"""
        return WaveformShareData(
            name="",
            data=[((10, 10, 10, 10), (0, 0, 0, 0))],  # 最小有效数据
            metadata=WaveformMetadata(
                created=datetime.now(),
                steps=1,
                duration_ms=100,
                max_intensity=0,
                max_frequency=10
            )
        )
    
    @staticmethod
    def validate_share_code(share_code: str) -> ShareCodeValidation:
        """快速验证分享码格式
        
        Args:
            share_code: 分享码字符串
            
        Returns:
            ShareCodeValidation: 验证结果
        """
        try:
            parsed = WaveformShareCodec.decode_share_code(share_code)
            return parsed.validation
        except Exception as e:
            return ShareCodeValidation(
                is_valid=False,
                errors=[f"验证失败: {e}"]
            )