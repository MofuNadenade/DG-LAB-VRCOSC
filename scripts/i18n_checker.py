#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地化文件一致性检查工具

此脚本用于检查不同语言的本地化文件是否保持一致：
- 键的数量是否相同
- 键的顺序是否一致
- 是否存在重复键
- 是否有缺失的键
"""

from ruamel.yaml import YAML
yaml = YAML()
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple

# 确保能找到项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
LOCALES_DIR = PROJECT_ROOT / 'src' / 'locales'

def get_ordered_keys(file_path: Path) -> List[str]:
    """获取YAML文件的键，保持原始顺序"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.load(f)  # type: ignore
    except Exception as e:
        print(f"❌ 无法读取文件 {file_path}: {e}")
        return []
    
    def extract_keys_ordered(obj: Any, prefix: str = '') -> List[str]:
        keys: List[str] = []
        if isinstance(obj, dict):
            for key in obj.keys():  # type: ignore
                full_key = f'{prefix}.{key}' if prefix else key  # type: ignore
                keys.append(full_key)  # type: ignore
                if isinstance(obj[key], dict):
                    keys.extend(extract_keys_ordered(obj[key], full_key))  # type: ignore
        return keys
    
    return extract_keys_ordered(data)

def check_duplicates(keys: List[str], lang_name: str) -> bool:
    """检查重复键"""
    duplicates: List[str] = []
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    
    if duplicates:
        print(f'❌ {lang_name}文件有重复键: {duplicates}')
        return False
    else:
        print(f'✅ {lang_name}文件无重复键')
        return True

def check_missing_keys(zh_keys: List[str], en_keys: List[str], ja_keys: List[str]) -> bool:
    """检查缺失的键"""
    zh_set = set(zh_keys)
    en_set = set(en_keys)
    ja_set = set(ja_keys)
    
    all_keys = zh_set | en_set | ja_set
    
    missing_in_zh = all_keys - zh_set
    missing_in_en = all_keys - en_set
    missing_in_ja = all_keys - ja_set
    
    has_missing = False
    
    if missing_in_zh:
        print(f'❌ 中文文件缺失键: {sorted(missing_in_zh)}')
        has_missing = True
    
    if missing_in_en:
        print(f'❌ 英文文件缺失键: {sorted(missing_in_en)}')
        has_missing = True
    
    if missing_in_ja:
        print(f'❌ 日文文件缺失键: {sorted(missing_in_ja)}')
        has_missing = True
    
    if not has_missing:
        print('✅ 所有文件都包含相同的键')
    
    return not has_missing

def show_order_differences(zh_keys: List[str], en_keys: List[str], ja_keys: List[str], show_details: bool = False) -> Tuple[int, List[Dict[str, Any]]]:
    """显示顺序差异"""
    print('\n=== 按顺序对比所有键 ===')
    
    if show_details:
        print('序号 | 中文键 | 英文键 | 日文键 | 状态')
        print('-' * 100)
    
    inconsistent_count = 0
    inconsistent_details: List[Dict[str, Any]] = []
    
    for i, (zh_key, en_key, ja_key) in enumerate(zip(zh_keys, en_keys, ja_keys), 1):
        if zh_key == en_key == ja_key:
            status = '✅'
            if show_details:
                # 截断过长的键名以便显示
                zh_display = zh_key[:25] + '...' if len(zh_key) > 25 else zh_key
                en_display = en_key[:25] + '...' if len(en_key) > 25 else en_key
                ja_display = ja_key[:25] + '...' if len(ja_key) > 25 else ja_key
                print(f'{i:3d} | {zh_display:27} | {en_display:27} | {ja_display:27} | {status}')
        else:
            status = '❌'
            inconsistent_count += 1
            inconsistent_details.append({
                'index': i,
                'zh_key': zh_key,
                'en_key': en_key,
                'ja_key': ja_key
            })
            
            if show_details:
                zh_display = zh_key[:25] + '...' if len(zh_key) > 25 else zh_key
                en_display = en_key[:25] + '...' if len(en_key) > 25 else en_key
                ja_display = ja_key[:25] + '...' if len(ja_key) > 25 else ja_key
                print(f'{i:3d} | {zh_display:27} | {en_display:27} | {ja_display:27} | {status}')
                
                # 显示完整的键名
                print(f'    中文: {zh_key}')
                print(f'    英文: {en_key}')
                print(f'    日文: {ja_key}')
                print()
    
    return inconsistent_count, inconsistent_details

