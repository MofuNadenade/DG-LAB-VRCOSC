# CoreInterface API 使用情况分析报告

## 概述

本报告分析了 `CoreInterface` 协议中各个API方法的使用情况，帮助识别哪些方法被实际使用，哪些方法可能未被使用。同时分析了每个API的依赖关系。

## API 依赖关系分析

### 核心依赖模块

#### 1. **数据模型层** (`src/models.py`)
- **ConnectionState**: 连接状态枚举
- **Channel**: 通道枚举 (A/B)
- **UIFeature**: UI功能开关枚举
- **StrengthData**: 强度数据模型
- **SettingsDict**: 应用程序设置配置类型

#### 2. **注册表系统** (`src/core/registries.py`)
- **PulseRegistry**: 脉冲注册表
- **OSCActionRegistry**: OSC动作注册表
- **OSCAddressRegistry**: OSC地址注册表
- **OSCBindingRegistry**: OSC绑定注册表
- **OSCTemplateRegistry**: OSC模板注册表
- **OSCCodeRegistry**: OSC代码注册表

#### 3. **UI框架** (`PySide6`)
- **QPixmap**: 图像处理类
- **QMainWindow**: 主窗口类
- **QWidget**: 基础组件类

#### 4. **服务层**
- **DGLabWebSocketService**: WebSocket服务
- **OSCService**: OSC服务
- **ChatboxService**: ChatBox服务

## API 使用情况详细分析

### 1. 数据访问属性

#### ✅ `registries: Registries`
- **状态**: 被使用
- **依赖模块**: 
  - `src/core/registries.py` (核心注册表系统)
  - `src/core/dglab_pulse.py` (脉冲管理)
  - `src/core/osc_*.py` (OSC相关模块)
- **使用位置**: 
  - `src/gui/main_window.py` (主窗口初始化时创建)
  - `src/gui/osc_address_tab.py` (OSC地址管理UI)
  - `src/core/osc_provider.py` (OSC选项提供者)

### 2. 连接状态管理

#### ✅ `set_connection_state(state: ConnectionState, message: str = "") -> None`
- **状态**: 被大量使用
- **依赖模块**:
  - `src/models.py` (ConnectionState枚举)
  - `src/services/dglab_websocket_service.py` (WebSocket服务)
  - `src/services/osc_service.py` (OSC服务)
  - `src/gui/network_config_tab.py` (网络配置UI)
- **使用位置**:
  - `src/gui/main_window.py` (MainWindow.on_client_*方法中)
  - `src/gui/network_config_tab.py` (处理连接状态变化)
  - `src/services/dglab_websocket_service.py` (更新连接状态)
  - `src/services/osc_service.py` (处理错误状态)

#### ✅ `get_connection_state() -> ConnectionState`
- **状态**: 被使用
- **依赖模块**:
  - `src/models.py` (ConnectionState枚举)
  - `src/gui/network_config_tab.py` (网络配置UI)
  - `src/gui/log_viewer_tab.py` (日志查看UI)
- **使用位置**:
  - `src/gui/network_config_tab.py` (检查当前状态)
  - `src/gui/log_viewer_tab.py` (显示设备状态)

### 3. 脉冲模式管理

#### ✅ `set_pulse_mode(channel: Channel, mode_name: str, silent: bool = False) -> None`
- **状态**: 被使用
- **依赖模块**:
  - `src/models.py` (Channel枚举)
  - `src/gui/main_window.py` (主窗口)
  - `src/gui/controller_settings_tab.py` (控制器设置UI)
- **使用位置**:
  - `src/gui/main_window.py` (管理脉冲模式设置)

#### ✅ `get_pulse_mode(channel: Channel) -> str`
- **状态**: 被使用
- **依赖模块**:
  - `src/models.py` (Channel枚举)
  - `src/gui/main_window.py` (主窗口)
- **使用位置**:
  - `src/gui/main_window.py` (获取当前脉冲模式)

### 4. 功能开关管理

#### ✅ `set_feature_state(feature: UIFeature, enabled: bool, silent: bool = False) -> None`
- **状态**: 被使用
- **依赖模块**:
  - `src/models.py` (UIFeature枚举)
  - `src/gui/main_window.py` (主窗口)
  - `src/gui/controller_settings_tab.py` (控制器设置UI)
