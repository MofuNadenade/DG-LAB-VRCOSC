# 开发指南

## 🛠️ 开发环境配置

### 系统要求
- Python 3.11+
- Windows 10/11 (主要支持平台)
- 蓝牙适配器 (用于蓝牙直连功能)

### 环境搭建
```bash
# 1. 克隆项目
git clone https://github.com/MofuNadenade/DG-LAB-VRCOSC.git
cd DG-LAB-VRCOSC

# 2. 创建虚拟环境
python -m venv .venv

# 3. 激活虚拟环境
.venv\Scripts\activate.bat # Windows (Command Prompt)
# .venv\Scripts\Activate.ps1 # Windows (PowerShell)
# source .venv/bin/activate # Linux/Mac

# 4. 安装依赖
pip install -r requirements.txt

# 5. 运行类型检查
python -m pyright src/

# 6. 运行项目
python src/app.py
```

### 推荐IDE
- **VS Code**: 安装Python、Pyright扩展
- **PyCharm**: 专业Python IDE，内置类型检查

## 🚀 快速开始

### 运行开发版本
```bash
# 直接运行
python src/app.py
```

### 构建应用
```bash
# 构建可执行文件
python scripts/build.py

# 开发模式构建（支持文件监听）
python scripts/dev_build.py --watch

# 仅生成版本文件
python scripts/generate_version.py
```

### 开发脚本工具
```bash
# 国际化管理工具
python scripts/i18n_manager.py analyze      # 分析本地化键使用情况
python scripts/i18n_manager.py check        # 检查语言文件一致性
python scripts/i18n_manager.py find-unused  # 查找未使用的键

# 国际化文件检查
python scripts/i18n_checker.py              # 基本一致性检查
python scripts/i18n_checker.py --details    # 详细键对比信息

# 版本管理
python scripts/generate_version.py --check  # 检查版本信息
```

## 📝 代码规范

### 类型检查
- 使用 `pyright` 进行类型检查
- 所有函数必须包含类型注解
- 运行 `python -m pyright src/` 检查

### 代码质量检查
- 运行 `python scripts/i18n_manager.py analyze` 检查国际化完整性
- 运行 `python scripts/i18n_checker.py` 验证多语言文件一致性
- 使用 `python scripts/generate_version.py --check` 验证版本信息

### 代码结构
```
src/
├── core/                    # 核心功能模块
│   ├── bluetooth/          # 蓝牙直连核心实现
│   │   ├── bluetooth_controller.py    # 蓝牙控制器
│   │   ├── device_manager.py          # 设备管理器
│   │   └── protocol_handler.py        # 协议处理器
│   └── ...
├── gui/                     # 用户界面
│   ├── connection/         # 连接管理界面
│   │   ├── bluetooth/      # 蓝牙连接界面
│   │   └── websocket/      # WebSocket连接界面
│   └── ...
├── services/               # 服务层
│   ├── dglab_bluetooth_service.py    # 蓝牙设备服务
│   └── ...
└── app.py                  # 主程序入口
```

## 🔧 蓝牙直连开发

### 蓝牙架构说明
项目实现了完整的蓝牙直连功能，基于DG-LAB V3协议：

- **BluetoothController**: 核心蓝牙控制器，负责设备扫描、连接、数据通信
- **DGLabBluetoothService**: 蓝牙设备服务，实现IDGLabDeviceService接口
- **BluetoothConnectionManager**: 蓝牙连接管理器，处理UI交互
- **BluetoothConnectionWidget**: 蓝牙连接界面组件

### 开发调试
```bash
# 测试蓝牙功能
python src/test_bluetooth_client.py

# 查看蓝牙设备扫描日志
python src/app.py --debug-bluetooth
```

### 协议实现
- 基于官方V3协议文档实现B0、BF指令
- 支持强度控制、波形数据传输、设备参数设置
- 完整的错误处理和连接状态管理

## 🆘 获取帮助

- 查看项目Issues
- 提交新的Issue
- 联系项目维护者

---

**注意**: 本项目使用严格类型检查，请确保所有代码都通过pyright检查。
