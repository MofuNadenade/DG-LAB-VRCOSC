"""
波形文件分析脚本

遍历 pulses/ 目录中的 .pulse 波形文件，使用 PulseFileParser 解析并输出结果。
用于批量分析和验证波形文件的格式和内容。
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加 src 目录到 Python 路径，以便导入模块
current_dir = Path(__file__).parent
src_dir = current_dir.parent / "src"
sys.path.insert(0, str(src_dir))

from core.official.pulse_file_parser import PulseFileParser
from core.official.pulse_file_models import ParseResult, PulseFileData, FrequencyMode


class PulseFileAnalyzer:
    """波形文件分析器
    
    用于批量分析 .pulse 波形文件，提供详细的解析结果和统计信息。
    """
    
    def __init__(self, pulses_directory: str = "pulses") -> None:
        """初始化分析器
        
        Args:
            pulses_directory: 包含 .pulse 文件的目录路径
        """
        super().__init__()
        self.pulses_directory = Path(pulses_directory)
        self.parser = PulseFileParser()
        self.results: List[Dict[str, Any]] = []
    
    def analyze_all_files(self) -> None:
        """分析所有 .pulse 文件"""
        if not self.pulses_directory.exists():
            print(f"错误：目录 {self.pulses_directory} 不存在")
            return
        
        # 查找所有 .pulse 文件
        pulse_files = list(self.pulses_directory.glob("*.pulse"))
        
        if not pulse_files:
            print(f"在目录 {self.pulses_directory} 中未找到 .pulse 文件")
            return
        
        print(f"找到 {len(pulse_files)} 个 .pulse 文件")
        print("=" * 80)
        
        for file_path in sorted(pulse_files):
            self.analyze_single_file(file_path)
        
        self.print_summary()
    
    def analyze_single_file(self, file_path: Path) -> None:
        """分析单个 .pulse 文件
        
        Args:
            file_path: .pulse 文件路径
        """
        print(f"\n📁 分析文件: {file_path.name}")
        print("-" * 60)
        
        try:
            # 解析文件
            result: ParseResult = self.parser.parse_file(str(file_path))
            
            # 记录结果
            file_result = {
                'file_name': file_path.name,
                'file_path': str(file_path),
                'success': result.success,
                'errors': result.errors,
                'warnings': result.warnings,
                'data': result.data
            }
            self.results.append(file_result)
            
            # 输出解析结果
            self._print_parse_result(file_result)
            
        except Exception as e:
            print(f"❌ 解析文件时发生异常: {e}")
            file_result = {
                'file_name': file_path.name,
                'file_path': str(file_path),
                'success': False,
                'errors': [f"解析异常: {e}"],
                'warnings': [],
                'data': None
            }
            self.results.append(file_result)
    
    def _print_parse_result(self, file_result: Dict[str, Any]) -> None:
        """打印单个文件的解析结果
        
        Args:
            file_result: 文件解析结果
        """
        if file_result['success']:
            print("✅ 解析成功")
            
            data: PulseFileData = file_result['data']
            header = data.header
            sections = data.sections
            
            # 输出头部信息
            print(f"📊 文件头部信息:")
            print(f"  - 休息时长: {header.rest_duration} 秒")
            print(f"  - 速度倍数: {header.speed_multiplier}")
            print(f"  - 未知参数: {header.unknown_param}")
            print(f"  - 小节数量: {len(sections)}")
            
            # 输出小节信息
            print(f"📋 小节详情:")
            for i, section in enumerate(sections, 1):
                status = "启用" if section.enabled else "禁用"
                pulse_count = len(section.pulse_data)
                
                # 频率模式名称映射
                mode_names = {
                    FrequencyMode.FIXED: "固定模式",
                    FrequencyMode.SECTION_GRADIENT: "节内渐变",
                    FrequencyMode.ELEMENT_GRADIENT: "元内渐变", 
                    FrequencyMode.ELEMENT_INTER_GRADIENT: "元间渐变"
                }
                mode_name = mode_names.get(section.frequency_mode, f"未知模式({section.frequency_mode})")
                
                print(f"  小节 {i}: {status}")
                print(f"    - 频率A: {section.freq_a}, 频率B: {section.freq_b}")
                print(f"    - 频率模式: {mode_name}")
                print(f"    - 小节时长: {section.section_duration} 秒")
                print(f"    - 脉冲数据项: {pulse_count}")
                
                # 显示前几个脉冲数据项
                if section.pulse_data:
                    print(f"    脉冲数据预览:")
                    for j, pulse_item in enumerate(section.pulse_data[:5]):  # 只显示前5个
                        print(f"      [{j+1}] 强度: {pulse_item.intensity}, 类型: {pulse_item.pulse_type}")
                    if len(section.pulse_data) > 5:
                        print(f"      ... 还有 {len(section.pulse_data) - 5} 个脉冲数据项")
            
            # 尝试转换为 PulseOperation
            try:
                operations = self.parser.convert_to_pulse_operations(header, sections)
                print(f"🔄 转换结果: 生成了 {len(operations)} 个 PulseOperation")
            except Exception as e:
                print(f"⚠️  转换为 PulseOperation 时出错: {e}")
        
        else:
            print("❌ 解析失败")
        
        # 输出错误信息
        if file_result['errors']:
            print(f"🚨 错误信息 ({len(file_result['errors'])} 个):")
            for error in file_result['errors']:
                if hasattr(error, 'message'):
                    print(f"  - {error.message}")
                else:
                    print(f"  - {error}")
        
        # 输出警告信息
        if file_result['warnings']:
            print(f"⚠️  警告信息 ({len(file_result['warnings'])} 个):")
            for warning in file_result['warnings']:
                if hasattr(warning, 'message'):
                    print(f"  - {warning.message}")
                else:
                    print(f"  - {warning}")
    
    def print_summary(self) -> None:
        """打印分析总结"""
        print("\n" + "=" * 80)
        print("📈 分析总结")
        print("=" * 80)
        
        total_files = len(self.results)
        successful_files = sum(1 for r in self.results if r['success'])
        failed_files = total_files - successful_files
        
        print(f"总文件数: {total_files}")
        print(f"成功解析: {successful_files}")
        print(f"解析失败: {failed_files}")
        print(f"成功率: {successful_files/total_files*100:.1f}%")
        
        # 统计错误和警告
        total_errors = sum(len(r['errors']) for r in self.results)
        total_warnings = sum(len(r['warnings']) for r in self.results)
        
        print(f"总错误数: {total_errors}")
        print(f"总警告数: {total_warnings}")
        
        # 显示失败的文件
        if failed_files > 0:
            print(f"\n❌ 解析失败的文件:")
            for result in self.results:
                if not result['success']:
                    print(f"  - {result['file_name']}")
        
        # 显示有警告的文件
        files_with_warnings = [r for r in self.results if r['warnings']]
        if files_with_warnings:
            print(f"\n⚠️  有警告的文件:")
            for result in files_with_warnings:
                print(f"  - {result['file_name']} ({len(result['warnings'])} 个警告)")


def main():
    """主函数"""
    print("🔍 波形文件分析器")
    print("=" * 80)
    
    # 创建分析器实例
    analyzer = PulseFileAnalyzer("pulses")
    
    # 执行分析
    analyzer.analyze_all_files()


if __name__ == "__main__":
    main()
