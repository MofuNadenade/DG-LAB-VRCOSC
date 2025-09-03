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
国际化管理工具，用于管理和维护多语言支持。

**Features:**
- 提取代码中使用的本地化键
- 提取语言文件中定义的键
- 查找未使用的本地化键
- 分析本地化键的使用情况
- 验证语言文件的一致性

**Usage:**
```bash
# 分析本地化键使用情况
python scripts/i18n_manager.py analyze

# 检查语言文件一致性
python scripts/i18n_manager.py check

# 列出代码中使用的所有键
python scripts/i18n_manager.py list-used

# 列出语言文件中定义的所有键
python scripts/i18n_manager.py list-defined

# 查找未使用的键
python scripts/i18n_manager.py find-unused

# 详细分析（包含更多信息）
python scripts/i18n_manager.py analyze --verbose

# 自定义源代码目录和语言文件
python scripts/i18n_manager.py analyze --src-dir custom/src --locales custom/zh.yml custom/en.yml
```

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