# Build System Documentation

This directory contains the optimized build system for DG-LAB-VRCOSC with dynamic version generation and cross-platform support.

## Quick Start

### Windows
```batch
# Quick build
scripts\build.bat

# Full build with clean
scripts\build.bat --clean

# Development mode
python scripts\dev_build.py --watch
```

### Linux/macOS
```bash
# Quick build
./scripts/build.sh

# Full build with clean
./scripts/build.sh --clean

# Development mode
python3 scripts/dev_build.py --watch
```

## Scripts Overview

### `generate_version.py`
Dynamic version generation based on git tags and commits.

**Features:**
- Automatic version detection from git tags
- Fallback to commit-based versioning
- Comprehensive build information
- Cross-platform support

**Usage:**
```bash
# Generate version file
python scripts/generate_version.py

# Check version without generating file
python scripts/generate_version.py --check

# Custom output location
python scripts/generate_version.py --output custom/path/version.py
```

### `build.py`
Main build script with full automation.

**Features:**
- Dependency management
- Type checking with pyright
- PyInstaller integration
- Resource bundling
- Build artifact management

**Usage:**
```bash
# Full build
python scripts/build.py

# Quick version-only build
python scripts/build.py --version-only

# Skip dependency installation
python scripts/build.py --no-deps

# Skip type checking
python scripts/build.py --no-typecheck

# Clean build
python scripts/build.py --clean

# Use direct PyInstaller (skip spec file)
python scripts/build.py --no-spec
```

### `dev_build.py`
Development build with file watching.

**Features:**
- Quick rebuild on file changes
- Auto version generation
- Development server mode
- File watching with automatic updates

**Usage:**
```bash
# Quick development build
python scripts/dev_build.py

# Development mode with file watching
python scripts/dev_build.py --watch
```

### `i18n_manager.py`
国际化管理工具，用于管理和维护多语言支持。这是一个功能完整的本地化键管理系统，支持分析、清理、重命名等操作。

**核心功能:**
- 📊 **智能分析**: 提取和分析代码中使用的本地化键，支持引用统计和热门键排行
- 🔍 **一致性检查**: 验证语言文件的一致性和完整性
- 🧹 **智能清理**: 清理未使用的键和空分组，支持预览模式
- ✏️ **智能编辑**: 重命名、移动和批量管理本地化键，支持父级键自动处理
- 📁 **引用管理**: 按文件分组显示本地化键使用情况，精确定位引用位置
- 🎯 **代码同步**: 智能更新代码中的键引用，支持父级键的所有子键自动更新

**支持的命令:**

#### 分析和检查命令
```bash
# 完整分析本地化键使用情况
python scripts/i18n_manager.py analyze

# 详细分析（显示源代码目录和语言文件信息）
python scripts/i18n_manager.py analyze --verbose

# 检查所有语言文件的键一致性
python scripts/i18n_manager.py check

# 列出代码中使用的所有键
python scripts/i18n_manager.py list-used

# 列出语言文件中定义的所有键
python scripts/i18n_manager.py list-defined

# 按文件分组显示本地化键使用情况
python scripts/i18n_manager.py list-by-file

# 查找未使用的键
python scripts/i18n_manager.py find-unused

# 分析键引用详情（查看特定键的所有引用位置）
python scripts/i18n_manager.py analyze-refs main.tabs

# 显示所有键引用统计和热门键排行
python scripts/i18n_manager.py analyze-refs
```

#### 清理命令
```bash
# 预览清理未使用的键（安全模式）
python scripts/i18n_manager.py --dry-run clean

# 执行清理未使用的键
python scripts/i18n_manager.py clean

# 预览清理空分组
python scripts/i18n_manager.py --dry-run clean-empty

# 执行清理空分组
python scripts/i18n_manager.py clean-empty
```

#### 键管理命令
```bash
# 重命名本地化键（预览模式）
python scripts/i18n_manager.py --dry-run rename old.key new.key --update-code

# 重命名键并同时更新代码中的引用
python scripts/i18n_manager.py rename old.key new.key --update-code

# 移动键到新分组
python scripts/i18n_manager.py move old.group.key new.group --update-code

# 批量重命名键（从YAML映射文件）
python scripts/i18n_manager.py batch-rename mapping.yml --update-code
```

#### 自定义配置
```bash
# 自定义源代码目录和语言文件
python scripts/i18n_manager.py analyze --src-dir custom/src --locales custom/zh.yml custom/en.yml custom/ja.yml

# 使用预览模式（所有修改操作都支持）
python scripts/i18n_manager.py --dry-run [command]
```

**批量重命名映射文件格式:**
```yaml
# mapping.yml
old.key.name: new.key.name
another.old.key: another.new.key
group.old.item: newgroup.item
```

