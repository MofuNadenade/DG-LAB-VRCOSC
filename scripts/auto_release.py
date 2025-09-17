#!/usr/bin/env python3
"""
自动发布脚本
从git获取上一个版本标签，增加版本号，生成版本文件，创建发布提交和标签，并创建GitHub Release
"""

import argparse
import subprocess
import sys
import re
from pathlib import Path
from typing import List, Optional, Tuple


def run_command(cmd: List[str], capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    """运行命令并返回结果"""
    print(f"运行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=capture_output, text=True, cwd=get_project_root())
    if result.returncode != 0:
        print(f"命令执行失败: {result.stderr}")
        sys.exit(1)
    return result


def get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).parent.parent


def get_latest_tag() -> Optional[str]:
    """获取最新的版本标签"""
    try:
        result = run_command(['git', 'describe', '--tags', '--abbrev=0'])
        tag: str = result.stdout.strip()
        print(f"当前最新标签: {tag}")
        return tag
    except Exception:
        print("未找到任何标签，将从 v0.0.0 开始")
        return None


def parse_version(version_str: Optional[str]) -> Tuple[int, int, int]:
    """解析版本号字符串为 (major, minor, patch)"""
    if not version_str:
        return (0, 0, 0)
    
    # 移除 'v' 前缀
    if version_str.startswith('v'):
        version_str = version_str[1:]
    
    # 使用正则表达式解析版本号
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)', version_str)
    if not match:
        print(f"无法解析版本号: {version_str}")
        sys.exit(1)
    
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def increment_version(current: Tuple[int, int, int], bump_type: str) -> Tuple[int, int, int]:
    """根据类型增加版本号"""
    major, minor, patch = current
    
    if bump_type == 'major':
        return (major + 1, 0, 0)
    elif bump_type == 'minor':
        return (major, minor + 1, 0)
    elif bump_type == 'patch':
        return (major, minor, patch + 1)
    else:
        print(f"无效的版本增量类型: {bump_type}")
        sys.exit(1)


def format_version(version: Tuple[int, int, int]) -> str:
    """格式化版本号为字符串"""
    return f"v{version[0]}.{version[1]}.{version[2]}"


def check_git_status() -> None:
    """检查git状态，确保工作区干净"""
    result = run_command(['git', 'status', '--porcelain'])
    status_output: str = result.stdout.strip()
    if status_output:
        print("错误: 工作区有未提交的更改，请先提交或清理")
        print(status_output)
        sys.exit(1)
    print("工作区状态: 干净")


def generate_version_file() -> None:
    """调用generate_version.py生成版本文件"""
    print("生成版本文件...")
    script_path = get_project_root() / 'scripts' / 'generate_version.py'
    run_command([sys.executable, str(script_path)], capture_output=False)


def create_release_commit(new_version: str, message: Optional[str] = None) -> None:
    """创建发布提交"""
    if not message:
        message = f"Release {new_version}"
    
    print(f"创建发布提交: {message}")
    
    # 添加版本文件到暂存区
    run_command(['git', 'add', 'src/version.py'])
    
    # 检查是否有其他需要提交的文件
    result = run_command(['git', 'status', '--porcelain'])
    status_output: str = result.stdout.strip()
    if status_output:
        print("发现其他更改文件:")
        print(status_output)
        response = input("是否包含这些文件到发布提交中? (y/N): ").lower()
        if response == 'y':
            run_command(['git', 'add', '.'])
    
    # 创建提交
    run_command(['git', 'commit', '-m', message])


def create_git_tag(new_version: str, message: Optional[str] = None) -> None:
    """创建git标签"""
    if not message:
        message = f"Release {new_version}"
    
    print(f"创建标签: {new_version}")
    run_command(['git', 'tag', '-a', new_version, '-m', message])


def push_to_remote(push_tags: bool = True) -> None:
    """推送到远程仓库"""
    print("推送提交到远程仓库...")
    run_command(['git', 'push'])
    
    if push_tags:
        print("推送标签到远程仓库...")
        run_command(['git', 'push', '--tags'])


