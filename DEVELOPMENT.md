# 开发指南

## 🛠️ 开发环境配置

### 系统要求
- Python 3.11+
- Windows 10/11 (主要支持平台)

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
├── core/          # 核心功能模块
├── gui/           # 用户界面
├── services/      # 服务层
└── app.py         # 主程序入口
```

## 🆘 获取帮助

- 查看项目Issues
- 提交新的Issue
- 联系项目维护者

---

**注意**: 本项目使用严格类型检查，请确保所有代码都通过pyright检查。
