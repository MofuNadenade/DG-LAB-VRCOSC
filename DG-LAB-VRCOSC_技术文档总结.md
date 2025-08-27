# DG-LAB-VRCOSC 技术文档总结

## 项目概述

**DG-LAB-VRCOSC** 是一个与 **VRChat** 游戏联动的郊狼 (DG-LAB) **3.0** 设备控制程序，通过 VRChat 游戏内的 avatars 互动和其他事件来控制设备的输出。

### 主要功能特性

- **VRChat Avatar 联动功能 (OSC)**：
  - 面板控制模式：通过 VRSuya 的 SoundPad 进行控制
  - 交互控制模式：支持 Contact 或 Physbones 参数控制
  - ChatBox 显示：显示当前设备信息
  - 远程控制：通过 avatar 上的面板控制其他玩家的设备

- **Terrors of Nowhere 游戏联动**：
  - 游戏内伤害增加设备输出
  - 游戏内死亡触发死亡惩罚
  - 通过 ToNSaveManager 的 WebSocket API 监控游戏事件

## 技术架构

### 整体架构设计

```
DG-LAB-VRCOSC
├── 核心层 (Core)
│   ├── 脉冲管理 (dglab_pulse.py)
│   ├── OSC 绑定 (osc_binding.py)
│   ├── OSC 动作 (osc_action.py)
│   └── 核心接口 (core_interface.py)
├── 服务层 (Services)
│   ├── 蓝牙服务 (dglab_bluetooth_service.py)
│   ├── WebSocket 服务 (dglab_websocket_service.py)
│   ├── OSC 服务 (osc_service.py)
│   └── ChatBox 服务 (chatbox_service.py)
├── GUI 层 (GUI)
│   ├── 主窗口 (main_window.py)
│   ├── 脉冲编辑器 (pulse_editor_tab.py)
│   ├── 网络配置 (network_config_tab.py)
│   └── 控制器设置 (controller_settings_tab.py)
└── 工具层 (Utils)
    ├── 国际化 (i18n.py)
    ├── 日志配置 (logger_config.py)
    └── 版本管理 (version.py)
```

### 核心模块分析

#### 1. 脉冲管理系统 (dglab_pulse.py)

```python
class Pulse:
    """脉冲波形定义"""
    def __init__(self, index: int, name: str, data: List[PulseOperation]):
        self.index: int = index          # 脉冲索引
        self.name: str = name            # 脉冲名称
        self.data: List[PulseOperation] = data  # 脉冲数据

class PulseRegistry:
    """脉冲注册表管理"""
    def register_pulse(self, name: str, data: List[PulseOperation]) -> Pulse
    def get_pulse_by_name(self, name: str) -> Optional[Pulse]
    def load_from_config(self, pulses_config: Dict[str, List[PulseOperation]])
```

#### 2. 蓝牙服务 (dglab_bluetooth_service.py)

基于 `pydglab` 库实现，支持 DG-LAB 3.0 主机的蓝牙直连：

```python
class DGLabBluetoothService:
    """DG-LAB蓝牙直连服务"""
    
    async def _initialize_device(self):
        """初始化设备设置"""
        # 设置系数 (强度上限, 强度系数, 频率系数)
        await self._dglab_instance.set_coefficient(100, 100, 100, model_v3.ChannelA)
        await self._dglab_instance.set_coefficient(100, 100, 100, model_v3.ChannelB)
        
        # 获取当前强度
        strength_a, strength_b = await self._dglab_instance.get_strength()
        
        # 初始化波形为静止状态
        await self._dglab_instance.set_wave_sync(0, 0, 0, 0, 0, 0)
```

#### 3. 数据模型 (models.py)

定义了核心数据类型和枚举：

```python
# 波形数据类型
WaveformFrequency = int          # 波形频率 [10, 240]
WaveformStrength = int           # 波形强度 [0, 100]

# 脉冲操作数据
PulseOperation = Tuple[
    WaveformFrequencyOperation,  # 4个频率值
    WaveformStrengthOperation    # 4个强度值
]

# 通道枚举
class Channel(IntEnum):
    A = 1
    B = 2

# 强度操作类型
class StrengthOperationType(IntEnum):
    DECREASE = 0    # 减少
    INCREASE = 1    # 增加
    SET_TO = 2      # 设置为指定值
```

## DG-LAB 3.0 协议分析

### 蓝牙特性

| 服务 UUID | 特性 UUID | 属性 | 名称 | 大小(BYTE) | 说明 |
|-----------|-----------|------|------|-------------|------|
| 0x180C | 0x150A | 写 | WRITE | 最长 20 字节 | 所有指令输入 |
| 0x180C | 0x150B | 通知 | NOTIFY | 最长 20 字节 | 所有回应消息 |
| 0x180A | 0x1500 | 读/通知 | READ/NOTIFY | 1 字节 | 电量信息 |

### 核心指令协议

#### B0 指令 - 通道强度和波形控制

**指令格式：**
```
0xB0 + 序列号(4bits) + 强度值解读方式(4bits) + 
A通道强度设定值(1byte) + B通道强度设定值(1byte) + 
A通道波形频率4条(4bytes) + A通道波形强度4条(4bytes) + 
B通道波形频率4条(4bytes) + B通道波形强度4条(4bytes)
```

