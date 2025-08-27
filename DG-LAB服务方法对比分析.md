# DG-LAB服务方法对比分析

本文档对比分析了DG-LAB项目中的三个核心服务文件的方法实现差异。

## 文件概览

- **`dglab_service_interface.py`**: 设备服务抽象接口
- **`dglab_bluetooth_service.py`**: 蓝牙直连服务实现
- **`dglab_websocket_service.py`**: WebSocket设备服务实现

## 方法列表

### 1. IDGLabService (接口)

#### 连接管理
- `start_service() -> bool`
- `stop_service() -> None`
- `is_server_running() -> bool`
- `get_connection_type() -> str`
- `wait_for_server_stop() -> None`

#### 属性访问
- `fire_mode_strength_step` (getter/setter)
- `fire_mode_disabled` (getter/setter)
- `enable_panel_control` (getter/setter)

#### 状态查询
- `get_current_channel() -> Channel`
- `get_last_strength() -> Optional[StrengthData]`
- `is_dynamic_bone_enabled(channel: Channel) -> bool`
- `get_pulse_mode(channel: Channel) -> int`
- `get_current_pulse_name(channel: Channel) -> str`

#### 通道控制
- `set_channel(value: Union[int, float]) -> Optional[Channel]`

#### 强度控制
- `set_float_output(value: float, channel: Channel) -> None`
- `adjust_strength(operation_type: StrengthOperationType, value: int, channel: Channel) -> None`
- `reset_strength(value: bool, channel: Channel) -> None`
- `increase_strength(value: bool, channel: Channel) -> None`
- `decrease_strength(value: bool, channel: Channel) -> None`

#### 波形控制
- `update_pulse_data() -> None`
- `set_pulse_data(channel: Channel, pulse_index: int, update_ui: bool = True) -> None`
- `set_test_pulse(channel: Channel, pulse: Pulse) -> None`
- `set_pulse_mode(channel: Channel, value: int) -> None`

#### 模式控制
- `set_dynamic_bone_mode(channel: Channel, enabled: bool) -> None`
- `set_mode(value: int, channel: Channel) -> None`
- `set_panel_control(value: float) -> None`
- `set_strength_step(value: float) -> None`

#### 开火模式
- `strength_fire_mode(value: bool, channel: Channel, fire_strength: int, last_strength: Optional[StrengthData]) -> None`

#### 数据更新
- `update_strength_data(strength_data: StrengthData) -> None`

### 2. DGLabBluetoothService (蓝牙实现)

#### 额外方法
- `is_connected() -> bool`
- `connect() -> bool`
- `disconnect() -> bool`
- `send_pulse_data(channel: Channel, data: List[PulseOperation]) -> None`
- `_convert_pulse_operations_to_wave_set(operations: List[PulseOperation]) -> List[tuple[int, int, int]]`
- `_get_channel_name(channel: Channel) -> str`
- `_get_dynamic_bone_ui_feature(channel: Channel) -> UIFeature`
- `_update_channel_pulse_tasks() -> None`
- `_set_mode_timer_handle(channel: Channel) -> None`
- `_initialize_device() -> None`

#### 内部类
- `BluetoothChannelPulseTask`

### 3. DGLabWebSocketService (WebSocket实现)

#### 额外方法
- `_handle_connection_lifecycle() -> None`
- `_handle_data(data: DGLabWebSocketData) -> None`
- `_handle_strength_data(data: pydglab_ws.StrengthData) -> None`
- `_handle_feedback_button(data: pydglab_ws.FeedbackButton) -> None`
- `_handle_ret_code(data: pydglab_ws.RetCode) -> None`
- `_handle_client_disconnected() -> None`
- `_attempt_reconnection() -> None`
- `_update_pulse_mode(channel: Channel, pulse_index: int) -> None`
- `_update_pulse_ui(channel: Channel, pulse_index: int) -> None`
- `_set_mode_timer_handle(channel: Channel) -> None`
- `_get_channel_name(channel: Channel) -> None`
- `_get_dynamic_bone_ui_feature(channel: Channel) -> UIFeature`
- `_map_value(value: float, min_value: float, max_value: float) -> float`
- `_update_channel_pulse_tasks() -> None`

#### 内部类
- `_ServerManager`
- `ChannelPulseTask`

## 方法对比表格

