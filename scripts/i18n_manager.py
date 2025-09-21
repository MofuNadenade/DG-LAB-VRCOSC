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

def extract_used_keys_by_file(src_dir: str) -> Dict[str, Set[str]]:
    """按文件分组提取src目录下所有Python文件中使用的本地化键"""
    file_keys: Dict[str, Set[str]] = {}
    
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                keys = extract_keys_from_file(file_path)
                if keys:  # 只记录有本地化键的文件
                    # 使用相对路径作为键，便于显示
                    relative_path = os.path.relpath(file_path, src_dir)
                    file_keys[relative_path] = keys
    
    return file_keys

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

def print_keys_by_file(file_keys: Dict[str, Set[str]]) -> None:
    """打印按文件分组的本地化键使用情况"""
    total_files = len(file_keys)
    total_keys = sum(len(keys) for keys in file_keys.values())
    
    print(f"=== 按文件分组的本地化键使用情况 ===")
    print(f"包含本地化键的文件数: {total_files}")
    print(f"使用的键总数: {total_keys}")
    
    if not file_keys:
        print("\n✅ 没有找到使用本地化键的文件！")
        return
    
    # 按文件路径排序
    for file_path in sorted(file_keys.keys()):
        keys = file_keys[file_path]
        print(f"\n📁 {file_path} ({len(keys)} 个键)")
        for key in sorted(keys):
            print(f"  - {key}")
    
    print(f"\n📊 统计信息:")
    print(f"  文件数量: {total_files}")
    print(f"  键总数: {total_keys}")
    if total_files > 0:
        print(f"  平均每文件: {total_keys / total_files:.1f} 个键")

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

def set_nested_value(data: Any, key_path: str, value: Any) -> None:
    """在嵌套字典中设置值"""
    keys = key_path.split('.')
    current = data
    
    # 导航到父级字典
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        elif not isinstance(current[key], dict):
            # 如果路径上的键已存在且不是字典，则无法继续
            raise ValueError(f"无法在路径 '{key_path}' 设置值：'{key}' 不是字典")
        current = current[key]
    
    # 设置最终值
    current[keys[-1]] = value

def get_nested_value(data: Any, key_path: str) -> Any:
    """从嵌套字典中获取值"""
    keys = key_path.split('.')
    current = data
    
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            raise KeyError(f"键 '{key_path}' 不存在")
        current = current[key]  # type: ignore
    
    return current  # type: ignore

def delete_nested_key(data: Any, key_path: str) -> bool:
    """从嵌套字典中删除键，返回是否成功删除"""
    keys = key_path.split('.')
    current = data
    
    # 导航到父级字典
    try:
        for key in keys[:-1]:
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]  # type: ignore
        
        # 删除最终键
        if isinstance(current, dict) and keys[-1] in current:
            del current[keys[-1]]
            return True
        return False
    except Exception:
        return False

