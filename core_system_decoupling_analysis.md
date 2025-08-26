# CoreSystem 解耦分析报告

## 当前架构分析

### 1. 依赖关系图

```
MainWindow (UI层)
├── 直接依赖
│   ├── DGLabController (服务容器)
│   ├── Registries (注册表集合)
│   ├── OSCOptionsProvider (OSC选项提供者)
│   └── 各种Tab组件
│
├── 核心功能实现
│   ├── OSC动作注册 (_register_basic_actions)
│   ├── 脉冲动作注册 (_register_pulse_actions)
│   ├── OSC绑定注册 (_register_osc_bindings)
│   ├── 控制器设置管理 (_load_controller_settings)
│   ├── 连接状态管理 (set_connection_state)
│   ├── 脉冲模式管理 (set_pulse_mode)
│   ├── 功能开关管理 (set_feature_state)
│   └── 强度步进管理 (set_strength_step)
│
└── 数据流
    ├── 从settings加载配置
    ├── 向registries注册数据
    ├── 向controller注册回调
    └── 向UI组件更新状态
```

### 2. 当前问题分析

#### 2.1 架构问题
- **职责混乱**: MainWindow既负责UI管理又负责核心业务逻辑
- **紧耦合**: UI组件直接依赖具体的业务实现
- **难以测试**: 核心逻辑与UI绑定，无法独立测试
- **扩展性差**: 新增功能需要修改MainWindow

#### 2.2 具体问题点
1. **OSC注册逻辑**: 在MainWindow中实现，应该属于核心系统
2. **配置管理**: 配置加载、保存逻辑分散在UI层
3. **状态管理**: 连接状态、设备状态管理混在UI中
4. **事件处理**: 各种回调方法直接写在MainWindow中

### 3. 解耦方案设计

#### 3.1 目标架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MainWindow    │    │   CoreSystem    │    │   Services      │
│   (纯UI层)      │◄──►│   (核心业务层)   │◄──►│   (服务层)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Tab组件       │    │   Registries    │    │   DGLabService   │
│   (UI组件)      │    │   (数据注册表)   │    │   (设备控制)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

#### 3.2 CoreSystem 设计（符合CoreInterface协议）