**强度值解读方式：**
- `0b00`: 对应通道强度不做改变
- `0b01`: 对应通道强度相对增加变化
- `0b10`: 对应通道强度相对减少变化  
- `0b11`: 对应通道强度绝对变化

**波形数据规则：**
- 每100ms发送两通道各4组波形频率和强度
- 每组频率-强度代表25ms的波形输出
- 频率范围：10~240，强度范围：0~100
- 超出范围的数据会被设备放弃

#### BF 指令 - 开火模式控制

**指令格式：**
```
0xBF + 序列号(4bits) + 开火模式(4bits) + 
A通道开火强度(1byte) + B通道开火强度(1byte) + 
开火持续时间(1byte) + 开火间隔时间(1byte) + 
A通道开火波形频率(1byte) + A通道开火波形强度(1byte) + 
B通道开火波形频率(1byte) + B通道开火波形强度(1byte)
```

**开火模式：**
- `0b0000`: 关闭开火模式
- `0b0001`: 单次开火
- `0b0010`: 连续开火
- `0b0011`: 脉冲开火

### 强度控制算法

项目实现了智能的强度累积控制算法：

```python
def strengthDataProcessingA():
    """A通道强度数据处理函数"""
    if accumulatedStrengthValueA != 0:
        if accumulatedStrengthValueA > 0:
            strengthParsingMethod = 0b0100  # 相对增加
        else:
            strengthParsingMethod = 0b1000  # 相对减少
        
        orderNo += 1
        inputOrderNo = orderNo
        isInputAllowed = false
        strengthSettingValueA = abs(accumulatedStrengthValueA)  # 取绝对值
        accumulatedStrengthValueA = 0
    else:
        orderNo = 0
        strengthParsingMethod = 0b0000  # 不做改变
        strengthSettingValueA = 0
```

## 技术实现特点

### 1. 异步架构设计

- 使用 `asyncio` 实现异步操作
- 蓝牙通信、WebSocket 连接、OSC 处理都采用异步模式
- 支持并发处理多个通道的脉冲数据

### 2. 模块化服务架构

- 每个功能模块都是独立的服务类
- 通过接口定义实现松耦合
- 支持服务的动态启动和停止

### 3. 智能脉冲管理

- 脉冲数据缓存和批量处理
- 支持实时波形更新
- 自动强度限制和范围检查

### 4. 多协议支持

- 蓝牙直连协议 (DG-LAB 3.0)
- WebSocket 协议 (ToN 游戏联动)
- OSC 协议 (VRChat 集成)
- 支持多种连接方式切换

## 配置和部署

### 环境要求

- Python 3.8+
- Windows 10/11
- 支持蓝牙的设备
- DG-LAB 3.0 主机

### 依赖库

```
pydglab          # DG-LAB 蓝牙通信库
pydantic         # 数据验证
asyncio          # 异步编程
tkinter          # GUI 界面
websockets       # WebSocket 支持
```

### 构建配置

项目使用 PyInstaller 进行打包：

```python
# DG-LAB-VRCOSC.spec
a = Analysis(
    ['src/app.py'],
    datas=[('src/locales', 'locales'), ('docs/images', 'docs/images')],
    hiddenimports=['pydglab', 'pydglab.model_v3']
)
```

## 使用说明

### 快速开始

1. 下载最新版本的 `DG-LAB-VRCOSC.zip`
2. 解压后运行主程序
3. 点击"启动"生成二维码
4. 使用 DG-LAB APP 连接设备并扫描二维码

### 功能配置

- **面板控制**：需要购买并导入 SoundPad 资源
- **ToN 游戏联动**：启用 ToNSaveManager 的 WebSocket API
- **强度设置**：根据个人情况设置合理的强度上限

## 注意事项

1. 本程序不对使用产生的任何后果负责
2. 请遵循 DG-LAB APP 的安全使用说明
3. 大部分代码使用 ChatGPT 生成，可能存在未发现的 BUG
4. 建议在使用前充分测试各项功能

## 技术亮点

1. **智能强度控制**：实现了累积强度变化的智能处理算法
2. **多协议集成**：支持蓝牙、WebSocket、OSC 等多种通信方式
3. **异步架构**：采用现代异步编程模式，提高性能和响应性
4. **模块化设计**：清晰的代码结构和接口定义，便于维护和扩展
5. **实时波形控制**：支持100ms精度的实时波形数据更新

## 未来发展方向

1. **协议扩展**：支持更多 DG-LAB 设备型号
2. **游戏集成**：增加更多游戏的联动支持
3. **AI 增强**：集成机器学习算法优化脉冲模式
4. **云端同步**：支持脉冲配置的云端存储和分享
5. **移动端支持**：开发移动端控制应用

---

*本文档基于 [DG-LAB-VRCOSC](https://github.com/ccvrc/DG-LAB-VRCOSC) 项目代码分析和 [DG-LAB 3.0 协议文档](https://github.com/DG-LAB-OPENSOURCE/DG-LAB-OPENSOURCE/raw/refs/heads/main/coyote/v3/README_V3.md) 整理而成。*