#### 键引用分析命令
```bash
# 分析特定键或键前缀的所有引用
python scripts/i18n_manager.py analyze-refs main.tabs

# 查看单个键的详细引用信息
python scripts/i18n_manager.py analyze-refs pulse_editor.save_pulse

# 显示所有键的引用统计
python scripts/i18n_manager.py analyze-refs

# 查看前缀分组统计
python scripts/i18n_manager.py analyze-refs connection_tab
```

**高级功能:**
- 🔍 **智能键引用扫描**: 一次性扫描所有Python文件，建立完整的键引用映射
- 🎯 **父级键支持**: 移动父级键时自动处理所有子键（如移动 `main.tabs` 会自动更新 `main.tabs.*`）
- 📊 **引用统计分析**: 显示键使用频率、热门键排行和前缀分组统计
- 🔗 **精确位置定位**: 显示每个键在代码中的具体使用位置（文件、行号、代码行）

**安全特性:**
- 🛡️ **预览模式**: 所有修改操作默认支持 `--dry-run` 预览
- 🔄 **智能代码同步**: 支持同时更新代码中的键引用，包括父级键的所有子键
- ✅ **一致性检查**: 确保所有语言文件保持同步
- 📋 **详细报告**: 提供完整的操作结果和统计信息
- 🎯 **精确替换**: 避免误替换相似键名，按键长度排序处理

#### 实际使用示例

**场景1: 重组标签页键结构**
```bash
# 1. 先分析当前的键引用情况
python scripts/i18n_manager.py analyze-refs main.tabs

# 2. 预览移动操作（智能处理所有子键）
python scripts/i18n_manager.py --dry-run move main.tabs ui.tabs --update-code

# 3. 执行移动操作
python scripts/i18n_manager.py move main.tabs ui.tabs --update-code

# 4. 验证结果
python scripts/i18n_manager.py check
```

**场景2: 批量重组键结构**
```bash
# 创建映射文件 reorganize.yml
# main.title: ui.app.title
# main.settings: ui.settings
# main.action: ui.action

# 执行批量重命名
python scripts/i18n_manager.py batch-rename reorganize.yml --update-code
```

**场景3: 清理和优化**
```bash
# 1. 查找未使用的键
python scripts/i18n_manager.py find-unused

# 2. 清理未使用的键
python scripts/i18n_manager.py clean

# 3. 清理空分组
python scripts/i18n_manager.py clean-empty

# 4. 最终验证
python scripts/i18n_manager.py analyze --verbose
```

#### 性能和最佳实践

**性能特性:**
- ⚡ **一次扫描多次使用**: 智能缓存键引用映射，避免重复文件读取
- 🚀 **批量处理优化**: 按文件分组处理，减少I/O操作
- 💾 **内存高效**: 流式处理大型项目，支持数千个键的管理
- 🔧 **增量更新**: 只更新实际发生变化的文件

**最佳实践建议:**
1. **重构前先分析**: 使用 `analyze-refs` 了解键的使用情况
2. **始终预览**: 使用 `--dry-run` 预览所有修改操作
3. **分步进行**: 大规模重构时分批处理，便于回滚
4. **保持备份**: 重要操作前备份语言文件
5. **验证一致性**: 操作后使用 `check` 命令验证文件一致性

**故障排除:**
```bash
# 检查键引用不一致
python scripts/i18n_manager.py analyze-refs problematic.key

# 验证语言文件完整性
python scripts/i18n_manager.py check

# 查看详细的使用统计
python scripts/i18n_manager.py analyze --verbose

# 清理孤立的键和空分组
python scripts/i18n_manager.py clean-empty
```

#### 快速参考

**常用命令速查:**
| 命令 | 功能 | 示例 |
|------|------|------|
| `analyze` | 分析键使用情况 | `python scripts/i18n_manager.py analyze` |
| `analyze-refs` | 分析键引用详情 | `python scripts/i18n_manager.py analyze-refs main` |
| `check` | 检查文件一致性 | `python scripts/i18n_manager.py check` |
| `move` | 移动键到新分组 | `python scripts/i18n_manager.py move old.key new --update-code` |
| `rename` | 重命名键 | `python scripts/i18n_manager.py rename old.key new.key --update-code` |
| `clean` | 清理未使用的键 | `python scripts/i18n_manager.py --dry-run clean` |
| `clean-empty` | 清理空分组 | `python scripts/i18n_manager.py clean-empty` |
| `batch-rename` | 批量重命名 | `python scripts/i18n_manager.py batch-rename mapping.yml --update-code` |