def rename_key_in_files(locale_files: List[str], old_key: str, new_key: str, dry_run: bool = True) -> None:
    """在所有语言文件中重命名键"""
    print(f"\n=== 重命名键 {'(预览模式)' if dry_run else '(执行模式)'} ===")
    print(f"从: {old_key}")
    print(f"到: {new_key}")
    
    if old_key == new_key:
        print("❌ 新旧键名相同，无需重命名")
        return
    
    success_count = 0
    error_count = 0
    
    for locale_file in locale_files:
        if not Path(locale_file).exists():
            print(f"⚠️ 文件不存在，跳过: {locale_file}")
            continue
            
        try:
            # 读取文件
            with open(locale_file, 'r', encoding='utf-8') as f:
                data: Any = yaml_writer.load(f)  # type: ignore
            
            if not data or not isinstance(data, dict):
                print(f"⚠️ 文件为空或格式无效，跳过: {locale_file}")
                continue
            
            # 检查旧键是否存在
            try:
                value = get_nested_value(data, old_key)
            except KeyError:
                print(f"⚠️ 键 '{old_key}' 在文件 {locale_file} 中不存在")
                continue
            
            # 检查新键是否已存在
            try:
                get_nested_value(data, new_key)
                print(f"❌ 新键 '{new_key}' 在文件 {locale_file} 中已存在")
                error_count += 1
                continue
            except KeyError:
                pass  # 新键不存在，这是我们想要的
            
            print(f"📝 处理文件: {locale_file}")
            print(f"  值: {value}")
            
            if not dry_run:
                # 设置新键
                set_nested_value(data, new_key, value)
                # 删除旧键
                delete_nested_key(data, old_key)
                
                # 写回文件
                with open(locale_file, 'w', encoding='utf-8') as f:
                    yaml_writer.dump(data, f)  # type: ignore
                
                print(f"  ✅ 已重命名")
                success_count += 1
            else:
                print(f"  📋 预览：将重命名")
                
        except Exception as e:
            print(f"❌ 处理文件 {locale_file} 时出错: {e}")
            error_count += 1
    
    if dry_run:
        print(f"\n📋 预览完成！要执行实际重命名，请移除 --dry-run 参数")
    else:
        print(f"\n🎉 重命名完成！成功: {success_count}, 错误: {error_count}")

def move_key_to_group(locale_files: List[str], old_key: str, new_group: str, dry_run: bool = True) -> None:
    """将键移动到新的分组中，保持键名不变"""
    # 提取键的最后一部分作为新键名
    key_parts = old_key.split('.')
    key_name = key_parts[-1]
    new_key = f"{new_group}.{key_name}"
    
    print(f"\n=== 移动键到新分组 {'(预览模式)' if dry_run else '(执行模式)'} ===")
    print(f"从: {old_key}")
    print(f"到: {new_key}")
    
    rename_key_in_files(locale_files, old_key, new_key, dry_run)

def batch_rename_keys(locale_files: List[str], mapping_file: str, dry_run: bool = True) -> None:
    """批量重命名键，从映射文件读取重命名规则"""
    print(f"\n=== 批量重命名键 {'(预览模式)' if dry_run else '(执行模式)'} ===")
    
    if not Path(mapping_file).exists():
        print(f"❌ 映射文件不存在: {mapping_file}")
        return
    
    try:
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mappings: Any = yaml_loader.load(f)  # type: ignore
        
        if not mappings or not isinstance(mappings, dict):
            print("❌ 映射文件为空或格式无效")
            return
        
        # 类型转换为字典
        mappings_dict: Dict[str, str] = {}
        for k, v in mappings.items():  # type: ignore
            if isinstance(k, str) and isinstance(v, str):
                mappings_dict[k] = v
            else:
                print(f"⚠️ 跳过无效的映射: {k} -> {v}")
        
        print(f"📖 从 {mapping_file} 读取到 {len(mappings_dict)} 个有效重命名规则")
        
        success_count = 0
        for old_key, new_key in mappings_dict.items():
            print(f"\n--- 处理: {old_key} -> {new_key} ---")
            try:
                rename_key_in_files(locale_files, old_key, new_key, dry_run)
                success_count += 1
            except Exception as e:
                print(f"❌ 重命名失败: {e}")
        
        print(f"\n🎉 批量重命名完成！处理了 {success_count}/{len(mappings_dict)} 个键")
        
    except Exception as e:
        print(f"❌ 读取映射文件时出错: {e}")

