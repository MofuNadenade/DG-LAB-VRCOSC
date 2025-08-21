# Services 目录

这个目录包含了重构后的服务模块，将原来的 `dglab_controller.py` 中的功能完全分离到专门的服务中。

**⚠️ 重要：控制器现在是一个纯粹的服务容器，不包含任何方法，只有属性访问器！**

## 服务架构

### DGLabService (`dglab_service.py`)
**统一的 DGLab 硬件控制服务**

整合了所有与 DGLab 硬件相关的功能：
- **通道管理**: A/B 通道脉冲任务、通道选择
- **强度控制**: 强度调节、动骨模式、面板控制
- **波形管理**: 波形数据更新、模式切换
- **开火模式**: 一键开火、强度步进
- **模式切换**: 交互/面板模式切换、UI 同步

### OSCService (`osc_service.py`)
**OSC 消息处理服务**

负责：
- OSC 消息解析和处理
- VRChat 参数处理
- OSC 客户端通信

### ChatboxService (`chatbox_service.py`)
**VRChat ChatBox 管理服务**

负责：
- ChatBox 状态显示
- 周期性状态更新
- ChatBox 开关控制

## 使用方式

### 标准方式 - 直接使用服务（推荐）
```python
# DGLab 硬件控制
await controller.dglab_service.set_strength_step(50)
await controller.dglab_service.reset_strength(True, Channel.A)
await controller.dglab_service.set_channel(1)
await controller.dglab_service.set_panel_control(True)

# OSC 通信
controller.osc_service.send_message_to_vrchat_chatbox("Hello")
controller.osc_service.send_value_to_vrchat("/avatar/parameters/test", 1.0)

# ChatBox 管理
await controller.chatbox_service.toggle_chatbox(1)
await controller.chatbox_service.send_strength_status(controller.dglab_service)
```

### 访问状态数据
```python
# 通过控制器的只读属性
last_strength = controller.last_strength
current_channel = controller.current_select_channel
pulse_mode_a = controller.pulse_mode_a
is_dynamic_mode_a = controller.is_dynamic_bone_mode_a
```

### 控制器特性
```python
# 控制器现在只是一个数据容器，没有任何方法
# 只保留这些实例变量和属性访问器：
controller.app_status_online        # 应用在线状态
controller.dglab_service           # DGLab 服务实例
controller.osc_service            # OSC 服务实例  
controller.chatbox_service        # ChatBox 服务实例
```

## 重构优势

1. **代码分离**: 职责明确，每个服务专注特定功能
2. **易于测试**: 服务可以独立测试
3. **代码复用**: 服务可以被其他组件使用
4. **维护性**: 功能集中，便于修改和扩展
5. **向后兼容**: 保持原有接口，平滑迁移

## 迁移指南

**重要：所有委托方法已被移除！** 必须直接使用服务：

### 强制迁移表

| 旧的控制器方法 | 新的服务方法 | 说明 |
|---------------|-------------|------|
| `controller.set_strength_step(value)` | `controller.dglab_service.set_strength_step(value)` | 强度步进设置 |
| `controller.reset_strength(value, channel)` | `controller.dglab_service.reset_strength(value, channel)` | 强度重置 |
| `controller.set_channel(value)` | `controller.dglab_service.set_channel(value)` | 通道切换 |
| `controller.set_panel_control(value)` | `controller.dglab_service.set_panel_control(value)` | 面板控制 |
| `controller.set_mode(value, channel)` | `controller.dglab_service.set_mode(value, channel)` | 模式切换 |
| `controller.send_message_to_vrchat_chatbox(msg)` | `controller.osc_service.send_message_to_vrchat_chatbox(msg)` | ChatBox 消息 |
| `controller.send_strength_status()` | `controller.chatbox_service.send_strength_status(controller.dglab_service)` | 状态发送 |

### 控制器架构
**DGLabController 现在完全没有方法**，只有：
- 构造函数 `__init__()` - 初始化服务
- 属性访问器 - 只读数据访问（`last_strength`, `current_select_channel` 等）
- 实例变量 - 服务引用和状态（`app_status_online`, `dglab_service` 等）

**所有业务逻辑都必须通过服务调用！**