def main() -> None:
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='检查本地化文件一致性')
    parser.add_argument('--details', '-d', action='store_true', 
                       help='显示详细的键对比信息')
    parser.add_argument('--issues-only', '-i', action='store_true',
                       help='只显示不一致的键')
    
    args = parser.parse_args()
    
    # 检查本地化文件是否存在
    zh_file = LOCALES_DIR / 'zh.yml'
    en_file = LOCALES_DIR / 'en.yml'
    ja_file = LOCALES_DIR / 'ja.yml'
    
    for file_path in [zh_file, en_file, ja_file]:
        if not file_path.exists():
            print(f'❌ 文件不存在: {file_path}')
            sys.exit(1)
    
    print('🔍 开始检查本地化文件一致性...\n')
    
    # 获取所有语言文件的键，保持顺序
    print('📖 读取本地化文件...')
    zh_keys = get_ordered_keys(zh_file)
    en_keys = get_ordered_keys(en_file)
    ja_keys = get_ordered_keys(ja_file)
    
    if not zh_keys or not en_keys or not ja_keys:
        print('❌ 无法读取某些本地化文件')
        sys.exit(1)
    
    print('=== 键数量统计 ===')
    print(f'中文 (zh.yml): {len(zh_keys)} 个键')
    print(f'英文 (en.yml): {len(en_keys)} 个键')
    print(f'日文 (ja.yml): {len(ja_keys)} 个键')
    
    # 检查长度是否一致
    if len(zh_keys) == len(en_keys) == len(ja_keys):
        print('✅ 键数量一致')
    else:
        print('❌ 键数量不一致')
    
    print('\n=== 重复键检查 ===')
    zh_no_dup = check_duplicates(zh_keys, '中文')
    en_no_dup = check_duplicates(en_keys, '英文')
    ja_no_dup = check_duplicates(ja_keys, '日文')
    
    print('\n=== 缺失键检查 ===')
    no_missing = check_missing_keys(zh_keys, en_keys, ja_keys)
    
    # 初始化变量
    inconsistent_count = 0
    inconsistent_details = []
    
    # 只有在键数量一致时才检查顺序
    if len(zh_keys) == len(en_keys) == len(ja_keys):
        inconsistent_count, inconsistent_details = show_order_differences(
            zh_keys, en_keys, ja_keys, args.details and not args.issues_only
        )
        
        if args.issues_only and inconsistent_details:
            print('\n=== 不一致的键详情 ===')
            for detail in inconsistent_details:
                print(f'第 {detail["index"]} 个键不一致:')
                print(f'  中文: {detail["zh_key"]}')
                print(f'  英文: {detail["en_key"]}')
                print(f'  日文: {detail["ja_key"]}')
                print()
        
        print('\n=== 总结 ===')
        if inconsistent_count == 0:
            print('🎉 所有键的顺序完全一致！')
        else:
            print(f'⚠️  发现 {inconsistent_count} 个键顺序不一致')
    
    # YAML格式验证
    print('\n=== YAML格式验证 ===')
    try:
        for file_path, lang in [(zh_file, '中文'), (en_file, '英文'), (ja_file, '日文')]:
            yaml.load(open(file_path, 'r', encoding='utf-8'))  # type: ignore
            print(f'✅ {lang}文件格式正确')
        print('所有语言文件格式验证完成')
    except Exception as e:
        print(f'❌ YAML格式验证失败: {e}')
        sys.exit(1)
    
    # 返回退出码
    all_good = (
        len(zh_keys) == len(en_keys) == len(ja_keys) and
        zh_no_dup and en_no_dup and ja_no_dup and
        no_missing and
        (inconsistent_count == 0)
    )
    
    if all_good:
        print('\n🎉 所有检查通过！本地化文件完全一致。')
        sys.exit(0)
    else:
        print('\n⚠️  发现一些问题，请修复后重新检查。')
        sys.exit(1)

if __name__ == '__main__':
    main()