def clean_empty_groups(locale_files: List[str], dry_run: bool = True) -> None:
    """清理语言文件中的空分组"""
    print(f"\n=== 清理空分组 {'(预览模式)' if dry_run else '(执行模式)'} ===")
    
    total_cleaned = 0
    
    for locale_file in locale_files:
        if not Path(locale_file).exists():
            print(f"⚠️ 文件不存在，跳过: {locale_file}")
            continue
            
        try:
            # 读取文件
            with open(locale_file, 'r', encoding='utf-8') as f:
                data: Any = yaml_writer.load(f)  # type: ignore
            
            if not data or not isinstance(data, dict):
                print(f"⚠️ 文件为空或格式无效，跳过: {locale_file}")
                continue
            
            print(f"\n📝 处理文件: {locale_file}")
            
            # 递归清理空组
            cleaned_data, removed_count = remove_empty_groups(data)
            
            if removed_count > 0:
                print(f"  将清理 {removed_count} 个空分组")
                total_cleaned += removed_count
                
                if not dry_run:
                    # 写回文件
                    with open(locale_file, 'w', encoding='utf-8') as f:
                        yaml_writer.dump(cleaned_data, f)  # type: ignore
                    print(f"  ✅ 已清理")
                else:
                    print(f"  📋 预览完成")
            else:
                print(f"  ✅ 没有空分组需要清理")
                
        except Exception as e:
            print(f"❌ 处理文件 {locale_file} 时出错: {e}")
    
    if dry_run:
        print(f"\n📋 预览完成！共发现 {total_cleaned} 个空分组。要执行实际清理，请移除 --dry-run 参数")
    else:
        print(f"\n🎉 清理完成！共清理了 {total_cleaned} 个空分组")

def remove_empty_groups(data: Any) -> Tuple[Any, int]:
    """递归移除空分组，返回清理后的数据和移除的分组数量"""
    if not isinstance(data, dict):
        return data, 0
    
    result = {}
    removed_count = 0
    
    for key, value in data.items():  # type: ignore
        if isinstance(value, dict):
            if len(value) == 0:  # type: ignore
                # 空字典，跳过（不添加到结果中）
                removed_count += 1
                print(f"    - 移除空分组: {key}")
            else:
                # 递归处理嵌套字典
                cleaned_value, nested_removed = remove_empty_groups(value)
                removed_count += nested_removed
                
                # 如果清理后仍然不为空，则保留
                if isinstance(cleaned_value, dict) and len(cleaned_value) > 0:  # type: ignore
                    result[key] = cleaned_value
                elif not isinstance(cleaned_value, dict):
                    result[key] = cleaned_value
                else:
                    # 清理后变为空字典，移除
                    removed_count += 1
                    print(f"    - 移除清理后变空的分组: {key}")
        else:
            # 非字典值，直接保留
            result[key] = value
    
    return result, removed_count  # type: ignore

def find_all_key_references(src_dir: str) -> Dict[str, List[Tuple[str, int, str]]]:
    """扫描所有Python文件，找出所有translate调用及其位置
    
    Returns:
        Dict[key, List[Tuple[file_path, line_number, full_line]]]
    """
    import re
    
    key_references: Dict[str, List[Tuple[str, int, str]]] = {}
    
    # 匹配translate调用的正则表达式
    translate_pattern = re.compile(r'translate\(["\']([^"\']+)["\']\)')
    
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    for line_num, line in enumerate(lines, 1):
                        matches = translate_pattern.findall(line)
                        for key in matches:
                            if key not in key_references:
                                key_references[key] = []
                            relative_path = os.path.relpath(file_path, src_dir)
                            key_references[key].append((relative_path, line_num, line.strip()))
                            
                except Exception as e:
                    print(f"⚠️ 读取文件 {file_path} 时出错: {e}")
    
    return key_references