```python
from typing import Optional
from PySide6.QtGui import QPixmap
from core.core_interface import CoreInterface
from core.registries import Registries
from models import ConnectionState, StrengthData, Channel, UIFeature, SettingsDict

class CoreSystem(CoreInterface):
    """核心业务系统，负责所有非UI的业务逻辑，符合CoreInterface协议"""
    
    def __init__(self):
        # 符合CoreInterface协议的数据访问属性
        self.registries = Registries()
        self.controller: Optional[DGLabController] = None
        self.settings: SettingsDict = {}
        
        # 子管理器
        self.osc_manager = OSCManager(self)
        self.state_manager = StateManager(self)
        self.config_manager = ConfigManager(self)
        
        # 内部状态
        self._current_connection_state: ConnectionState = ConnectionState.DISCONNECTED
        self._pulse_modes = {Channel.A: "连击", Channel.B: "连击"}
        self._feature_states = {
            UIFeature.PANEL_CONTROL: True,
            UIFeature.CHATBOX_STATUS: False,
            UIFeature.DYNAMIC_BONE_A: False,
            UIFeature.DYNAMIC_BONE_B: False
        }
        self._strength_step = 30
        self._current_channel = Channel.A
        self._connection_status = False
        self._strength_data = StrengthData()
    
    # ============ 符合CoreInterface协议的方法 ============
    
    # 连接状态管理
    def set_connection_state(self, state: ConnectionState, message: str = "") -> None:
        """设置连接状态"""
        self._current_connection_state = state
        logger.info(f"连接状态变更为: {state} - {message}")
    
    def get_connection_state(self) -> ConnectionState:
        """获取连接状态"""
        return self._current_connection_state
    
    # 脉冲模式管理
    def set_pulse_mode(self, channel: Channel, mode_name: str, silent: bool = False) -> None:
        """设置脉冲模式"""
        self._pulse_modes[channel] = mode_name
        if not silent and self.controller is not None:
            # 同步到设备
            asyncio.create_task(self._sync_pulse_mode_to_device(channel, mode_name))
    
    def get_pulse_mode(self, channel: Channel) -> str:
        """获取脉冲模式"""
        return self._pulse_modes.get(channel, "连击")
    
    # 功能开关管理
    def set_feature_state(self, feature: UIFeature, enabled: bool, silent: bool = False) -> None:
        """设置功能状态"""
        self._feature_states[feature] = enabled
        if not silent and self.controller is not None:
            # 同步到设备
            asyncio.create_task(self._sync_feature_to_device(feature, enabled))
    
    def get_feature_state(self, feature: UIFeature) -> bool:
        """获取功能状态"""
        return self._feature_states.get(feature, False)
    
    # 数值控制管理
    def set_strength_step(self, value: int, silent: bool = False) -> None:
        """设置强度步进"""
        self._strength_step = value
        if not silent and self.controller is not None:
            # 同步到设备
            self.controller.dglab_service.fire_mode_strength_step = value
    
    def get_strength_step(self) -> int:
        """获取强度步进"""
        return self._strength_step
    
    # 日志管理
    def log_info(self, message: str) -> None:
        """记录信息日志"""
        logger.info(message)
    
    def log_warning(self, message: str) -> None:
        """记录警告日志"""
        logger.warning(message)
    
    def log_error(self, message: str) -> None:
        """记录错误日志"""
        logger.error(message)
    
    def clear_logs(self) -> None:
        """清空日志"""
        # 在CoreSystem中，这个方法可能不需要实现
        # 或者可以用于清理内部日志缓存
        pass
    
    # 控制器管理
    def set_controller_available(self, available: bool) -> None:
        """设置控制器可用状态"""
        # 这个方法主要用于UI更新，在CoreSystem中可能不需要实现
        # 或者可以用于内部状态管理
        pass
    
    # 连接状态通知回调
    def on_client_connected(self) -> None:
        """客户端连接时的回调"""
        self._connection_status = True
        self.set_connection_state(ConnectionState.CONNECTED, "客户端已连接")
        logger.info("客户端已连接")
    
    def on_client_disconnected(self) -> None:
        """客户端断开连接时的回调"""
        self._connection_status = False
        self.set_connection_state(ConnectionState.WAITING, "客户端已断开连接")
        logger.info("客户端已断开连接")
    
    def on_client_reconnected(self) -> None:
        """客户端重新连接时的回调"""
        self._connection_status = True
        self.set_connection_state(ConnectionState.CONNECTED, "客户端已重新连接")
        logger.info("客户端已重新连接")
    
    # 现有方法保持不变
    def update_current_channel_display(self, channel_name: str) -> None:
        """更新当前选择通道显示"""
        # 这个方法主要用于UI更新，在CoreSystem中可能不需要实现
        # 或者可以用于内部状态管理
        self._current_channel = Channel.A if "A" in channel_name else Channel.B
    
    def update_qrcode(self, qrcode_pixmap: QPixmap) -> None:
        """更新二维码"""
        # 这个方法主要用于UI更新，在CoreSystem中可能不需要实现
        # 或者可以用于内部状态管理
        pass
    
    def update_connection_status(self, is_online: bool) -> None:
        """根据设备连接状态更新状态"""
        self._connection_status = is_online
        if is_online:
            self.set_connection_state(ConnectionState.CONNECTED, "设备已连接")
        else:
            self.set_connection_state(ConnectionState.DISCONNECTED, "设备已断开")
    
    def update_status(self, strength_data: StrengthData) -> None:
        """更新通道强度和波形"""
        self._strength_data = strength_data
    
    def save_settings(self) -> None:
        """保存设置到文件"""
        self.config_manager.save_settings()
    
    # ============ CoreSystem特有的方法 ============
    
    # 控制器管理
    def set_controller(self, controller: Optional[DGLabController]) -> None:
        """设置控制器"""
        self.controller = controller
        if controller is not None:
            # 注册OSC动作
            asyncio.create_task(self.osc_manager.register_all_actions())
            # 加载配置
            self.config_manager.load_controller_settings()
    
    # 配置管理
    def load_settings(self) -> None:
        """加载配置"""
        self.config_manager.load_all_settings()
    
    # 内部同步方法
    async def _sync_pulse_mode_to_device(self, channel: Channel, mode_name: str) -> None:
        """同步脉冲模式到设备"""
        if self.controller is None:
            return
        
        # 查找脉冲索引
        pulse_index = -1
        for pulse in self.registries.pulse_registry.pulses:
            if pulse.name == mode_name:
                pulse_index = pulse.index
                break
        
        if pulse_index >= 0:
            self.controller.dglab_service.set_pulse_mode(channel, pulse_index)
    
    async def _sync_feature_to_device(self, feature: UIFeature, enabled: bool) -> None:
        """同步功能状态到设备"""
        if self.controller is None:
            return
        
        dglab_service = self.controller.dglab_service
        
        if feature == UIFeature.PANEL_CONTROL:
            dglab_service.enable_panel_control = enabled
        elif feature == UIFeature.CHATBOX_STATUS:
            self.controller.chatbox_service.set_enabled(enabled)
        elif feature == UIFeature.DYNAMIC_BONE_A:
            dglab_service.set_dynamic_bone_mode(Channel.A, enabled)
        elif feature == UIFeature.DYNAMIC_BONE_B:
            dglab_service.set_dynamic_bone_mode(Channel.B, enabled)
```