**重要参数:**
- `--dry-run`: 预览模式，不执行实际修改
- `--update-code`: 同时更新代码中的键引用
- `--verbose`: 显示详细信息
- `--src-dir`: 指定源代码目录
- `--locales`: 指定语言文件列表

### `i18n_checker.py`
国际化文件一致性检查工具，专门用于验证多语言文件的完整性和一致性。

**Features:**
- 检查键的数量是否相同
- 检查键的顺序是否一致
- 检查是否存在重复键
- 检查是否有缺失的键
- YAML格式验证

**Usage:**
```bash
# 基本一致性检查
python scripts/i18n_checker.py

# 显示详细的键对比信息
python scripts/i18n_checker.py --details

# 只显示不一致的键
python scripts/i18n_checker.py --issues-only
```

### Platform Scripts
- `build.bat` - Windows batch script
- `build.sh` - Unix/Linux/macOS shell script

## Version System

### Version Format
- **Tagged release**: `v1.0.0`
- **Development**: `v1.0.0-20250820-1159-abc123`

### Version Components
- `VERSION`: Full version string
- `VERSION_SHORT`: Tag-only version (e.g., `v1.0.0`)
- `BUILD_INFO`: Comprehensive build metadata

### Build Information
The generated `version.py` includes:
```python
BUILD_INFO = {
    "version": "v0.1.1-20250820-1159-ad723d1",
    "commit_hash": "ad723d13a4e47ee4814bcd7c5cf55384838fe743",
    "commit_short": "ad723d1",
    "branch": "master",
    "commit_date": "2025-08-20 11:48:48 +0800",
    "build_time": "2025-08-20T11:59:05.711136",
    "python_version": "3.13.0 (...)",
    "platform": "win32"
}
```

## PyInstaller Configuration

### Spec File Features
- Optimized module inclusion/exclusion
- Proper resource bundling
- UPX compression support
- Single-file executable generation

### Included Resources
- Application icon (`src/icon/fish-cake.ico`)
- Translation files (`src/locales/`)
- Version information
- Build metadata

### Build Artifacts
After successful build, `dist/` contains:
- `DG-LAB-VRCOSC.exe` - Main executable
- `version.txt` - Version information
- `build-info.json` - Detailed build metadata

## GitHub Actions Integration

The build system integrates with GitHub Actions for:
- Automatic version generation
- Dependency caching
- Type checking
- Multi-platform builds
- Artifact publishing

### Workflow Features
- Fetch full git history for version generation
- Python 3.13 support
- pyright type checking
- Optimized PyInstaller builds
- Build artifact collection

## Development Workflow

### Local Development
1. Clone repository
2. Run `python scripts/dev_build.py --watch`
3. Edit code - version auto-updates
4. Test changes immediately

### Release Building
1. Create git tag: `git tag v1.0.0`
2. Run `python scripts/build.py --clean`
3. Test executable in `dist/`
4. Commit and push tag for CI build

### Continuous Integration
- Push to `master` triggers build
- Tag creation triggers release build
- Artifacts automatically uploaded

## Troubleshooting

### Common Issues

**Windows encoding errors:**
- Build scripts handle UTF-8 encoding automatically
- If issues persist, set `PYTHONIOENCODING=utf-8`

**Missing dependencies:**
- Run `pip install -r requirements.txt`
- Ensure PyInstaller is installed: `pip install pyinstaller`

**Version generation fails:**
- Check git is available and repository has history
- Ensure `scripts/generate_version.py` is executable

**Build artifacts missing:**
- Check `dist/` directory exists
- Verify PyInstaller completed successfully
- Check file permissions

### Debug Mode
Enable verbose output:
```bash
python scripts/build.py --no-typecheck --no-deps
```

### Clean Rebuild
Force clean build:
```bash
python scripts/build.py --clean
```

## Advanced Configuration

### Custom Build Options
Modify `DG-LAB-VRCOSC.spec` for:
- Additional resources
- Different compression settings
- Debug vs release builds
- Platform-specific options

### Version Customization
Edit `scripts/generate_version.py` for:
- Custom version format
- Additional build metadata
- Different fallback behavior
- Custom output templates

## Performance

### Build Optimization
- UPX compression enabled
- Excluded unnecessary modules
- Optimized resource bundling
- Cached dependency installation

### Build Times
- Version generation: ~1 second
- Type checking: ~5-10 seconds
- PyInstaller build: ~30-60 seconds
- Total clean build: ~2-3 minutes

## Security

### Build Security
- No credentials in build scripts
- Secure artifact handling
- Reproducible builds
- Version verification

### Code Signing
Add code signing to `DG-LAB-VRCOSC.spec`:
```python
codesign_identity="Developer ID Application: Your Name"
```