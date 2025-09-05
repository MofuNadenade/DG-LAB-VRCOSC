# **DG-LAB-VRCOSC**

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/MofuNadenade/DG-LAB-VRCOSC)](https://github.com/MofuNadenade/DG-LAB-VRCOSC/releases)
[![GitHub downloads](https://img.shields.io/github/downloads/MofuNadenade/DG-LAB-VRCOSC/total)](https://github.com/MofuNadenade/DG-LAB-VRCOSC/releases)
[![GitHub stars](https://img.shields.io/github/stars/MofuNadenade/DG-LAB-VRCOSC)](https://github.com/MofuNadenade/DG-LAB-VRCOSC/stargazers)
[![GitHub license](https://img.shields.io/github/license/MofuNadenade/DG-LAB-VRCOSC)](https://github.com/MofuNadenade/DG-LAB-VRCOSC/blob/master/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.13+-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)](https://github.com/MofuNadenade/DG-LAB-VRCOSC)

> 与 **VRChat** 游戏联动的郊狼 (DG-LAB) **3.0** 设备控制程序

> ⚠️ **重要提示**: 本README文件使用AI工具生成，并经过人工检查。由于项目功能复杂，可能存在遗漏或不准确的信息。如有疑问，请参考项目源码或提交Issue反馈。

![](https://count.getloli.com/get/@MofuNadenade-DG-LAB-VRCOSC?theme=rule34)

通过 VRChat 游戏内的 avatars 互动和其他事件来控制 DG-LAB 设备的输出，实现沉浸式的触觉反馈体验。

## ✨ 主要功能

### 🔌 设备兼容性
- **支持设备**: DG-LAB 3.0 主机
- **连接方式**: 
  - **WebSocket**: 通过 WebSocket 控制 DG-LAB APP（稳定/安全）
  - **蓝牙直连**: 直接通过蓝牙连接 DG-LAB 3.0 主机（快捷/可能会被电飞？）

### 🎮 VRChat Avatar 联动功能 (OSC)

#### 面板控制模式
- 通过 VRSuya 的 [SoundPad](https://booth.pm/zh-cn/items/5950846) 进行控制
- 映射按键到设备功能
- 支持**远程控制** - 可通过自己 Avatar 上的面板控制其他安装相同面板玩家的设备

#### 交互控制模式
- 支持通过 VRChat Avatar 的任意参数进行控制
- Avatar 之间的交互可以控制设备输出（例如触碰或拉伸动骨）

#### ChatBox 显示
- 可通过 VRChat 的 ChatBox 显示当前设备信息

### 🎯 Terrors of Nowhere 游戏联动

- **伤害反馈**: 游戏内受到伤害会增加设备输出
- **死亡惩罚**: 游戏内死亡会触发死亡惩罚
- **技术实现**: 通过 [ToNSaveManager](https://github.com/ChrisFeline/ToNSaveManager) 的 WebSocket API 监控游戏事件

> **注意**: 需要在游玩 ToN 时运行 ToNSaveManager 存档软件，并打开设置中的 WebSocket API 服务器

## 🖥️ 界面预览

### 应用程序界面
![DG-LAB-VRCOSC-APP-1.png](docs/assets/DG-LAB-VRCOSC-APP-1.png)

![DG-LAB-VRCOSC-APP-2.png](docs/assets/DG-LAB-VRCOSC-APP-2.png)

![DG-LAB-VRCOSC-APP-3.png](docs/assets/DG-LAB-VRCOSC-APP-3.png)

![DG-LAB-VRCOSC-APP-4.png](docs/assets/DG-LAB-VRCOSC-APP-4.png)

![DG-LAB-VRCOSC-APP-5.png](docs/assets/DG-LAB-VRCOSC-APP-5.png)

![DG-LAB-VRCOSC-APP-6.png](docs/assets/DG-LAB-VRCOSC-APP-6.png)

### SoundPad 控制面板
![DG-LAB-VRCOSC-SoundPad-CN.png](docs%2Fassets%2FDG-LAB-VRCOSC-SoundPad-CN.png)

### VRChat 游戏内轮盘菜单
![DG-LAB-VRCOSC-VRChatMenu-CN.png](docs%2Fassets%2FDG-LAB-VRCOSC-VRChatMenu-CN.png)

## 🆕 新增功能特性

### 📱 蓝牙直连支持
- **直接连接**: 无需DG-LAB APP，直接通过蓝牙连接DG-LAB 3.0主机
- **自动扫描**: 自动扫描并发现附近的DG-LAB设备
- **稳定连接**: 基于官方V3协议实现，连接稳定可靠
- **实时控制**: 支持实时强度调节和波形数据传输
- **设备管理**: 完整的设备连接状态管理和错误处理

### 🎛️ 波形编辑器
- **可视化编辑**: 参考DG-LAB官方APP界面设计的波形编辑器
- **实时预览**: 支持波形实时预览和测试播放
- **多通道支持**: 支持A/B双通道独立编辑和测试
- **波形管理**: 支持创建、复制、导入、导出波形文件

### 🔧 OSC 地址与绑定编辑器
- **智能地址管理**: 支持自定义OSC地址名称和代码
- **绑定配置**: 灵活的OSC绑定配置系统
- **实时查询**: OSC信息实时查询和状态监控
- **模板系统**: 预设OSC模板，快速配置常用功能
- **PCS支持**: 内置PCS地址模板和配置

### 🏗️ 技术架构升级
- **严格类型检查**: 使用Pyright进行完整的类型检查
- **模块化设计**: 重构为模块化架构，提高代码可维护性
- **解耦设计**: 服务层与UI层完全解耦，支持插件化扩展

## 📋 使用说明

### 面板控制功能设置
1. 在 Booth 购买 [声音面板](https://booth.pm/zh-cn/items/5950846)
2. 将资源导入工程
3. 导入本项目提供的修改包
4. 将修改包内提供的 prefab 安装到您的 avatar 中

> ✅ 此处的修改包发布已获取 [VRサウンドパッド] 原作者授权

### ToN 游戏优化
如需缩短对 ToN 游戏状态的响应时间，可调整 ToNSaveManager 设置中的 **常规-设置更新速率**：
- 默认: 1000ms
- 推荐: 100ms（根据实际情况调整）

## 🚀 快速开始

### 1. 下载安装
下载 [release](https://github.com/MofuNadenade/DG-LAB-VRCOSC/releases) 中最新版本的 `DG-LAB-VRCOSC.zip`，解压后运行

### 2. 设备连接

#### 方式一：蓝牙直连（推荐）
1. 确保 DG-LAB 3.0 主机已开机并处于可发现状态
2. 在主界面选择"蓝牙连接"模式
3. 点击"扫描设备"按钮，程序会自动搜索附近的 DG-LAB 设备
4. 从设备列表中选择要连接的设备
5. 点击"连接"按钮建立蓝牙连接

#### 方式二：WebSocket连接
1. 点击主界面的 `启动` 来生成二维码
2. 使用 DG-LAB APP 连接 DG-LAB 3.0 主机
3. 点击 APP 中的 `SOCKET控制` 然后扫描此处二维码连接设备

### 3. 故障排除

#### 蓝牙连接问题
- 确保 DG-LAB 3.0 主机已开机且蓝牙功能正常
- 检查电脑蓝牙适配器是否正常工作
- 确保设备距离在蓝牙有效范围内（建议3米内）
- 如果连接失败，尝试重启 DG-LAB 主机后重新扫描

#### WebSocket连接问题
- 检查网卡设置是否正确
- 检查端口配置是否正确
- 确保 DG-LAB APP 版本支持 WebSocket 功能
- 修改后再次尝试启动

> 📝 **模型修改**: 你需要修改你使用的模型，才能让此程序与游戏中的 avatar 联动（模型修改文档编写中 WIP）
> 
> 🎮 **ToN 支持**: ToN 游戏支持不需要修改模型，只需按上面的说明启用 ToNSaveManager 的 WebSocket API 接口即可

## ⚠️ 注意事项

1. **免责声明**: 本程序及开发者不对使用该程序产生的**任何后果**负责，使用程序则视为同意本条款
2. **安全使用**: 请遵循 DG-LAB APP 中的说明，以安全的方式使用设备，使用此程序前请根据个人情况设置合理的强度上限
3. **代码质量**: 本程序部分功能使用 ChatGPT、Claude Code 等AI技术生成，可能未经过充分的测试

## 📚 使用教程

📺 **视频使用教程**: [https://www.bilibili.com/video/BV1k81VYfETR](https://www.bilibili.com/video/BV1k81VYfETR)

## 🔄 项目改进说明

本项目基于原版 DG-LAB-VRCOSC v0.1.1 版本进行重大升级，主要改进包括：

### 🚀 功能增强
- **蓝牙直连**: 新增蓝牙直连功能，无需DG-LAB APP即可直接控制设备
- **波形编辑器**: 从简单的预设波形升级为完整的可视化编辑器
- **OSC管理**: 从基础OSC支持升级为完整的地址绑定管理系统
- **PCS系统**: 新增PCS支持，可以一键绑定PCS地址
- **游戏联动**: 从基础ToN支持升级为可配置的伤害系统
- **多语言**: 新增完整的国际化支持

### 🏗️ 架构重构
- **代码质量**: 从ChatGPT生成的代码升级为严格类型检查的模块化架构
- **性能优化**: 从同步架构升级为全异步架构
- **可维护性**: 从单体代码升级为解耦的模块化设计
- **扩展性**: 支持插件化扩展和自定义功能

### 🎯 用户体验
- **界面设计**: 重新设计的现代化用户界面
- **操作流程**: 优化的操作流程和用户引导
- **错误处理**: 完善的错误处理和用户提示
- **配置管理**: 灵活的配置管理和个性化设置

## 🔗 相关链接

- **项目地址**: [https://github.com/MofuNadenade/DG-LAB-VRCOSC](https://github.com/MofuNadenade/DG-LAB-VRCOSC)
- **原项目**: [https://github.com/ccvrc/DG-LAB-VRCOSC](https://github.com/ccvrc/DG-LAB-VRCOSC)
- **ToNSaveManager**: [https://github.com/ChrisFeline/ToNSaveManager](https://github.com/ChrisFeline/ToNSaveManager)
- **Terrors of Nowhere**: [https://terror.moe/](https://terror.moe/)
- **VRSuya SoundPad**: [https://booth.pm/zh-cn/items/5950846](https://booth.pm/zh-cn/items/5950846)

## 👨‍💻 开发者资源

- **开发指南**: [DEVELOPMENT.md](DEVELOPMENT.md) - 开发环境配置、代码规范、贡献指南

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给它一个星标！**

</div>
