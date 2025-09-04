"""
波形分享相关的Pydantic数据模型

定义了波形分享功能所需的所有数据结构和验证逻辑
"""

from datetime import datetime
from typing import List
from pydantic import BaseModel, Field, field_validator, ConfigDict

from models import PulseOperation


class WaveformMetadata(BaseModel):
    """波形元数据"""
    created: datetime = Field(description="创建时间")
    steps: int = Field(description="步骤数量")
    duration_ms: int = Field(description="持续时间(毫秒)")
    max_intensity: int = Field(description="最大强度")
    max_frequency: int = Field(description="最大频率")
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() + 'Z'
        }
    )


class WaveformShareData(BaseModel):
    """波形分享数据结构"""
    version: str = Field(default="1.0", description="版本号")
    name: str = Field(description="波形名称")
    data: List[PulseOperation] = Field(description="波形数据")
    metadata: WaveformMetadata = Field(description="元数据")
    
    @field_validator('data')
    @classmethod
    def validate_pulse_operations(cls, v: List[PulseOperation]) -> List[PulseOperation]:
        """验证波形操作数据"""
        for i, operation in enumerate(v):
            if len(operation) != 2:
                raise ValueError(f"步骤{i+1}: 格式错误，应为包含2个元素的元组")
            
            freq, intensity = operation
            
            # 验证频率
            if len(freq) != 4:
                raise ValueError(f"步骤{i+1}: 频率数据应为4个元素")
            
            # 验证强度
            if len(intensity) != 4:
                raise ValueError(f"步骤{i+1}: 强度数据应为4个元素")
        
        return v


class ShareCodeComponents(BaseModel):
    """分享码组件"""
    prefix: str = Field(description="前缀")
    display_name: str = Field(description="显示名称")
    base64_data: str = Field(description="BASE64数据")
    hash_value: str = Field(pattern=r'^[a-f0-9]{64}$', description="SHA256哈希值")


class ShareCodeValidation(BaseModel):
    """分享码验证结果"""
    is_valid: bool = Field(description="是否有效")
    errors: List[str] = Field(default_factory=list, description="错误列表")
    warnings: List[str] = Field(default_factory=list, description="警告列表")


class ParsedShareCode(BaseModel):
    """解析后的分享码数据"""
    components: ShareCodeComponents = Field(description="分享码组件")
    pulse_data: WaveformShareData = Field(description="波形数据")
    validation: ShareCodeValidation = Field(description="验证结果")