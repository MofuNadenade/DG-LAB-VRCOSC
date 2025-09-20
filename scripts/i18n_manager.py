#!/usr/bin/env python3
"""
本地化管理工具

功能包括：
1. 提取代码中使用的本地化键
2. 提取语言文件中定义的键
3. 查找未使用的本地化键
4. 分析本地化键的使用情况
5. 验证语言文件的一致性
"""

import re
import os
import sys
import argparse
from pathlib import Path
from typing import Set, Dict, List, Tuple, Any
from ruamel.yaml import YAML

yaml_loader = YAML(typ='safe')
yaml_writer = YAML()
yaml_writer.preserve_quotes = True
yaml_writer.default_flow_style = False

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """将嵌套字典扁平化为点分隔的键"""
    items: List[Tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())  # type: ignore
        else:
            items.append((new_key, v))
    return dict(items)

def extract_keys_from_yaml(file_path: str) -> Set[str]:
    """从YAML文件中提取所有键"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml_loader.load(f)  # type: ignore
            if data:
                flat_data = flatten_dict(data)  # type: ignore
                return set(flat_data.keys())
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return set()

def extract_keys_from_file(file_path: str) -> Set[str]:
    """从单个Python文件中提取本地化键"""
    keys: Set[str] = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 匹配 translate("key") 和 translate('key') 模式
            pattern = r'translate\(["\']([^"\']+)["\']\)'
            matches = re.findall(pattern, content)
            keys.update(matches)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return keys

def extract_used_keys(src_dir: str) -> Set[str]:
    """提取src目录下所有Python文件中使用的本地化键"""
    all_keys: Set[str] = set()
    
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                keys = extract_keys_from_file(file_path)
                all_keys.update(keys)
    
    return all_keys

def extract_defined_keys(locale_files: List[str]) -> Set[str]:
    """提取所有语言文件中定义的键"""
    all_defined_keys: Set[str] = set()
    
    for file_path in locale_files:
        if Path(file_path).exists():
            keys = extract_keys_from_yaml(file_path)
            all_defined_keys.update(keys)
    
    return all_defined_keys

def check_consistency(locale_files: List[str]) -> Tuple[bool, List[str]]:
    """检查所有语言文件的键是否一致"""
    errors: List[str] = []
    file_keys: Dict[str, Set[str]] = {}
    
    # 提取每个文件的键
    for file_path in locale_files:
        if Path(file_path).exists():
            file_keys[file_path] = extract_keys_from_yaml(file_path)
        else:
            errors.append(f"文件不存在: {file_path}")
    
    if len(file_keys) < 2:
        return True, errors
    
    # 比较键的一致性
    files = list(file_keys.keys())
    base_file = files[0]
    base_keys = file_keys[base_file]
    
    for other_file in files[1:]:
        other_keys = file_keys[other_file]
        
        # 检查缺失的键
        missing_in_other = base_keys - other_keys
        missing_in_base = other_keys - base_keys
        
        if missing_in_other:
            errors.append(f"{other_file} 缺少键: {sorted(missing_in_other)}")
        
        if missing_in_base:
            errors.append(f"{base_file} 缺少键: {sorted(missing_in_base)}")
    
    return len(errors) == 0, errors

def analyze_usage(src_dir: str, locale_files: List[str]) -> Dict[str, Any]:
    """分析本地化键的使用情况"""
    used_keys = extract_used_keys(src_dir)
    defined_keys = extract_defined_keys(locale_files)
    unused_keys = defined_keys - used_keys
    missing_keys = used_keys - defined_keys
    
    return {
        'used_keys': used_keys,
        'defined_keys': defined_keys,
        'unused_keys': unused_keys,
        'missing_keys': missing_keys,
        'total_used': len(used_keys),
        'total_defined': len(defined_keys),
        'total_unused': len(unused_keys),
        'total_missing': len(missing_keys)
    }

def print_usage_report(analysis: Dict[str, Any]) -> None:
    """打印使用情况报告"""
    print("=== 本地化键使用情况分析 ===")
    print(f"定义的键总数: {analysis['total_defined']}")
    print(f"使用的键总数: {analysis['total_used']}")
    print(f"未使用的键总数: {analysis['total_unused']}")
    print(f"缺失的键总数: {analysis['total_missing']}")
    
    if analysis['unused_keys']:
        print(f"\n=== 未使用的键 ({analysis['total_unused']} 个) ===")
        for key in sorted(analysis['unused_keys']):
            print(key)
    else:
        print("\n✅ 所有定义的键都被使用了！")
    
    if analysis['missing_keys']:
        print(f"\n=== 缺失的键 ({analysis['total_missing']} 个) ===")
        for key in sorted(analysis['missing_keys']):
            print(key)
    else:
        print("\n✅ 所有使用的键都已定义！")

def remove_keys_from_dict(data: Any, keys_to_remove: Set[str], parent_key: str = '') -> Dict[str, Any]:
    """从嵌套字典中移除指定的键"""
    result: Dict[str, Any] = {}

    for k, v in data.items():
        current_key = f"{parent_key}.{k}" if parent_key else k
        
        if current_key in keys_to_remove:
            continue  # 跳过要删除的键
        
        if isinstance(v, dict):
            # 递归处理嵌套字典
            nested_result = remove_keys_from_dict(v, keys_to_remove, current_key)
            if nested_result:  # 只有当嵌套字典不为空时才添加
                result[k] = nested_result
        else:
            result[k] = v
    
    return result

def clean_unused_keys(locale_files: List[str], unused_keys: Set[str], dry_run: bool = True) -> None:
    """清理未使用的键"""
    print(f"\n=== 清理未使用的键 ({'预览模式' if dry_run else '执行模式'}) ===")
    
    if not unused_keys:
        print("✅ 没有未使用的键需要清理！")
        return
    
    for locale_file in locale_files:
        print(f"\n处理文件: {locale_file}")
        
        try:
            # 读取原始数据
            with open(locale_file, 'r', encoding='utf-8') as f:
                original_data = yaml_writer.load(f)  # type: ignore
            
            if not original_data:
                print(f"  ⚠️ 文件为空，跳过")
                continue
            
            # 移除未使用的键
            cleaned_data = remove_keys_from_dict(original_data, unused_keys)
            
            # 计算移除的键数量
            original_keys = set(flatten_dict(original_data).keys())  # type: ignore
            removed_keys = original_keys & unused_keys
            
            if removed_keys:
                print(f"  将移除 {len(removed_keys)} 个键:")
                for key in sorted(removed_keys):
                    print(f"    - {key}")
                
                if not dry_run:
                    # 写入清理后的数据
                    with open(locale_file, 'w', encoding='utf-8') as f:
                        yaml_writer.dump(cleaned_data, f)  # type: ignore
                    print(f"  ✅ 已更新文件")
                else:
                    print(f"  📋 预览完成（移除 --dry-run 执行实际清理）")
            else:
                print(f"  ✅ 此文件中没有未使用的键")
                
        except Exception as e:
            print(f"  ❌ 处理文件时出错: {e}")
    
    if dry_run:
        print(f"\n📋 预览完成！要执行实际清理，请移除 --dry-run 参数")
    else:
        print(f"\n🎉 清理完成！已从所有语言文件中移除 {len(unused_keys)} 个未使用的键")

def main() -> None:
    parser = argparse.ArgumentParser(description='本地化管理工具')
    parser.add_argument('--src-dir', default='src', help='源代码目录 (默认: src)')
    parser.add_argument('--locales', nargs='+', 
                       default=['src/locales/zh.yml', 'src/locales/en.yml', 'src/locales/ja.yml'],
                       help='语言文件路径列表')
    parser.add_argument('--dry-run', action='store_true', help='预览模式，不执行实际修改')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 分析命令
    analyze_parser = subparsers.add_parser('analyze', help='分析本地化键使用情况')
    analyze_parser.add_argument('--verbose', '-v', action='store_true', help='显示详细信息')
    
    # 检查一致性命令
    subparsers.add_parser('check', help='检查语言文件一致性')
    
    # 列出使用的键命令
    subparsers.add_parser('list-used', help='列出代码中使用的所有键')
    
    # 列出定义的键命令
    subparsers.add_parser('list-defined', help='列出语言文件中定义的所有键')
    
    # 查找未使用的键命令
    subparsers.add_parser('find-unused', help='查找未使用的键')
    
    # 清理未使用的键命令
    subparsers.add_parser('clean', help='清理未使用的键')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 转换为绝对路径
    src_dir = os.path.abspath(args.src_dir)
    locale_files = [os.path.abspath(f) for f in args.locales]
    
    if args.command == 'analyze':
        analysis = analyze_usage(src_dir, locale_files)
        print_usage_report(analysis)
        
        if args.verbose:
            print(f"\n=== 详细信息 ===")
            print(f"源代码目录: {src_dir}")
            print(f"语言文件: {locale_files}")
    
    elif args.command == 'check':
        is_consistent, errors = check_consistency(locale_files)
        
        if is_consistent:
            print("✅ 所有语言文件的键都是一致的！")
        else:
            print("❌ 语言文件键不一致:")
            for error in errors:
                print(f"  - {error}")
    
    elif args.command == 'list-used':
        used_keys = extract_used_keys(src_dir)
        print(f"=== 代码中使用的本地化键 ({len(used_keys)} 个) ===")
        for key in sorted(used_keys):
            print(key)
    
    elif args.command == 'list-defined':
        defined_keys = extract_defined_keys(locale_files)
        print(f"=== 语言文件中定义的键 ({len(defined_keys)} 个) ===")
        for key in sorted(defined_keys):
            print(key)
    
    elif args.command == 'find-unused':
        analysis = analyze_usage(src_dir, locale_files)
        
        if analysis['unused_keys']:
            print(f"=== 未使用的键 ({analysis['total_unused']} 个) ===")
            for key in sorted(analysis['unused_keys']):
                print(key)
        else:
            print("✅ 所有键都被使用了！")
    
    elif args.command == 'clean':
        analysis = analyze_usage(src_dir, locale_files)
        
        if analysis['unused_keys']:
            clean_unused_keys(locale_files, analysis['unused_keys'], dry_run=args.dry_run)
        else:
            print("✅ 没有未使用的键需要清理！")

if __name__ == "__main__":
    main()