| 功能分类 | 方法名 | 接口定义 | 蓝牙实现 | WebSocket实现 | 差异说明 |
|---------|--------|----------|----------|---------------|----------|
| **连接管理** | `start_service()` | ✅ | ✅ | ✅ | 蓝牙：简单启动，WebSocket：启动服务器管理器 |
| | `stop_service()` | ✅ | ✅ | ✅ | 蓝牙：断开连接，WebSocket：停止服务器 |
| | `is_server_running()` | ✅ | ✅ | ✅ | 蓝牙：检查内部状态，WebSocket：检查服务器管理器状态 |
| | `get_connection_type()` | ✅ | ✅ | ✅ | 蓝牙返回"bluetooth"，WebSocket返回"websocket" |
| | `wait_for_server_stop()` | ✅ | ✅ | ✅ | 蓝牙：等待内部事件，WebSocket：等待服务器停止事件 |
| **属性访问** | `fire_mode_strength_step` | ✅ | ✅ | ✅ | 实现方式相同 |
| | `fire_mode_disabled` | ✅ | ✅ | ✅ | 实现方式相同 |
| | `enable_panel_control` | ✅ | ✅ | ✅ | 实现方式相同 |
| **状态查询** | `get_current_channel()` | ✅ | ✅ | ✅ | 实现方式相同 |
| | `get_last_strength()` | ✅ | ✅ | ✅ | 实现方式相同 |
| | `is_dynamic_bone_enabled()` | ✅ | ✅ | ✅ | 实现方式相同 |
| | `get_pulse_mode()` | ✅ | ✅ | ✅ | 实现方式相同 |
| | `get_current_pulse_name()` | ✅ | ✅ | ✅ | 蓝牙：通过core_interface获取，WebSocket：直接获取 |
| **通道控制** | `set_channel()` | ✅ | ✅ | ✅ | 蓝牙：根据强度比例，WebSocket：根据数值范围 |
| **强度控制** | `set_float_output()` | ✅ | ✅ | ✅ | 蓝牙：使用强度上限，WebSocket：使用动态映射 |
| | `adjust_strength()` | ✅ | ✅ | ✅ | 蓝牙：同步设置两通道，WebSocket：单独设置 |
| | `reset_strength()` | ✅ | ✅ | ✅ | 实现方式相同 |
| | `increase_strength()` | ✅ | ✅ | ✅ | 实现方式相同 |
| | `decrease_strength()` | ✅ | ✅ | ✅ | 实现方式相同 |
| **波形控制** | `update_pulse_data()` | ✅ | ✅ | ✅ | 蓝牙：更新设备脉冲数据，WebSocket：设置波形任务 |
| | `set_pulse_data()` | ✅ | ✅ | ✅ | 蓝牙：更新波形数据，WebSocket：验证索引后更新 |
| | `set_test_pulse()` | ✅ | ✅ | ✅ | 蓝牙：发送脉冲数据，WebSocket：设置波形任务 |
| | `set_pulse_mode()` | ✅ | ✅ | ✅ | 蓝牙：直接设置，WebSocket：边界检查后设置 |
| **模式控制** | `set_dynamic_bone_mode()` | ✅ | ✅ | ✅ | 实现方式相同 |
| | `set_mode()` | ✅ | ✅ | ✅ | 实现方式相同 |
| | `set_panel_control()` | ✅ | ✅ | ✅ | 蓝牙：简单设置，WebSocket：更新UI组件 |
| | `set_strength_step()` | ✅ | ✅ | ✅ | 蓝牙：直接设置，WebSocket：映射后更新UI |
| **开火模式** | `strength_fire_mode()` | ✅ | ✅ | ✅ | 蓝牙：简单强度调整，WebSocket：复杂状态管理 |
| **数据更新** | `update_strength_data()` | ✅ | ✅ | ✅ | 蓝牙：通知UI更新，WebSocket：设置事件通知 |
| **蓝牙特有** | `is_connected()` | ❌ | ✅ | ❌ | 蓝牙连接状态检查 |
| | `connect()` | ❌ | ✅ | ❌ | 蓝牙设备连接 |
| | `disconnect()` | ❌ | ✅ | ❌ | 蓝牙设备断开 |
| **WebSocket特有** | `_handle_connection_lifecycle()` | ❌ | ❌ | ✅ | 连接生命周期管理 |
| | `_handle_data()` | ❌ | ❌ | ✅ | 统一数据处理 |
| | `_attempt_reconnection()` | ❌ | ❌ | ✅ | 自动重连机制 |

## 主要差异总结

### 1. 连接方式
- **蓝牙服务**: 使用pydglab库直连设备，建立点对点连接
- **WebSocket服务**: 使用pydglab_ws库建立服务器，支持多客户端连接

### 2. 状态管理
- **蓝牙服务**: 简单的连接状态管理
- **WebSocket服务**: 复杂的连接状态管理，包含重连机制和生命周期管理

### 3. 波形处理
- **蓝牙服务**: 直接发送脉冲数据到设备
- **WebSocket服务**: 使用任务管理波形播放，支持更复杂的波形控制

### 4. UI更新机制
- **蓝牙服务**: 基本的UI状态更新
- **WebSocket服务**: 丰富的UI状态更新和事件通知机制

### 5. 错误处理
- **蓝牙服务**: 基本的异常捕获和日志记录
- **WebSocket服务**: 完善的错误处理、重试机制和状态恢复

### 6. 性能优化
- **蓝牙服务**: 使用简单的状态检查
- **WebSocket服务**: 使用事件驱动替代轮询，提高响应效率

## 实现一致性

两个实现都完整实现了`IDGLabService`接口定义，确保了功能的一致性。虽然在具体实现细节上有显著差异，但这些差异主要体现在：

- 底层通信协议的不同
- 连接管理策略的差异
- 错误处理和恢复机制的复杂度
- UI交互的丰富程度

这种设计模式允许系统在不同连接方式下保持统一的API接口，同时充分利用各自技术栈的优势。