#### 3.3 协议符合性分析

**完全符合的方法**:
- ✅ `registries` 属性
- ✅ `set_connection_state()` / `get_connection_state()`
- ✅ `set_pulse_mode()` / `get_pulse_mode()`
- ✅ `set_feature_state()` / `get_feature_state()`
- ✅ `set_strength_step()` / `get_strength_step()`
- ✅ `save_settings()`

**需要适配的方法**:
- 🔄 `clear_logs()` - 在CoreSystem中可能不需要实现
- 🔄 `set_controller_available()` - 主要用于UI更新
- 🔄 `update_current_channel_display()` - 主要用于UI更新
- 🔄 `update_qrcode()` - 主要用于UI更新

**需要实现的方法**:
- ✅ `log_info()` / `log_warning()` / `log_error()` - 使用logger实现
- ✅ `on_client_connected()` / `on_client_disconnected()` / `on_client_reconnected()` - 内部状态管理

#### 3.4 解耦后的依赖关系

```
MainWindow (UI层)
├── 依赖 CoreSystem (通过CoreInterface协议)
├── 调用核心方法 (通过协议接口)
└── 获取状态信息 (通过协议接口)

CoreSystem (核心层，实现CoreInterface协议)
├── 管理所有业务逻辑
├── 协调各个服务
├── 管理状态和配置
├── 提供协议规定的接口
└── 维护内部状态

Services (服务层)
├── 实现具体功能
├── 被CoreSystem调用
└── 维护内部状态
```

### 4. 实施步骤

#### 4.1 第一阶段：创建CoreSystem基础结构
1. 创建 `CoreSystem` 类，实现 `CoreInterface` 协议
2. 创建子管理器类 (`OSCManager`, `StateManager`, `ConfigManager`)
3. 实现协议要求的所有方法
4. 确保类型注解和接口完全匹配

#### 4.2 第二阶段：迁移核心逻辑
1. 将OSC注册逻辑迁移到 `OSCManager`
2. 将状态管理逻辑迁移到 `StateManager`
3. 将配置管理逻辑迁移到 `ConfigManager`
4. 保持MainWindow接口不变

#### 4.3 第三阶段：重构MainWindow
1. MainWindow只保留UI相关代码
2. 通过CoreInterface协议调用核心功能
3. 移除重复的业务逻辑代码
4. 确保UI状态与CoreSystem状态同步

#### 4.4 第四阶段：优化和测试
1. 优化接口设计
2. 添加单元测试
3. 性能测试和优化
4. 文档更新

### 5. 潜在问题和风险

#### 5.1 技术风险
- **协议实现**: 需要确保完全符合CoreInterface协议
- **循环依赖**: 需要仔细设计接口避免循环引用
- **状态同步**: UI状态与核心状态可能不一致

#### 5.2 实施风险
- **重构范围大**: 需要修改多个文件
- **测试覆盖**: 需要重新设计测试策略
- **向后兼容**: 需要保持现有功能不变

### 6. 最佳方案推荐

#### 6.1 渐进式重构
1. **先创建CoreSystem**: 实现CoreInterface协议，不破坏现有功能
2. **逐步迁移逻辑**: 一次迁移一个功能模块
3. **保持接口稳定**: 确保UI层调用方式不变

#### 6.2 接口设计原则
1. **协议优先**: 优先确保符合CoreInterface协议
2. **依赖倒置**: UI依赖抽象接口，不依赖具体实现
3. **单一职责**: 每个类只负责一个方面

#### 6.3 状态管理设计
1. **状态集中**: 所有状态集中在CoreSystem中管理
2. **协议兼容**: 确保所有协议方法都有合理实现
3. **同步机制**: 确保UI状态与核心状态同步

### 7. 预期收益

#### 7.1 架构收益
- **协议兼容**: 完全符合CoreInterface协议
- **清晰的分层**: UI、业务、服务层职责明确
- **易于维护**: 核心逻辑集中管理
- **便于测试**: 可以独立测试核心逻辑

#### 7.2 开发收益
- **团队协作**: 不同开发者可以并行开发不同层
- **代码复用**: 核心逻辑可以被其他UI复用
- **扩展性**: 新增功能更容易实现

### 8. 总结

将CoreInterface从UI中分离出来创建CoreSystem是一个必要的架构重构。CoreSystem必须完全符合CoreInterface协议，确保向后兼容性。虽然重构工作量较大，但能够显著提升代码质量和可维护性。建议采用渐进式重构策略，确保在重构过程中不破坏现有功能，同时严格遵循协议规范。