def update_code_references_smart(src_dir: str, old_key: str, new_key: str, dry_run: bool = True) -> None:
    """智能更新代码中的键引用，支持父级键重命名"""
    print(f"\n=== 智能更新代码引用 {'(预览模式)' if dry_run else '(执行模式)'} ===")
    print(f"从: {old_key}")
    print(f"到: {new_key}")
    
    # 首先扫描所有键引用
    print("🔍 扫描代码中的所有键引用...")
    all_references = find_all_key_references(src_dir)
    
    # 找出需要更新的键
    keys_to_update: List[Tuple[str, str]] = []
    
    # 1. 精确匹配
    if old_key in all_references:
        keys_to_update.append((old_key, new_key))
    
    # 2. 前缀匹配（处理父级键重命名）
    old_key_prefix = old_key + "."
    new_key_prefix = new_key + "."
    
    for key in all_references:
        if key.startswith(old_key_prefix):
            # 计算新的键名
            suffix = key[len(old_key_prefix):]
            new_full_key = new_key_prefix + suffix
            keys_to_update.append((key, new_full_key))
    
    if not keys_to_update:
        print(f"ℹ️ 没有找到对键 '{old_key}' 或其子键的引用")
        return
    
    print(f"📋 找到 {len(keys_to_update)} 个需要更新的键:")
    for old_k, new_k in keys_to_update:
        ref_count = len(all_references[old_k])
        print(f"  • {old_k} → {new_k} ({ref_count} 处引用)")
    
    # 按文件分组更新
    files_to_update: Dict[str, List[Tuple[str, str]]] = {}
    
    for old_k, new_k in keys_to_update:
        for file_path, _, _ in all_references[old_k]:
            full_file_path = os.path.join(src_dir, file_path)
            if full_file_path not in files_to_update:
                files_to_update[full_file_path] = []
            files_to_update[full_file_path].append((old_k, new_k))
    
    # 执行文件更新
    updated_files = 0
    total_replacements = 0
    
    for file_path, key_pairs in files_to_update.items():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = content
            file_replacements = 0
            
            # 按键长度降序排序，避免短键替换长键的问题
            key_pairs.sort(key=lambda x: len(x[0]), reverse=True)
            
            for old_k, new_k in key_pairs:
                # 精确替换
                patterns = [
                    (f'translate("{old_k}")', f'translate("{new_k}")'),
                    (f"translate('{old_k}')", f"translate('{new_k}')"),
                ]
                
                for old_pattern, new_pattern in patterns:
                    if old_pattern in new_content:
                        count = new_content.count(old_pattern)
                        new_content = new_content.replace(old_pattern, new_pattern)
                        file_replacements += count
            
            if file_replacements > 0:
                relative_path = os.path.relpath(file_path, src_dir)
                print(f"📝 {relative_path}: {file_replacements} 处替换")
                
                if not dry_run:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                
                updated_files += 1
                total_replacements += file_replacements
                
        except Exception as e:
            print(f"❌ 处理文件 {file_path} 时出错: {e}")
    
    if dry_run:
        print(f"\n📋 预览完成！将在 {updated_files} 个文件中进行 {total_replacements} 处替换")
    else:
        print(f"\n✅ 更新完成！在 {updated_files} 个文件中进行了 {total_replacements} 处替换")