- **使用位置**:
  - `src/gui/main_window.py` (管理各种功能开关)

#### ✅ `get_feature_state(feature: UIFeature) -> bool`
- **状态**: 被使用
- **依赖模块**:
  - `src/models.py` (UIFeature枚举)
  - `src/gui/main_window.py` (主窗口)
- **使用位置**:
  - `src/gui/main_window.py` (获取功能开关状态)

### 5. 数值控制管理

#### ✅ `set_strength_step(value: int, silent: bool = False) -> None`
- **状态**: 被使用
- **依赖模块**:
  - `src/gui/main_window.py` (主窗口)
  - `src/gui/controller_settings_tab.py` (控制器设置UI)
- **使用位置**:
  - `src/gui/main_window.py` (设置强度步进值)

#### ✅ `get_strength_step() -> int`
- **状态**: 被使用
- **依赖模块**:
  - `src/gui/main_window.py` (主窗口)
- **使用位置**:
  - `src/gui/main_window.py` (获取强度步进值)

### 6. 日志管理

#### ❌ `log_info(message: str) -> None`
- **状态**: **未被使用**
- **依赖模块**: `src/gui/main_window.py` (主窗口)
- **使用位置**: 无外部调用
- **分析**: 
  - 在MainWindow中有实现，但从未被外部调用
  - 只有 `log_error` 被使用
  - 建议：如果不需要，可以考虑移除

#### ❌ `log_warning(message: str) -> None`
- **状态**: **未被使用**
- **依赖模块**: `src/gui/main_window.py` (主窗口)
- **使用位置**: 无外部调用
- **分析**: 
  - 在MainWindow中有实现，但从未被外部调用
  - 建议：如果不需要，可以考虑移除

#### ✅ `log_error(message: str) -> None`
- **状态**: 被使用
- **依赖模块**: `src/gui/main_window.py` (主窗口)
- **使用位置**:
  - `src/gui/main_window.py` (记录错误日志)

#### ❌ `clear_logs() -> None`
- **状态**: **未被使用**
- **依赖模块**: `src/gui/main_window.py` (主窗口)
- **使用位置**: 无外部调用
- **分析**: 
  - 在MainWindow中有实现，但从未被外部调用
  - 建议：如果不需要，可以考虑移除

### 7. 控制器管理

#### ✅ `set_controller_available(available: bool) -> None`
- **状态**: 被使用
- **依赖模块**: `src/gui/main_window.py` (主窗口)
- **使用位置**:
  - `src/gui/main_window.py` (启用/禁用控制器相关UI)

### 8. 连接状态通知回调

#### ✅ `on_client_connected() -> None`
- **状态**: 被使用
- **依赖模块**:
  - `src/services/dglab_websocket_service.py` (WebSocket服务)
  - `src/gui/main_window.py` (主窗口)
- **使用位置**:
  - `src/services/dglab_websocket_service.py` (通知客户端连接)

#### ✅ `on_client_disconnected() -> None`
- **状态**: 被使用
- **依赖模块**:
  - `src/services/dglab_websocket_service.py` (WebSocket服务)
  - `src/gui/main_window.py` (主窗口)
- **使用位置**:
  - `src/services/dglab_websocket_service.py` (通知客户端断开)

#### ✅ `on_client_reconnected() -> None`
- **状态**: 被使用
- **依赖模块**:
  - `src/services/dglab_websocket_service.py` (WebSocket服务)
  - `src/gui/main_window.py` (主窗口)
- **使用位置**:
  - `src/services/dglab_websocket_service.py` (通知客户端重连)

### 9. 现有方法保持不变

#### ✅ `update_current_channel_display(channel_name: str) -> None`
- **状态**: 被使用
- **依赖模块**:
  - `src/services/dglab_websocket_service.py` (WebSocket服务)
  - `src/gui/main_window.py` (主窗口)
- **使用位置**:
  - `src/services/dglab_websocket_service.py` (更新当前通道显示)

#### ✅ `update_qrcode(qrcode_pixmap: QPixmap) -> None`
- **状态**: 被使用
- **依赖模块**:
  - `PySide6.QtGui` (QPixmap)
  - `src/services/dglab_websocket_service.py` (WebSocket服务)
  - `src/gui/main_window.py` (主窗口)
