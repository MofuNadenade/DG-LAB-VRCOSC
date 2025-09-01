# DG-LAB V3 蓝牙控制模块

基于郊狼情趣脉冲主机V3协议的蓝牙LE控制实现。

## 模块架构

```
bluetooth/
├── __init__.py           # 模块导出
├── bluetooth_models.py   # V3协议数据模型
├── bluetooth_protocol.py # V3协议处理器  
├── bluetooth_controller.py # 高级蓝牙控制器
└── README.md            # 本文档
```

## 核心组件

### 1. 数据模型 (bluetooth_models.py)

#### 基础类型
```python
PulseOperation = Tuple[
    WaveformFrequencyOperation,  # 4个频率值 (10-240)
    WaveformStrengthOperation    # 4个强度值 (0-100)
]

WaveformFrequencyOperation = Tuple[int, int, int, int]
WaveformStrengthOperation = Tuple[int, int, int, int]
```

#### 设备状态
```python
DeviceState = TypedDict({
    'channel_a': ChannelState,
    'channel_b': ChannelState, 
    'is_connected': bool,
    'battery_level': int
})

ChannelState = TypedDict({
    'strength': int,                    # 当前强度 (0-200)
    'strength_limit': int,              # 强度软上限 (0-200)  
    'frequency_balance': int,           # 频率平衡参数1 (0-255)
    'strength_balance': int,            # 强度平衡参数2 (0-255)
    'pulses': List[PulseOperation]      # 波形操作数据
})
```

#### 协议指令
- **B0Command**: 20字节强度+波形控制指令
- **BFCommand**: 7字节软上限+平衡参数设置指令
- **B1Response**: 4字节强度回应消息

### 2. 协议处理器 (bluetooth_protocol.py)

纯协议层实现，负责V3协议的数据处理和转换：

#### 核心功能
- B0指令构建与解析
- BF指令构建与解析  
- B1回应解析
- 数据验证 (`validate_wave_frequency`, `validate_wave_strength`)
- 强度解读方式处理

#### 频率转换算法
支持10-1000Hz输入，自动转换为10-240协议值：
```python
# 输入10-100Hz → 直接使用
# 输入101-600Hz → (输入-100)/5+100  
# 输入601-1000Hz → (输入-600)/10+200
```

### 3. 蓝牙控制器 (bluetooth_controller.py)

高级控制接口，提供设备管理和波形控制：

#### 连接管理
- `scan_devices()` - 扫描V3设备
- `connect_device()` - 连接到设备
- `disconnect_device()` - 断开连接

#### 强度控制
- `set_strength_absolute()` - 绝对设置强度
- `set_strength_relative()` - 相对调整强度  
- `set_strength_to_zero()` - 强度归零

#### 波形控制（核心功能）
- `set_wave_data(channel, pulses: List[PulseOperation])` - 设置波形数据
- `clear_wave_data(channel)` - 清除波形数据
- `_get_current_wave_data(channel)` - 获取当前波形（循环播放）

## 波形循环播放机制

### 工作原理
1. **数据存储**: `List[PulseOperation]` 存储在对应通道
2. **循环索引**: 每个通道维护独立的 `_wave_index_x`  
3. **定时发送**: 每100ms发送一个B0指令，包含当前波形数据
4. **自动循环**: 索引到达末尾时自动回到开头

### 时序说明
```
时间: 0ms    100ms   200ms   300ms   400ms
索引: [0] -> [1] -> [2] -> [0] -> [1] -> ...
数据: 每个PulseOperation包含4组25ms的波形数据
```

### 使用示例
```python
# 设置循环播放的波形数据
pulses = [
    ((20, 30, 40, 50), (10, 20, 30, 40)),  # 第1个100ms
    ((50, 40, 30, 20), (40, 30, 20, 10)),  # 第2个100ms  
    ((30, 30, 30, 30), (25, 25, 25, 25)),  # 第3个100ms
]

await controller.set_wave_data(Channel.A, pulses)
# 每100ms自动循环发送，创建连续的波形输出
```

## 协议常量

```python
class ProtocolConstants:
    # 数据范围
    STRENGTH_MIN = 0
    STRENGTH_MAX = 200
    WAVE_FREQUENCY_MIN = 10      
    WAVE_FREQUENCY_MAX = 240     
    WAVE_STRENGTH_MIN = 0
    WAVE_STRENGTH_MAX = 100
    
    # 发送间隔
    DATA_SEND_INTERVAL = 0.1  # 100ms
    
    # 默认值
    DEFAULT_STRENGTH_LIMIT = 200
    DEFAULT_FREQUENCY_BALANCE = 100
    DEFAULT_STRENGTH_BALANCE = 100
```

## 蓝牙规格

### 设备名称
- 脉冲主机3.0: `47L121000`
- 无线传感器: `47L120100`

### GATT服务特性
```python
class BluetoothUUIDs:
    SERVICE_WRITE = "0000180c-0000-1000-8000-00805f9b34fb"
    SERVICE_NOTIFY = "0000180c-0000-1000-8000-00805f9b34fb"  
    SERVICE_BATTERY = "0000180a-0000-1000-8000-00805f9b34fb"
    
    CHARACTERISTIC_WRITE = "0000150a-0000-1000-8000-00805f9b34fb"
    CHARACTERISTIC_NOTIFY = "0000150b-0000-1000-8000-00805f9b34fb"
    CHARACTERISTIC_BATTERY = "00001500-0000-1000-8000-00805f9b34fb"
```

## 关键特性

### 强类型安全
所有数据类型都有严格的类型标注和验证：
```python
self._wave_data_a: List[PulseOperation] = []
self._wave_data_b: List[PulseOperation] = []
self._device_state: DeviceState = self._create_device_state()
```

### 异步架构
全面使用async/await模式，支持非阻塞操作：
```python
async def set_wave_data(self, channel: Channel, pulses: List[PulseOperation]) -> bool
async def connect_device(self, device: DeviceInfo) -> bool
```

### 错误处理
完善的异常处理和日志记录：
```python
try:
    # 协议操作
except Exception as e:
    logger.error(f"操作失败: {e}")
    return False
```

### 状态管理
- 实时设备状态跟踪
- 序列号管理防止指令冲突
- 连接状态监控和自动恢复

## 开发注意事项

1. **数据验证**: 所有输入数据都会进行范围验证
2. **循环播放**: 空的波形数据会返回静止状态 `((10,10,10,10), (0,0,0,0))`
3. **通道独立**: AB两个通道的波形数据和索引完全独立管理
4. **协议兼容**: 严格遵循V3协议规范，确保硬件兼容性
5. **性能优化**: 避免频繁的内存分配，使用高效的数据结构

## 依赖项

- `bleak`: 跨平台蓝牙LE库
- `asyncio`: 异步编程支持
- `typing`: 类型标注支持
- `struct`: 二进制数据打包/解包