def build_application() -> bool:
    """构建应用程序"""
    print("构建应用程序 (使用 --clean)...")
    build_script = get_project_root() / 'scripts' / 'build.py'
    try:
        result = subprocess.run(
            [sys.executable, str(build_script), '--clean'],
            cwd=get_project_root(),
            text=True
        )
        if result.returncode == 0:
            print("✅ 应用程序构建成功")
            return True
        else:
            print(f"❌ 应用程序构建失败，退出码: {result.returncode}")
            return False
    except Exception as e:
        print(f"❌ 应用程序构建失败: {e}")
        return False


def create_github_release(version: str, previous_version: Optional[str] = None) -> bool:
    """使用GitHub CLI创建Release"""
    print(f"创建GitHub Release: {version}")
    
    # 构建变更日志URL
    if previous_version:
        changelog_url = f"**Full Changelog**: https://github.com/MofuNadenade/DG-LAB-VRCOSC/compare/{previous_version}...{version}"
    else:
        changelog_url = f"**Full Changelog**: https://github.com/MofuNadenade/DG-LAB-VRCOSC/commits/{version}"
    
    # 检查构建产物是否存在
    project_root = get_project_root()
    exe_path = project_root / 'dist' / 'DG-LAB-VRCOSC.exe'
    
    if not exe_path.exists():
        print(f"❌ 构建产物不存在: {exe_path}")
        return False
    
    try:
        # 创建Release
        cmd = [
            'gh', 'release', 'create', version,
            '--title', version,
            '--notes', changelog_url,
            str(exe_path)
        ]
        
        run_command(cmd, capture_output=False)
        print(f"✅ GitHub Release {version} 创建成功")
        return True
        
    except Exception as e:
        print(f"❌ GitHub Release创建失败: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description='自动发布脚本')
    parser.add_argument('bump_type', choices=['major', 'minor', 'patch'], 
                       help='版本增量类型 (major/minor/patch)')
    parser.add_argument('-m', '--message', help='发布提交信息')
    parser.add_argument('--no-push', action='store_true', help='不推送到远程仓库')
    parser.add_argument('--no-build', action='store_true', help='跳过应用程序构建')
    parser.add_argument('--no-release', action='store_true', help='不创建GitHub Release')
    parser.add_argument('--dry-run', action='store_true', help='模拟运行，不执行实际操作')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("== 模拟运行模式 ==")
    
    # 检查git状态
    if not args.dry_run:
        check_git_status()
    
    # 获取当前最新标签
    current_tag = get_latest_tag()
    current_version = parse_version(current_tag)
    print(f"当前版本: {format_version(current_version)}")
    
    # 计算新版本
    new_version_tuple = increment_version(current_version, args.bump_type)
    new_version = format_version(new_version_tuple)
    print(f"新版本: {new_version}")
    
    if args.dry_run:
        print("== 模拟运行结束 ==")
        return
    
    # 确认操作
    response = input(f"确认发布 {new_version}? (y/N): ").lower()
    if response != 'y':
        print("操作取消")
        return
    
    try:
        # 生成版本文件
        generate_version_file()
        
        # 创建发布提交
        create_release_commit(new_version, args.message)
        
        # 创建标签
        create_git_tag(new_version, args.message)
        
        # 构建应用程序
        if not args.no_build:
            if not build_application():
                print("❌ 构建失败，发布中止")
                sys.exit(1)
        
        # 推送到远程仓库
        if not args.no_push:
            push_to_remote()
        
        # 创建GitHub Release
        if not args.no_release:
            if not create_github_release(new_version, current_tag):
                print("⚠️ GitHub Release创建失败，但版本发布已完成")
        
        print(f"✅ 发布 {new_version} 完成!")
        
        if args.no_push:
            print("注意: 使用了 --no-push 选项，请手动推送:")
            print("  git push")
            print("  git push --tags")
        
        if args.no_release:
            print("注意: 使用了 --no-release 选项，请手动创建GitHub Release")
        
    except Exception as e:
        print(f"❌ 发布失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()