- **使用位置**:
  - `src/services/dglab_websocket_service.py` (更新二维码显示)

#### ✅ `update_client_state(is_online: bool) -> None`
- **状态**: 被使用
- **依赖模块**:
  - `src/gui/main_window.py` (主窗口)
  - `src/gui/network_config_tab.py` (网络配置UI)
- **使用位置**:
  - `src/gui/main_window.py` (更新连接状态)

#### ✅ `update_status(strength_data: StrengthData) -> None`
- **状态**: 被使用
- **依赖模块**:
  - `src/models.py` (StrengthData模型)
  - `src/services/dglab_websocket_service.py` (WebSocket服务)
  - `src/gui/main_window.py` (主窗口)
- **使用位置**:
  - `src/services/dglab_websocket_service.py` (更新状态信息)

#### ✅ `save_settings() -> None`
- **状态**: 被使用
- **依赖模块**:
  - `src/config.py` (配置管理)
  - `src/models.py` (SettingsDict类型)
  - `src/gui/main_window.py` (主窗口)
- **使用位置**:
  - `src/gui/main_window.py` (保存设置)

## 依赖关系总结

### 核心依赖层次

```
CoreInterface
├── 数据模型层 (models.py)
│   ├── ConnectionState, Channel, UIFeature
│   ├── StrengthData, SettingsDict
│   └── OSC相关类型
├── 注册表系统 (core/registries.py)
│   ├── PulseRegistry, OSCActionRegistry
│   ├── OSCAddressRegistry, OSCBindingRegistry
│   └── OSCTemplateRegistry, OSCCodeRegistry
├── UI框架 (PySide6)
│   ├── QPixmap, QMainWindow, QWidget
│   └── 各种UI组件
└── 服务层
    ├── DGLabWebSocketService
    ├── OSCService, ChatboxService
    └── 各种业务服务
```

### 依赖强度分析

#### **强依赖** (必须存在)
- `models.py` - 所有枚举和类型定义
- `registries.py` - 核心注册表系统
- `PySide6` - UI框架基础

#### **中等依赖** (重要但可替换)
- `dglab_websocket_service.py` - WebSocket服务
- `osc_service.py` - OSC服务
- `main_window.py` - 主窗口实现

#### **弱依赖** (可选或可简化)
- `chatbox_service.py` - ChatBox服务
- 各种Tab组件的具体实现

## 总结

### 被使用的API (25个)
- `registries` 属性
- `set_connection_state()` / `get_connection_state()`
- `set_pulse_mode()` / `get_pulse_mode()`
- `set_feature_state()` / `get_feature_state()`
- `set_strength_step()` / `get_strength_step()`
- `set_controller_available()`
- `on_client_connected()` / `on_client_disconnected()` / `on_client_reconnected()`
- `update_current_channel_display()`
- `update_qrcode()`
- `update_client_state()`
- `update_status()`
- `save_settings()`
- `log_error()`

### 未被使用的API (3个)
- ❌ `log_info()` - 从未被调用
- ❌ `log_warning()` - 从未被调用
- ❌ `clear_logs()` - 从未被调用

### 建议

1. **保留所有被使用的API**: 这些API在系统中发挥着重要作用，必须保留
2. **考虑移除未使用的API**: 特别是日志相关的方法，如果确实不需要，可以考虑从协议中移除
3. **向后兼容性**: 如果决定移除某些API，需要确保不影响现有代码的兼容性

### 对CoreSystem设计的影响

在实现CoreSystem时，对于未被使用的API：
- 可以设置为空实现（pass）
- 或者提供简单的默认实现
- 或者考虑是否真的需要这些方法

这样可以简化CoreSystem的实现，同时保持与CoreInterface协议的完全兼容。

### 架构重构建议

基于依赖关系分析，建议重构时：

1. **保持核心依赖**: 确保models.py和registries.py的稳定性
2. **简化服务依赖**: 可以考虑简化或合并某些服务
3. **UI框架解耦**: 减少对PySide6具体实现的依赖
4. **配置管理集中**: 将配置相关逻辑集中到CoreSystem中
