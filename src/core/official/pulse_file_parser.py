"""
官方.pulse文件解析器

解析郊狼App的.pulse波形文件格式，转换为系统内部PulseOperation格式。
严格按照官方波形格式文档实现，支持四种频率模式和脉冲元循环机制。
"""

import logging
import math
from pathlib import Path
from typing import List, Optional

from models import PulseOperation, WaveformFrequencyOperation, WaveformStrengthOperation
from core.official.pulse_file_models import (
    PulseFileData, PulseFileHeader, PulseSection, PulseDataItem,
    FrequencyMode, PulseFileConstants, ParseResult, ParseError, ParserContext,
    FrequencySliderValue, FrequencyInputValue, ProtocolFrequencyValue,
    SectionTimeSliderValue, SpeedMultiplier, IntensityValue
)

logger = logging.getLogger(__name__)


class PulseFileParser:
    """官方.pulse文件解析器
    
    负责解析郊狼App的.pulse波形文件，并将其转换为系统内部的PulseOperation格式。
    实现了完整的频率模式支持和脉冲元循环机制。
    
    Usage:
        parser = PulseFileParser()
        result = parser.parse_file("example.pulse")
        if result.success:
            operations = parser.convert_to_pulse_operations(result.data.header, result.data.sections)
    """
    
    def __init__(self) -> None:
        """初始化解析器"""
        super().__init__()
        self._constants = PulseFileConstants()
    
    def parse_file(self, file_path: str) -> ParseResult:
        """解析.pulse文件
        
        Args:
            file_path: .pulse文件路径
            
        Returns:
            ParseResult: 包含解析结果、数据和错误信息
        """
        try:
            file_path_obj = Path(file_path)
            
            if not file_path_obj.exists():
                return ParseResult(
                    success=False,
                    data=None,
                    errors=[ParseError(f"文件不存在: {file_path_obj}")],
                    warnings=[]
                )
            
            if not file_path_obj.suffix.lower() == '.pulse':
                logger.warning(f"文件扩展名不是.pulse: {file_path_obj}")
            
            with open(file_path_obj, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            return self.parse_content(content)
            
        except UnicodeDecodeError as e:
            return ParseResult(
                success=False,
                data=None,
                errors=[ParseError(f"文件编码错误，请确保文件为UTF-8编码: {e}")],
                warnings=[]
            )
        except Exception as e:
            return ParseResult(
                success=False,
                data=None,
                errors=[ParseError(f"解析文件失败: {e}")],
                warnings=[]
            )
    
    def parse_content(self, content: str) -> ParseResult:
        """解析.pulse文件内容
        
        Args:
            content: 文件内容字符串
            
        Returns:
            ParseResult: 解析结果
        """
        context = ParserContext()
        
        try:
            # 检查文件格式标识符
            if not content.startswith(self._constants.FILE_FORMAT_PREFIX):
                context.add_error(f"不是有效的.pulse文件格式，应以'{self._constants.FILE_FORMAT_PREFIX}'开头")
                return ParseResult.from_context(context)
            
            # 分离头部和小节数据
            parts = content.split("=", 1)
            if len(parts) != 2:
                context.add_error("文件格式错误：缺少波形描述部分")
                return ParseResult.from_context(context)
            
            header_str, sections_str = parts
            
            # 解析头部
            header = self._parse_header(header_str, context)
            if context.has_errors():
                return ParseResult.from_context(context)
            
            # 解析小节
            sections = self._parse_sections(sections_str, context)
            
            if not sections:
                context.add_warning("文件中没有有效的小节数据")
            
            # 确保header不为None
            if header is None:
                context.add_error("解析头部失败")
                return ParseResult.from_context(context)
                
            data = PulseFileData(header=header, sections=sections)
            return ParseResult.from_context(context, data)
            
        except Exception as e:
            context.add_error(f"解析内容时发生异常: {e}")
            return ParseResult.from_context(context)
    
    def _parse_header(self, header_str: str, context: ParserContext) -> Optional[PulseFileHeader]:
        """解析文件头部
        
        Args:
            header_str: 头部字符串
            context: 解析器上下文
            
        Returns:
            Optional[PulseFileHeader]: 解析成功时返回头部数据，失败时返回None
        """
        try:
            # 移除前缀
            if header_str.startswith(self._constants.FILE_FORMAT_PREFIX):
                header_str = header_str[len(self._constants.FILE_FORMAT_PREFIX):]
            
            # 解析参数
            params = header_str.split(",")
            if len(params) != 3:
                context.add_error(f"波形描述参数数量错误，期望3个参数，实际{len(params)}个")
                return None
            
            try:
                rest_duration_slider = int(params[0].strip())
                speed_multiplier = int(params[1].strip())
                unknown_param = int(params[2].strip())
            except ValueError as e:
                context.add_error(f"波形描述参数格式错误: {e}")
                return None
            
            # 转换休息时长为实际秒数（滑块值 * 0.1）
            rest_duration = rest_duration_slider * 0.1
            
            # 验证速度倍率
            if speed_multiplier not in self._constants.VALID_SPEED_MULTIPLIERS:
                context.add_error(f"无效的速度倍率: {speed_multiplier}，支持的值: {self._constants.VALID_SPEED_MULTIPLIERS}")
                return None
            
            return PulseFileHeader(
                rest_duration=rest_duration,
                speed_multiplier=speed_multiplier,
                unknown_param=unknown_param
            )
            
        except Exception as e:
            context.add_error(f"解析头部时发生异常: {e}")
            return None
    
    def _parse_sections(self, sections_str: str, context: ParserContext) -> List[PulseSection]:
        """解析小节数据
        
        Args:
            sections_str: 小节字符串
            context: 解析器上下文
            
        Returns:
            List[PulseSection]: 解析成功的小节列表
        """
        sections: List[PulseSection] = []
        
        # 按分隔符分割小节
        section_parts = sections_str.split(self._constants.SECTION_SEPARATOR)
        
        for i, section_str in enumerate(section_parts):
            section_str = section_str.strip()
            if not section_str:
                continue
                
            try:
                section = self._parse_section(section_str, i, context)
                if section is not None:
                    sections.append(section)
                
            except Exception as e:
                context.add_warning(f"解析第{i+1}个小节失败: {e}")
                continue
        
        return sections
    
    def _parse_section(self, section_str: str, section_index: int, context: ParserContext) -> Optional[PulseSection]:
        """解析单个小节
        
        Args:
            section_str: 小节字符串
            section_index: 小节索引
            context: 解析器上下文
            
        Returns:
            Optional[PulseSection]: 解析成功时返回小节数据，失败时返回None
        """
        # 分离基础参数和脉冲数据
        if self._constants.PULSE_DATA_SEPARATOR not in section_str:
            context.add_warning(f"小节{section_index+1}格式错误：缺少脉冲数据分隔符'{self._constants.PULSE_DATA_SEPARATOR}'")
            return None
        
        basic_params_str, pulse_data_str = section_str.split(self._constants.PULSE_DATA_SEPARATOR, 1)
        basic_params = [param.strip() for param in basic_params_str.split(",")]
        
        if len(basic_params) != 5:
            context.add_warning(f"小节{section_index+1}基础参数数量错误，期望5个参数，实际{len(basic_params)}个")
            return None
        
        try:
            freq_a = int(basic_params[0])
            freq_b = int(basic_params[1])
            section_duration_slider = int(basic_params[2])
            frequency_mode_value = int(basic_params[3])
            enabled = int(basic_params[4]) == 1
        except (ValueError, IndexError) as e:
            context.add_warning(f"小节{section_index+1}参数格式错误: {e}")
            return None
        
        # 验证频率滑块值范围
        if not (0 <= freq_a < len(self._constants.FREQ_SLIDER_VALUE_MAP)):
            context.add_warning(f"小节{section_index+1}频率A滑块值{freq_a}超出范围[0-{len(self._constants.FREQ_SLIDER_VALUE_MAP)-1}]")
        
        if not (0 <= freq_b < len(self._constants.FREQ_SLIDER_VALUE_MAP)):
            context.add_warning(f"小节{section_index+1}频率B滑块值{freq_b}超出范围[0-{len(self._constants.FREQ_SLIDER_VALUE_MAP)-1}]")
        
        # 验证小节时长滑块值范围
        if not (0 <= section_duration_slider < len(self._constants.SECTION_TIME_MAP)):
            context.add_warning(f"小节{section_index+1}时长滑块值{section_duration_slider}超出范围[0-{len(self._constants.SECTION_TIME_MAP)-1}]")
        
        # 验证频率模式
        try:
            frequency_mode = FrequencyMode(frequency_mode_value)
        except ValueError:
            context.add_warning(f"小节{section_index+1}频率模式{frequency_mode_value}无效，使用固定模式")
            frequency_mode = FrequencyMode.FIXED
        
        # 转换小节时长为实际秒数
        section_duration = self._slider_to_section_time(section_duration_slider)
        
        # 解析脉冲数据
        pulse_data = self._parse_pulse_data(pulse_data_str, section_index, context)
        
        return PulseSection(
            freq_a=freq_a,
            freq_b=freq_b,
            section_duration=section_duration,
            frequency_mode=frequency_mode,
            enabled=enabled,
            pulse_data=pulse_data
        )
    
    def _parse_pulse_data(self, pulse_data_str: str, section_index: int, context: ParserContext) -> List[PulseDataItem]:
        """解析脉冲数据
        
        Args:
            pulse_data_str: 脉冲数据字符串
            section_index: 小节索引
            context: 解析器上下文
            
        Returns:
            List[PulseDataItem]: 解析成功的脉冲数据列表
        """
        pulse_data: List[PulseDataItem] = []
        
        if not pulse_data_str.strip():
            return pulse_data
        
        items = pulse_data_str.split(self._constants.PULSE_ITEM_SEPARATOR)
        
        for item_index, item in enumerate(items):
            item = item.strip()
            if not item:
                continue
            
            if self._constants.PULSE_ITEM_INTERNAL_SEPARATOR not in item:
                context.add_warning(f"小节{section_index+1}脉冲数据项{item_index+1}格式错误: {item}，缺少分隔符'{self._constants.PULSE_ITEM_INTERNAL_SEPARATOR}'")
                continue
            
            try:
                intensity_str, pulse_type_str = item.split(self._constants.PULSE_ITEM_INTERNAL_SEPARATOR, 1)
                # 强度值可能是浮点数格式（如100.00），需要先转换为float再转为int
                intensity = int(float(intensity_str.strip()))
                pulse_type = int(pulse_type_str.strip())
                
                # 验证强度范围
                if not (self._constants.INTENSITY_MIN <= intensity <= self._constants.INTENSITY_MAX):
                    context.add_warning(f"小节{section_index+1}脉冲数据项{item_index+1}强度值{intensity}超出范围[{self._constants.INTENSITY_MIN}-{self._constants.INTENSITY_MAX}]")
                    intensity = max(self._constants.INTENSITY_MIN, min(self._constants.INTENSITY_MAX, intensity))
                
                pulse_data.append(PulseDataItem(
                    intensity=intensity,
                    pulse_type=pulse_type
                ))
                
            except ValueError as e:
                context.add_warning(f"小节{section_index+1}脉冲数据项{item_index+1}格式错误: {item}, {e}")
                continue
        
        return pulse_data
    
    def _slider_to_frequency(self, slider_value: FrequencySliderValue) -> FrequencyInputValue:
        """将频率滑块值转换为实际频率输入值（毫秒）
        
        Args:
            slider_value: 频率滑块值 (0-83)
            
        Returns:
            FrequencyInputValue: 频率输入值 (10-1000ms)
        """
        if 0 <= slider_value < len(self._constants.FREQ_SLIDER_VALUE_MAP):
            return self._constants.FREQ_SLIDER_VALUE_MAP[slider_value]
        else:
            # 超出范围时使用边界值
            if slider_value < 0:
                return self._constants.FREQ_SLIDER_VALUE_MAP[0]
            else:
                return self._constants.FREQ_SLIDER_VALUE_MAP[-1]
    
    def _input_value_to_protocol_value(self, input_value: FrequencyInputValue) -> ProtocolFrequencyValue:
        """将频率输入值转换为协议频率值
        
        根据协议文档，将输入值范围(10~1000)转换为波形频率协议值(10~240)
        
        协议转换算法：
        - 10-100: 直接使用输入值
        - 101-600: (输入值 - 100)/5 + 100
        - 601-1000: (输入值 - 600)/10 + 200
        
        Args:
            input_value: 频率输入值(10-1000)，来自.pulse文件的频率滑块映射
            
        Returns:
            ProtocolFrequencyValue: 协议频率值(10-240)
        """
        # 限制输入范围
        input_value = max(10, min(1000, input_value))
        
        # 根据协议算法转换
        if 10 <= input_value <= 100:
            protocol_value = input_value
        elif 101 <= input_value <= 600:
            protocol_value = int((input_value - 100) / 5) + 100
        elif 601 <= input_value <= 1000:
            protocol_value = int((input_value - 600) / 10) + 200
        else:
            protocol_value = 10
        
        # 确保在有效范围内
        return max(self._constants.PROTOCOL_FREQ_MIN, min(self._constants.PROTOCOL_FREQ_MAX, protocol_value))
    
    def _validate_protocol_range(self, protocol_value: ProtocolFrequencyValue) -> ProtocolFrequencyValue:
        """验证并限制协议频率值在有效范围内
        
        Args:
            protocol_value: 协议频率值
            
        Returns:
            ProtocolFrequencyValue: 限制后的协议频率值
        """
        return max(self._constants.PROTOCOL_FREQ_MIN, min(self._constants.PROTOCOL_FREQ_MAX, protocol_value))
    
    def _slider_to_section_time(self, slider_value: SectionTimeSliderValue) -> float:
        """将小节时长滑块值转换为实际时长（秒）
        
        Args:
            slider_value: 小节时长滑块值 (0-99)
            
        Returns:
            float: 实际时长（秒）
        """
        if 0 <= slider_value < len(self._constants.SECTION_TIME_MAP):
            return self._constants.SECTION_TIME_MAP[slider_value]
        else:
            # 超出范围时使用边界值
            if slider_value < 0:
                return self._constants.SECTION_TIME_MAP[0]
            else:
                return self._constants.SECTION_TIME_MAP[-1]
    
    def convert_to_pulse_operations(self, header: PulseFileHeader, sections: List[PulseSection]) -> List[PulseOperation]:
        """将解析的数据转换为PulseOperation列表
        
        Args:
            header: 文件头部信息
            sections: 小节列表
            
        Returns:
            List[PulseOperation]: 转换后的波形操作列表
        """
        pulse_operations: List[PulseOperation] = []
        
        for section in sections:
            if not section.enabled:
                continue
            
            # 根据频率模式生成脉冲操作
            section_operations = self._generate_section_operations(section, header.speed_multiplier)
            pulse_operations.extend(section_operations)
        
        return pulse_operations
    
    def _generate_section_operations(self, section: PulseSection, speed_multiplier: SpeedMultiplier) -> List[PulseOperation]:
        """为单个小节生成脉冲操作
        
        根据郊狼App格式，小节时长控制脉冲元的重复播放时间。
        脉冲元总是会重复完整个循环之后再停止。
        
        speed_multiplier的作用：
        - 1: 正常速度播放（100ms为一个脉冲，对应PulseOperation的4个25ms子步骤）
        - 2: 2倍速播放（50ms为一个脉冲，对应PulseOperation的2个25ms子步骤）
        - 4: 4倍速播放（25ms为一个脉冲，对应PulseOperation的1个25ms子步骤）
        
        Args:
            section: 脉冲小节信息
            speed_multiplier: 速度倍率
            
        Returns:
            List[PulseOperation]: 小节的脉冲操作列表
        """
        operations: List[PulseOperation] = []
        
        # 1. 验证速度倍率
        if speed_multiplier not in self._constants.VALID_SPEED_MULTIPLIERS:
            raise ValueError(f"无效的速度倍率: {speed_multiplier}，可接受值为{self._constants.VALID_SPEED_MULTIPLIERS}")
        
        # 2. 计算脉冲元的实际长度（根据脉冲数据和速度倍率）
        pulse_element_duration = self._calculate_pulse_element_duration(section.pulse_data, speed_multiplier)
        
        # 3. 计算循环次数（向上取整）
        cycles = math.ceil(section.section_duration / pulse_element_duration)
        
        # 4. 根据频率模式生成操作
        if section.frequency_mode == FrequencyMode.ELEMENT_INTER_GRADIENT:
            # 元间渐变：需要为每个脉冲元计算不同的频率
            operations = self._generate_element_inter_gradient_operations(section, cycles, speed_multiplier)
        else:
            # 其他模式：生成单个脉冲元然后重复
            for cycle in range(cycles):
                pulse_element_operations = self._generate_pulse_element_operations(section, speed_multiplier, cycle, cycles)
                operations.extend(pulse_element_operations)
        
        # 5. 截取到精确的小节时长（转换为100ms步数）
        target_steps = int(section.section_duration * 10)
        operations = operations[:target_steps]
        
        return operations
    
    def _generate_element_inter_gradient_operations(self, section: PulseSection, cycles: int, speed_multiplier: SpeedMultiplier) -> List[PulseOperation]:
        """生成元间渐变模式的操作
        
        元间渐变：第一个脉冲元到最后一个脉冲元从频率A渐变到频率B
        
        Args:
            section: 脉冲小节信息
            cycles: 循环次数
            speed_multiplier: 速度倍率
            
        Returns:
            List[PulseOperation]: 元间渐变的脉冲操作列表
        """
        all_operations: List[PulseOperation] = []
        
        for cycle in range(cycles):
            # 计算当前脉冲元的频率（在频率A和频率B之间渐变）
            if cycles > 1:
                progress = cycle / (cycles - 1)
                current_frequency = self._interpolate_frequency(section.freq_a, section.freq_b, progress)
            else:
                current_frequency = self._convert_frequency_to_protocol(section.freq_a)
            
            # 生成当前脉冲元的操作
            pulse_element_operations = self._generate_pulse_element_operations_with_frequency(
                section, current_frequency, speed_multiplier, cycle, cycles
            )
            all_operations.extend(pulse_element_operations)
        
        return all_operations
    
    def _generate_pulse_element_operations_with_frequency(
        self, 
        section: PulseSection, 
        frequency: ProtocolFrequencyValue, 
        speed_multiplier: SpeedMultiplier, 
        cycle_index: int = 0, 
        total_cycles: int = 1
    ) -> List[PulseOperation]:
        """使用指定频率生成脉冲元操作
        
        Args:
            section: 脉冲小节信息
            frequency: 指定的协议频率值
            speed_multiplier: 速度倍率
            cycle_index: 当前循环索引
            total_cycles: 总循环次数
            
        Returns:
            List[PulseOperation]: 脉冲元操作列表
        """
        if not section.pulse_data:
            # 如果没有脉冲数据，生成默认的脉冲元
            return self._generate_default_pulse_operations(frequency, speed_multiplier)
        
        # 根据脉冲数据和速度倍率生成操作
        operations: List[PulseOperation] = []
        
        for pulse_index in range(len(section.pulse_data)):
            # 根据速度倍率决定是否生成PulseOperation
            if self._should_generate_operation(pulse_index, speed_multiplier):
                # 获取压缩后的脉冲数据项
                compressed_items = self._get_compressed_pulse_items(section.pulse_data, pulse_index, speed_multiplier)
                
                # 创建PulseOperation（使用指定频率）
                operation = self._create_pulse_operation_from_items(frequency, compressed_items)
                operations.append(operation)
        
        return operations
    
    def _calculate_pulse_element_duration(self, pulse_data: List[PulseDataItem], speed_multiplier: SpeedMultiplier) -> float:
        """计算脉冲元的实际长度（秒）
        
        根据郊狼App格式，脉冲元由最少两根"竖条"组成，
        每根竖条代表0.1s的输出强度，也就是每个脉冲元的最短长度为0.2秒。
        
        speed_multiplier影响播放速度：
        - 1: 正常速度，每个脉冲数据项代表0.1秒
        - 2: 2倍速，每个脉冲数据项代表0.05秒（50ms）
        - 4: 4倍速，每个脉冲数据项代表0.025秒（25ms）
        
        Args:
            pulse_data: 脉冲数据列表
            speed_multiplier: 速度倍率
            
        Returns:
            float: 脉冲元实际长度（秒）
        """
        if not pulse_data:
            return self._constants.MIN_PULSE_ELEMENT_DURATION / speed_multiplier
        
        # 根据速度倍率计算每个脉冲数据项的时间
        time_per_item = self._constants.BASE_TIME_PER_ITEM / speed_multiplier
        
        return len(pulse_data) * time_per_item
    
    def _generate_pulse_element_operations(
        self, 
        section: PulseSection, 
        speed_multiplier: SpeedMultiplier, 
        cycle_index: int = 0, 
        total_cycles: int = 1
    ) -> List[PulseOperation]:
        """生成单个脉冲元的操作列表
        
        speed_multiplier决定每个脉冲数据项对应多少个PulseOperation：
        - 1: 每个脉冲数据项对应1个PulseOperation（100ms）
        - 2: 每个脉冲数据项对应0.5个PulseOperation（50ms）
        - 4: 每个脉冲数据项对应0.25个PulseOperation（25ms）
        
        Args:
            section: 脉冲小节信息
            speed_multiplier: 速度倍率
            cycle_index: 当前脉冲元索引（用于元间渐变）
            total_cycles: 总脉冲元数量（用于元间渐变）
            
        Returns:
            List[PulseOperation]: 脉冲元操作列表
        """
        if not section.pulse_data:
            # 如果没有脉冲数据，生成默认的脉冲元
            input_value = self._slider_to_frequency(section.freq_a)
            protocol_value = self._input_value_to_protocol_value(input_value)
            frequency = self._validate_protocol_range(protocol_value)
            
            return self._generate_default_pulse_operations(frequency, speed_multiplier)
        
        # 根据脉冲数据和速度倍率生成操作
        return self._generate_pulse_operations_from_data(section, speed_multiplier, cycle_index, total_cycles)
    
    def _generate_default_pulse_operations(self, frequency: ProtocolFrequencyValue, speed_multiplier: SpeedMultiplier) -> List[PulseOperation]:
        """生成默认脉冲元操作（无脉冲数据时）
        
        Args:
            frequency: 协议频率值
            speed_multiplier: 速度倍率
            
        Returns:
            List[PulseOperation]: 默认脉冲元操作列表
        """
        operations: List[PulseOperation] = []
        
        # 根据速度倍率生成操作（默认脉冲元长度为0.2秒）
        if speed_multiplier == 1:
            # 生成2个100ms步骤（0.2秒）
            for _ in range(2):
                operations.append(self._create_pulse_operation(frequency, 0))
        elif speed_multiplier == 2:
            # 生成4个50ms步骤（0.2秒）
            for _ in range(4):
                operations.append(self._create_pulse_operation(frequency, 0))
        elif speed_multiplier == 4:
            # 生成8个25ms步骤（0.2秒）
            for _ in range(8):
                operations.append(self._create_pulse_operation(frequency, 0))
        
        return operations
    
    def _generate_pulse_operations_from_data(
        self, 
        section: PulseSection, 
        speed_multiplier: SpeedMultiplier, 
        cycle_index: int = 0, 
        total_cycles: int = 1
    ) -> List[PulseOperation]:
        """根据脉冲数据生成操作
        
        Args:
            section: 脉冲小节信息
            speed_multiplier: 速度倍率
            cycle_index: 当前循环索引
            total_cycles: 总循环次数
            
        Returns:
            List[PulseOperation]: 脉冲操作列表
        """
        operations: List[PulseOperation] = []
        
        for pulse_index, pulse_item in enumerate(section.pulse_data):
            # 根据速度倍率决定是否生成PulseOperation
            if self._should_generate_operation(pulse_index, speed_multiplier):
                # 获取压缩后的脉冲数据项
                compressed_items = self._get_compressed_pulse_items(section.pulse_data, pulse_index, speed_multiplier)
                
                # 根据频率模式创建PulseOperation
                if section.frequency_mode == FrequencyMode.ELEMENT_GRADIENT:
                    # 元内渐变：使用特殊的创建方法
                    operation = self._create_pulse_operation_with_element_gradient(section, compressed_items, speed_multiplier)
                else:
                    # 其他模式：根据频率模式计算频率
                    frequency = self._calculate_pulse_frequency(section, pulse_item, pulse_index, cycle_index, total_cycles)
                    operation = self._create_pulse_operation_from_items(frequency, compressed_items)
                
                operations.append(operation)
        
        return operations
    
    def _should_generate_operation(self, pulse_index: int, speed_multiplier: SpeedMultiplier) -> bool:
        """判断是否应该生成PulseOperation
        
        Args:
            pulse_index: 脉冲索引
            speed_multiplier: 速度倍率
            
        Returns:
            bool: 是否应该生成操作
        """
        if speed_multiplier == 1:
            return True  # 每个脉冲数据项都生成
        elif speed_multiplier == 2:
            return pulse_index % 2 == 0  # 每2个脉冲数据项生成1个
        elif speed_multiplier == 4:
            return pulse_index % 4 == 0  # 每4个脉冲数据项生成1个
        return False
    
    def _get_compressed_pulse_items(
        self, 
        pulse_data: List[PulseDataItem], 
        start_index: int, 
        speed_multiplier: SpeedMultiplier
    ) -> List[PulseDataItem]:
        """获取压缩后的脉冲数据项
        
        Args:
            pulse_data: 脉冲数据列表
            start_index: 起始索引
            speed_multiplier: 速度倍率
            
        Returns:
            List[PulseDataItem]: 压缩后的脉冲数据项列表
        """
        if speed_multiplier == 1:
            return [pulse_data[start_index]]
        elif speed_multiplier == 2:
            # 获取2个脉冲数据项
            items = pulse_data[start_index:start_index + 2]
            if len(items) < 2:
                items.append(pulse_data[start_index])  # 用当前项填充
            return items
        elif speed_multiplier == 4:
            # 获取4个脉冲数据项
            items = pulse_data[start_index:start_index + 4]
            while len(items) < 4:
                items.append(pulse_data[start_index])  # 用当前项填充
            return items
        return [pulse_data[start_index]]
    
    def _create_pulse_operation(self, frequency: ProtocolFrequencyValue, intensity: IntensityValue) -> PulseOperation:
        """创建单个PulseOperation
        
        Args:
            frequency: 协议频率值
            intensity: 强度值
            
        Returns:
            PulseOperation: 脉冲操作
        """
        freq_tuple: WaveformFrequencyOperation = (frequency, frequency, frequency, frequency)
        intensity_tuple: WaveformStrengthOperation = (intensity, intensity, intensity, intensity)
        return (freq_tuple, intensity_tuple)
    
    def _create_pulse_operation_from_items(
        self, 
        frequency: ProtocolFrequencyValue, 
        items: List[PulseDataItem]
    ) -> PulseOperation:
        """从脉冲数据项列表创建PulseOperation
        
        Args:
            frequency: 协议频率值
            items: 脉冲数据项列表
            
        Returns:
            PulseOperation: 脉冲操作
        """
        freq_tuple: WaveformFrequencyOperation = (frequency, frequency, frequency, frequency)
        intensity_tuple: WaveformStrengthOperation = (
            items[0].intensity if len(items) > 0 else 0,
            items[1].intensity if len(items) > 1 else 0,
            items[2].intensity if len(items) > 2 else 0,
            items[3].intensity if len(items) > 3 else 0
        )
        return (freq_tuple, intensity_tuple)
    
    def _create_pulse_operation_with_element_gradient(
        self, 
        section: PulseSection, 
        items: List[PulseDataItem], 
        speed_multiplier: SpeedMultiplier
    ) -> PulseOperation:
        """创建带有元内渐变的PulseOperation
        
        元内渐变：在PulseOperation的4个25ms子步骤内从频率A渐变到频率B
        根据速度倍率决定渐变的子步骤数量：
        - speed_multiplier=1: 4个子步骤都参与渐变
        - speed_multiplier=2: 2个子步骤参与渐变
        - speed_multiplier=4: 1个子步骤，无法渐变
        
        Args:
            section: 脉冲小节信息
            items: 脉冲数据项列表
            speed_multiplier: 速度倍率
            
        Returns:
            PulseOperation: 带元内渐变的脉冲操作
        """
        # 根据速度倍率确定参与渐变的子步骤数量
        if speed_multiplier == 1:
            gradient_steps = 4
        elif speed_multiplier == 2:
            gradient_steps = 2
        elif speed_multiplier == 4:
            gradient_steps = 1
        else:
            gradient_steps = 4
        
        # 计算渐变频率
        freq_a_protocol = self._convert_frequency_to_protocol(section.freq_a)
        freq_b_protocol = self._convert_frequency_to_protocol(section.freq_b)
        
        if gradient_steps == 1:
            # 无法渐变，使用固定频率
            freq_tuple: WaveformFrequencyOperation = (freq_a_protocol, freq_a_protocol, freq_a_protocol, freq_a_protocol)
        else:
            # 生成渐变频率
            frequencies: List[int] = []
            for i in range(4):
                if i < gradient_steps:
                    progress = i / (gradient_steps - 1) if gradient_steps > 1 else 0
                    freq = int(freq_a_protocol + (freq_b_protocol - freq_a_protocol) * progress)
                    freq = self._validate_protocol_range(freq)
                else:
                    # 超出渐变步数的部分使用最后一个渐变值
                    progress = 1.0
                    freq = int(freq_a_protocol + (freq_b_protocol - freq_a_protocol) * progress)
                    freq = self._validate_protocol_range(freq)
                frequencies.append(freq)
            freq_tuple = (frequencies[0], frequencies[1], frequencies[2], frequencies[3])
        
        # 强度元组
        intensity_tuple: WaveformStrengthOperation = (
            items[0].intensity if len(items) > 0 else 0,
            items[1].intensity if len(items) > 1 else 0,
            items[2].intensity if len(items) > 2 else 0,
            items[3].intensity if len(items) > 3 else 0
        )
        
        return (freq_tuple, intensity_tuple)
    
    def _calculate_pulse_frequency(
        self, 
        section: PulseSection, 
        pulse_item: PulseDataItem, 
        pulse_index: int, 
        cycle_index: int = 0, 
        total_cycles: int = 1
    ) -> ProtocolFrequencyValue:
        """计算单个脉冲的频率（返回协议频率值10-240）
        
        Args:
            section: 脉冲小节信息
            pulse_item: 脉冲数据项
            pulse_index: 脉冲索引
            cycle_index: 循环索引
            total_cycles: 总循环次数
            
        Returns:
            ProtocolFrequencyValue: 协议频率值
        """
        # 根据频率模式计算频率
        total_pulses = len(section.pulse_data) if section.pulse_data else 1
        return self._calculate_section_frequency_with_mode(
            section, pulse_index, total_pulses, cycle_index, total_cycles
        )
    
    def _calculate_section_frequency_with_mode(
        self, 
        section: PulseSection, 
        pulse_index: int, 
        total_pulses: int, 
        cycle_index: int = 0, 
        total_cycles: int = 1, 
        global_pulse_index: int = 0, 
        total_section_pulses: int = 1
    ) -> ProtocolFrequencyValue:
        """根据频率模式计算脉冲频率（返回协议频率值10-240）
        
        Args:
            section: 脉冲小节信息
            pulse_index: 当前脉冲在脉冲元中的索引
            total_pulses: 脉冲元中的总脉冲数
            cycle_index: 当前脉冲元的循环索引
            total_cycles: 总循环数
            global_pulse_index: 当前脉冲在整个小节中的全局索引
            total_section_pulses: 整个小节的总脉冲数
            
        Returns:
            ProtocolFrequencyValue: 协议频率值
        """
        if section.frequency_mode == FrequencyMode.FIXED:
            # 固定模式：使用频率A
            return self._convert_frequency_to_protocol(section.freq_a)
        
        elif section.frequency_mode == FrequencyMode.SECTION_GRADIENT:
            # 节内渐变：在整个小节的持续时间内从频率A渐变到频率B
            # 跨越所有重复的脉冲元，从小节开始到小节结束
            if total_section_pulses > 1:
                progress = global_pulse_index / (total_section_pulses - 1)
            else:
                progress = 0
            return self._interpolate_frequency(section.freq_a, section.freq_b, progress)
        
        elif section.frequency_mode == FrequencyMode.ELEMENT_GRADIENT:
            # 元内渐变：每个脉冲元内部从频率A渐变到频率B（周期性变化）
            # 在每个脉冲元的持续时间内进行渐变，多个脉冲元重复这个周期
            pulse_element_length = len(section.pulse_data) if section.pulse_data else 1
            if pulse_element_length > 1:
                # 计算当前脉冲在脉冲元中的相对位置
                element_pulse_index = pulse_index % pulse_element_length
                progress = element_pulse_index / (pulse_element_length - 1)
                return self._interpolate_frequency(section.freq_a, section.freq_b, progress)
            else:
                return self._convert_frequency_to_protocol(section.freq_a)
        
        elif section.frequency_mode == FrequencyMode.ELEMENT_INTER_GRADIENT:
            # 元间渐变：每个脉冲元内部频率固定，但不同脉冲元之间从频率A渐变到频率B
            # 第一个脉冲元到最后一个脉冲元的频率渐变
            if total_cycles > 1:
                progress = cycle_index / (total_cycles - 1)
                return self._interpolate_frequency(section.freq_a, section.freq_b, progress)
            else:
                return self._convert_frequency_to_protocol(section.freq_a)
        
        else:
            return self._convert_frequency_to_protocol(section.freq_a)
    
    def _convert_frequency_to_protocol(self, freq_slider: FrequencySliderValue) -> ProtocolFrequencyValue:
        """将频率滑块值转换为协议频率值
        
        Args:
            freq_slider: 频率滑块值
            
        Returns:
            ProtocolFrequencyValue: 协议频率值
        """
        input_value = self._slider_to_frequency(freq_slider)
        protocol_value = self._input_value_to_protocol_value(input_value)
        return self._validate_protocol_range(protocol_value)
    
    def _interpolate_frequency(self, freq_a_slider: FrequencySliderValue, freq_b_slider: FrequencySliderValue, progress: float) -> ProtocolFrequencyValue:
        """在两个频率之间进行插值计算
        
        Args:
            freq_a_slider: 频率A滑块值
            freq_b_slider: 频率B滑块值
            progress: 插值进度 (0.0-1.0)
            
        Returns:
            ProtocolFrequencyValue: 插值后的协议频率值
        """
        freq_a_input = self._slider_to_frequency(freq_a_slider)
        freq_b_input = self._slider_to_frequency(freq_b_slider)
        interpolated_input = int(freq_a_input + (freq_b_input - freq_a_input) * progress)
        protocol_value = self._input_value_to_protocol_value(interpolated_input)
        return self._validate_protocol_range(protocol_value)
