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

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

def flatten_dict(d: dict, parent_key: str = '', sep: str = '.') -> dict:
    """将嵌套字典扁平化为点分隔的键"""
    items: List[Tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def extract_keys_from_yaml(file_path: str) -> Set[str]:
    """从YAML文件中提取所有键"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml_loader.load(f)
            if data:
                flat_data = flatten_dict(data)
                return set(flat_data.keys())
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return set()

def extract_keys_from_file(file_path: str) -> Set[str]:
    """从单个Python文件中提取本地化键"""
    keys = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 匹配 _("key") 和 _('key') 模式
            pattern = r'_\(["\']([^"\']+)["\']\)'
            matches = re.findall(pattern, content)
            keys.update(matches)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return keys

def extract_used_keys(src_dir: str) -> Set[str]:
    """提取src目录下所有Python文件中使用的本地化键"""
    all_keys = set()
    
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                keys = extract_keys_from_file(file_path)
                all_keys.update(keys)
    
    return all_keys

def extract_defined_keys(locale_files: List[str]) -> Set[str]:
    """提取所有语言文件中定义的键"""
    all_defined_keys = set()
    
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

def print_usage_report(analysis: Dict[str, Any]):
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

def main():
    parser = argparse.ArgumentParser(description='本地化管理工具')
    parser.add_argument('--src-dir', default='src', help='源代码目录 (默认: src)')
    parser.add_argument('--locales', nargs='+', 
                       default=['src/locales/zh.yml', 'src/locales/en.yml', 'src/locales/ja.yml'],
                       help='语言文件路径列表')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 分析命令
    analyze_parser = subparsers.add_parser('analyze', help='分析本地化键使用情况')
    analyze_parser.add_argument('--verbose', '-v', action='store_true', help='显示详细信息')
    
    # 检查一致性命令
    check_parser = subparsers.add_parser('check', help='检查语言文件一致性')
    
    # 列出使用的键命令
    list_used_parser = subparsers.add_parser('list-used', help='列出代码中使用的所有键')
    
    # 列出定义的键命令
    list_defined_parser = subparsers.add_parser('list-defined', help='列出语言文件中定义的所有键')
    
    # 查找未使用的键命令
    find_unused_parser = subparsers.add_parser('find-unused', help='查找未使用的键')
    
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

if __name__ == "__main__":
    main()