def update_code_references(src_dir: str, old_key: str, new_key: str, dry_run: bool = True) -> None:
    """更新代码中的键引用（兼容性包装）"""
    update_code_references_smart(src_dir, old_key, new_key, dry_run)

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
    
    # 按文件列出使用的键命令
    subparsers.add_parser('list-by-file', help='按文件分组列出使用的本地化键')
    
    # 分析键引用命令
    ref_parser = subparsers.add_parser('analyze-refs', help='分析键引用详情')
    ref_parser.add_argument('key_pattern', nargs='?', help='键模式（可选，支持前缀匹配）')
    
    # 查找未使用的键命令
    subparsers.add_parser('find-unused', help='查找未使用的键')
    
    # 清理未使用的键命令
    subparsers.add_parser('clean', help='清理未使用的键')
    
    # 清理空组命令
    subparsers.add_parser('clean-empty', help='清理空的分组')
    
    # 重命名键命令
    rename_parser = subparsers.add_parser('rename', help='重命名本地化键')
    rename_parser.add_argument('old_key', help='旧键名')
    rename_parser.add_argument('new_key', help='新键名')
    rename_parser.add_argument('--update-code', action='store_true', help='同时更新代码中的引用')
    
    # 移动键到新分组命令
    move_parser = subparsers.add_parser('move', help='移动键到新分组')
    move_parser.add_argument('old_key', help='要移动的键')
    move_parser.add_argument('new_group', help='目标分组')
    move_parser.add_argument('--update-code', action='store_true', help='同时更新代码中的引用')
    
    # 批量重命名命令
    batch_parser = subparsers.add_parser('batch-rename', help='批量重命名键')
    batch_parser.add_argument('mapping_file', help='包含重命名映射的YAML文件')
    batch_parser.add_argument('--update-code', action='store_true', help='同时更新代码中的引用')
    
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
    
    elif args.command == 'list-by-file':
        file_keys = extract_used_keys_by_file(src_dir)
        print_keys_by_file(file_keys)
    
    elif args.command == 'analyze-refs':
        all_references = find_all_key_references(src_dir)
        
        if args.key_pattern:
            # 过滤匹配的键
            filtered_refs: Dict[str, List[Tuple[str, int, str]]] = {}
            pattern: str = args.key_pattern
            for key, refs in all_references.items():
                if key == pattern or key.startswith(pattern + "."):
                    filtered_refs[key] = refs
            
            if filtered_refs:
                print(f"=== 键引用分析: {pattern} ===")
                for key in sorted(filtered_refs.keys()):
                    refs = filtered_refs[key]
                    print(f"\n🔑 {key} ({len(refs)} 处引用)")
                    for file_path, line_num, line_content in refs:
                        print(f"  📄 {file_path}:{line_num} - {line_content}")
            else:
                print(f"❌ 没有找到匹配 '{pattern}' 的键引用")
        else:
            # 显示所有键的统计
            print(f"=== 所有键引用统计 ===")
            print(f"总键数: {len(all_references)}")
            
            # 按引用次数排序
            sorted_keys = sorted(all_references.items(), key=lambda x: len(x[1]), reverse=True)
            
            print(f"\n📊 引用次数最多的前10个键:")
            for i, (key, refs) in enumerate(sorted_keys[:10], 1):
                print(f"{i:2d}. {key} ({len(refs)} 处)")
            
            print(f"\n📊 按前缀分组统计:")
            prefix_stats: Dict[str, int] = {}
            for key in all_references:
                if '.' in key:
                    prefix = key.split('.')[0]
                    prefix_stats[prefix] = prefix_stats.get(prefix, 0) + 1
            
            for prefix in sorted(prefix_stats.keys()):
                count = prefix_stats[prefix]
                print(f"  {prefix}.*: {count} 个键")
    
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
    
    elif args.command == 'clean-empty':
        clean_empty_groups(locale_files, dry_run=args.dry_run)
    
    elif args.command == 'rename':
        rename_key_in_files(locale_files, args.old_key, args.new_key, dry_run=args.dry_run)
        
        if args.update_code:
            update_code_references(src_dir, args.old_key, args.new_key, dry_run=args.dry_run)
    
    elif args.command == 'move':
        move_key_to_group(locale_files, args.old_key, args.new_group, dry_run=args.dry_run)
        
        if args.update_code:
            # 计算新键名
            key_parts = args.old_key.split('.')
            key_name = key_parts[-1]
            new_key = f"{args.new_group}.{key_name}"
            update_code_references(src_dir, args.old_key, new_key, dry_run=args.dry_run)
    
    elif args.command == 'batch-rename':
        batch_rename_keys(locale_files, args.mapping_file, dry_run=args.dry_run)
        
        if args.update_code:
            # 对于批量重命名，需要读取映射文件并逐个更新代码引用
            try:
                with open(args.mapping_file, 'r', encoding='utf-8') as f:
                    mappings: Any = yaml_loader.load(f)  # type: ignore
                
                if mappings and isinstance(mappings, dict):
                    for k, v in mappings.items():  # type: ignore
                        if isinstance(k, str) and isinstance(v, str):
                            update_code_references(src_dir, k, v, dry_run=args.dry_run)
            except Exception as e:
                print(f"❌ 更新代码引用时出错: {e}")

if __name__ == "__main__":
    main()
