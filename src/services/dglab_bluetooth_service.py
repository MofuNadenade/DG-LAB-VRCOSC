"""
DG-LAB 蓝牙直连服务实现

基于pydglab库实现的蓝牙直连设备服务，实现IDGLabService接口。
"""

import asyncio
from typing import Optional, List, Union, Dict
import logging

# 使用正确的pydglab导入
import pydglab
from pydglab import model_v3

# 导入新的类型定义
from core.core_interface import CoreInterface
from models import Channel, StrengthData, StrengthOperationType, PulseOperation, UIFeature
from core.dglab_pulse import Pulse

logger = logging.getLogger(__name__)


class BluetoothChannelPulseTask:
    """蓝牙通道脉冲任务实现"""
    
    def __init__(self, channel: Channel, bluetooth_service: 'DGLabBluetoothService') -> None:
        super().__init__()
        self.channel = channel
        self.bluetooth_service = bluetooth_service
        self.task: Optional[asyncio.Task[None]] = None
        self._current_pulse: Optional[Pulse] = None
        self._current_pulse_data: List[PulseOperation] = []
        logger.info(f"蓝牙脉冲任务初始化 - 通道: {channel}")
    
    def set_pulse(self, pulse: Pulse) -> None:
        """设置脉冲波形"""
        self._current_pulse = pulse
        if pulse and pulse.data:
            self.set_pulse_data(pulse.data)
        logger.info(f"蓝牙设置脉冲波形: {pulse.name if pulse else 'None'}")
    
    def set_pulse_data(self, data: List[PulseOperation]) -> None:
        """设置脉冲数据"""
        self._current_pulse_data = data.copy()
        # 异步更新到蓝牙设备
        asyncio.create_task(self.update_device_pulse_data())
        logger.info(f"蓝牙设置脉冲数据: {len(data)}个操作")
    
    async def update_device_pulse_data(self) -> None:
        """更新设备脉冲数据"""
        if self.bluetooth_service.is_connected() and self._current_pulse_data:
            try:
                await self.bluetooth_service.send_pulse_data(self.channel, self._current_pulse_data)
            except Exception as e:
                logger.error(f"更新蓝牙设备脉冲数据失败: {e}")


class DGLabBluetoothService:
    """DG-LAB蓝牙直连服务"""
    
    def __init__(self, core_interface: CoreInterface) -> None:
        """初始化蓝牙服务"""
        super().__init__()
        self._core_interface: CoreInterface = core_interface
        self._dglab_instance: Optional['pydglab.dglab_v3'] = None
        self._is_connected: bool = False
        self._last_strength: Optional[StrengthData] = None
        self._current_channel: Channel = Channel.A
        
        # 服务状态
        self._fire_mode_strength_step: int = 5
        self._fire_mode_disabled: bool = False
        self._enable_panel_control: bool = True
        
        # 波形管理
        self._pulse_modes: Dict[Channel, int] = {Channel.A: 0, Channel.B: 0}
        
        # 强度上限、强度系数、频率系数
        self._strength_limit: int = 200  # 强度上限
        self._strength_coefficient: int = 100  # 强度系数
        self._frequency_coefficient: int = 100  # 频率系数
        
        # 通道脉冲任务
        self._channel_pulse_tasks: Dict[Channel, BluetoothChannelPulseTask] = {}
        
        # 动态骨骼状态
        self._dynamic_bone_modes: Dict[Channel, bool] = {Channel.A: False, Channel.B: False}
        
        # 当前强度缓存
        self._current_strength_a: int = 0
        self._current_strength_b: int = 0
        
        # 服务器状态
        self._server_running: bool = False
        self._stop_event: asyncio.Event = asyncio.Event()
        
        # 模式切换定时器
        self._set_mode_timer: Optional[asyncio.Task[None]] = None
        
        logger.info("蓝牙服务已初始化")
    
    # ==================== IDGLabService接口实现 ====================
    
    async def start_service(self) -> bool:
        """启动蓝牙服务"""
        try:
            logger.info("开始启动蓝牙服务...")
            self._server_running = True
            self._stop_event.clear()
            
            # 蓝牙服务启动成功
            logger.info("蓝牙服务启动成功")
            return True
            
        except Exception as e:
            logger.error(f"启动蓝牙服务失败: {e}")
            self._server_running = False
            return False
    
    async def stop_service(self) -> None:
        """停止蓝牙服务"""
        try:
            logger.info("正在停止蓝牙服务...")
            self._server_running = False
            self._stop_event.set()
            
            # 断开蓝牙连接
            if self._is_connected:
                await self.disconnect()
                
            # 取消所有波形任务
            for task_manager in self._channel_pulse_tasks.values():
                if task_manager.task and not task_manager.task.done():
                    task_manager.task.cancel()
            
            logger.info("蓝牙服务已停止")
            
        except Exception as e:
            logger.error(f"停止蓝牙服务失败: {e}")
    
    def is_server_running(self) -> bool:
        """检查服务器运行状态"""
        return self._server_running
    
    def get_connection_type(self) -> str:
        """获取连接类型标识"""
        return "bluetooth"
    
    async def wait_for_server_stop(self) -> None:
        """等待服务器停止事件"""
        await self._stop_event.wait()
    
    # ==================== 连接管理 ====================
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._is_connected and self._dglab_instance is not None
    
    async def connect(self) -> bool:
        """连接到DG-LAB设备"""
        try:
            logger.info("开始扫描DG-LAB蓝牙设备...")
            
            # 扫描设备
            await pydglab.scan()
            
            # 创建dglab_v3实例
            self._dglab_instance = pydglab.dglab_v3()
            
            # 尝试连接设备
            try:
                await self._dglab_instance.create()
            except TimeoutError:
                logger.warning("连接超时，重试中...")
                await self._dglab_instance.create()
            
            self._is_connected = True
            
            # 初始化设备设置
            await self._initialize_device()
            
            # 初始化通道脉冲任务
            self._update_channel_pulse_tasks()
            
            logger.info("蓝牙设备连接成功")
            
            # 通知UI
            if self._core_interface:
                self._core_interface.on_client_connected()
            
            return True
            
        except Exception as e:
            logger.error(f"蓝牙设备连接失败: {e}")
            self._is_connected = False
            if self._dglab_instance:
                try:
                    await self._dglab_instance.close()
                except:
                    pass
                self._dglab_instance = None
            return False
    
    async def disconnect(self) -> bool:
        """断开设备连接"""
        try:
            if self._dglab_instance:
                await self._dglab_instance.close()
                self._dglab_instance = None
            
            self._is_connected = False
            logger.info("蓝牙设备已断开连接")
            
            # 清空通道脉冲任务
            self._update_channel_pulse_tasks()
            
            # 通知UI
            if self._core_interface:
                self._core_interface.on_client_disconnected()
            
            return True
            
        except Exception as e:
            logger.error(f"断开蓝牙设备失败: {e}")
            return False
    
    # ==================== 属性访问器 ====================
    
    @property
    def fire_mode_strength_step(self) -> int:
        """获取开火模式强度步进"""
        return self._fire_mode_strength_step
    
    @fire_mode_strength_step.setter
    def fire_mode_strength_step(self, value: int) -> None:
        """设置开火模式强度步进"""
        self._fire_mode_strength_step = value
        logger.info(f"蓝牙设置开火模式强度步进为: {value}")
    
    @property
    def fire_mode_disabled(self) -> bool:
        """获取开火模式是否禁用"""
        return self._fire_mode_disabled
    
    @fire_mode_disabled.setter
    def fire_mode_disabled(self, value: bool) -> None:
        """设置开火模式禁用状态"""
        self._fire_mode_disabled = value
        logger.info(f"蓝牙设置开火模式禁用状态为: {value}")
    
    @property
    def enable_panel_control(self) -> bool:
        """获取面板控制启用状态"""
        return self._enable_panel_control
    
    @enable_panel_control.setter
    def enable_panel_control(self, value: bool) -> None:
        """设置面板控制启用状态"""
        self._enable_panel_control = value
        logger.info(f"蓝牙设置面板控制启用状态为: {value}")
    
    @property
    def strength_limit(self) -> int:
        """获取强度上限"""
        return self._strength_limit
    
    @strength_limit.setter
    def strength_limit(self, value: int) -> None:
        """设置强度上限"""
        self._strength_limit = value
        logger.info(f"蓝牙设置强度上限为: {value}")
    
    @property
    def strength_coefficient(self) -> int:
        """获取强度系数"""
        return self._strength_coefficient
    
    @strength_coefficient.setter
    def strength_coefficient(self, value: int) -> None:
        """设置强度系数"""
        self._strength_coefficient = value
        logger.info(f"蓝牙设置强度系数为: {value}")
    
    @property
    def frequency_coefficient(self) -> int:
        """获取频率系数"""
        return self._frequency_coefficient
    
    @frequency_coefficient.setter
    def frequency_coefficient(self, value: int) -> None:
        """设置频率系数"""
        self._frequency_coefficient = value
        logger.info(f"蓝牙设置频率系数为: {value}")
    
    # ==================== 状态查询接口 ====================
    
    def get_current_channel(self) -> Channel:
        """获取当前选中的通道"""
        return self._current_channel
    
    def get_last_strength(self) -> Optional[StrengthData]:
        """获取最后的强度数据"""
        return self._last_strength
    
    def is_dynamic_bone_enabled(self, channel: Channel) -> bool:
        """检查指定通道的动骨模式是否启用"""
        return self._dynamic_bone_modes[channel]
    
    def get_pulse_mode(self, channel: Channel) -> int:
        """获取指定通道的波形模式索引"""
        return self._pulse_modes[channel]
    
    def get_current_pulse_name(self, channel: Channel) -> str:
        """获取当前通道的波形名称"""
        pulse_index = self.get_pulse_mode(channel)
        if self._core_interface:
            try:
                pulse = self._core_interface.registries.pulse_registry.get_pulse_by_index(pulse_index)
                if pulse:
                    return pulse.name
            except (IndexError, AttributeError):
                pass
        return f"蓝牙波形{pulse_index}"
    
    # ==================== 通道控制接口 ====================
    
    async def set_channel(self, value: Union[int, float]) -> Optional[Channel]:
        """设置当前通道"""
        # 根据强度比例确定通道
        if value < 0.5:
            self._current_channel = Channel.A
        else:
            self._current_channel = Channel.B
        
        logger.info(f"蓝牙切换到通道: {self._current_channel}")
        return self._current_channel
    
    # ==================== 强度控制接口 ====================
    
    async def set_float_output(self, value: float, channel: Channel) -> None:
        """设置浮点输出强度（用于动骨模式）"""
        if not self._enable_panel_control:
            return

        if value >= 0.0 and self._last_strength:
            if channel == Channel.A and self._dynamic_bone_modes[Channel.A]:
                strength = int(value * self._strength_limit)  # 将浮点值转换为强度（0-强度上限范围）
                await self.adjust_strength(StrengthOperationType.SET_TO, strength, channel)
                logger.info(f"蓝牙浮点输出: 通道{channel}强度设置为{strength}")
            elif channel == Channel.B and self._dynamic_bone_modes[Channel.B]:
                strength = int(value * self._strength_limit)  # 将浮点值转换为强度（0-强度上限范围）
                await self.adjust_strength(StrengthOperationType.SET_TO, strength, channel)
                logger.info(f"蓝牙浮点输出: 通道{channel}强度设置为{strength}")
    
    async def adjust_strength(self, operation_type: StrengthOperationType, value: int, channel: Channel) -> None:
        """调整通道强度"""
        if not self.is_connected():
            logger.warning("设备未连接，无法调整强度")
            return
        
        try:
            current_strength: int = self._current_strength_a if channel == Channel.A else self._current_strength_b
            target_strength: int
            
            if operation_type == StrengthOperationType.SET_TO:
                target_strength = value
            elif operation_type == StrengthOperationType.INCREASE:
                target_strength = current_strength + value
            elif operation_type == StrengthOperationType.DECREASE:
                target_strength = current_strength - value
            
            # 限制强度范围
            target_strength = max(0, min(self._strength_limit, target_strength))
            
            # 更新内部状态
            if channel == Channel.A:
                self._current_strength_a = target_strength
            else:
                self._current_strength_b = target_strength
            
            # 同步设置两个通道的强度
            if self._dglab_instance:
                await self._dglab_instance.set_strength_sync(self._current_strength_a, self._current_strength_b)
            
            # 更新强度数据
            self._last_strength = StrengthData(
                a=self._current_strength_a, 
                b=self._current_strength_b,
                a_limit=self._strength_limit,
                b_limit=self._strength_limit
            )
            
            # 通知UI更新
            if self._core_interface:
                self._core_interface.update_status(self._last_strength)
            
            logger.info(f"蓝牙调整通道{channel}强度为: {target_strength}")
            
        except Exception as e:
            logger.error(f"蓝牙调整强度失败: {e}")
    
    async def reset_strength(self, value: bool, channel: Channel) -> None:
        """重置通道强度"""
        if value:
            await self.adjust_strength(StrengthOperationType.SET_TO, 0, channel)
            logger.info(f"蓝牙重置通道{channel}强度为0")
    
    async def increase_strength(self, value: bool, channel: Channel) -> None:
        """增大强度, 固定 1"""
        if value:
            await self.adjust_strength(StrengthOperationType.INCREASE, 1, channel)
            logger.info(f"蓝牙增大通道{channel}强度")
    
    async def decrease_strength(self, value: bool, channel: Channel) -> None:
        """减小强度, 固定 1"""
        if value:
            await self.adjust_strength(StrengthOperationType.DECREASE, 1, channel)
            logger.info(f"蓝牙减小通道{channel}强度")
    
    # ==================== 波形控制接口 ====================
    
    async def update_pulse_data(self) -> None:
        """更新波形数据"""
        try:
            # 更新A通道波形
            await self._channel_pulse_tasks[Channel.A].update_device_pulse_data()
            # 更新B通道波形
            await self._channel_pulse_tasks[Channel.B].update_device_pulse_data()
            
            logger.info("蓝牙波形数据更新完成")
            
        except Exception as e:
            logger.error(f"蓝牙更新波形数据失败: {e}")
    
    async def set_pulse_data(self, channel: Channel, pulse_index: int, update_ui: bool = True) -> None:
        """设置指定通道的波形数据"""
        self._pulse_modes[channel] = pulse_index
        
        # 更新波形数据
        await self.update_pulse_data()
        logger.info(f"蓝牙切换通道{channel}波形为索引{pulse_index}")
    
    async def set_test_pulse(self, channel: Channel, pulse: Pulse) -> None:
        """在指定通道播放测试波形"""
        if pulse and pulse.data:
            await self.send_pulse_data(channel, pulse.data)
            logger.info(f"蓝牙播放测试波形: 通道{channel}, 波形{pulse.name}")
    
    def set_pulse_mode(self, channel: Channel, value: int) -> None:
        """设置指定通道的波形模式"""
        self._pulse_modes[channel] = value
        logger.info(f"蓝牙设置通道{channel}波形模式为: {value}")
    
    # ==================== 模式控制接口 ====================
    
    def set_dynamic_bone_mode(self, channel: Channel, enabled: bool) -> None:
        """设置指定通道的动骨模式"""
        self._dynamic_bone_modes[channel] = enabled
        logger.info(f"蓝牙设置通道{channel}动态骨骼模式: {enabled}")
    
    async def set_mode(self, value: int, channel: Channel) -> None:
        """切换工作模式（延时触发）"""
        if value == 1:  # 按下按键
            if self._set_mode_timer is not None:
                self._set_mode_timer.cancel()
            self._set_mode_timer = asyncio.create_task(self._set_mode_timer_handle(channel))
        elif value == 0:  # 松开按键
            if self._set_mode_timer:
                self._set_mode_timer.cancel()
                self._set_mode_timer = None
    
    async def set_panel_control(self, value: float) -> None:
        """面板控制功能开关"""
        self._enable_panel_control = value > 0.5
        logger.info(f"蓝牙设置面板控制: {self._enable_panel_control}")
    
    async def set_strength_step(self, value: float) -> None:
        """开火模式步进值设定"""
        self._fire_mode_strength_step = int(value)
        logger.info(f"蓝牙设置强度步进值为: {self._fire_mode_strength_step}")
    
    # ==================== 开火模式接口 ====================
    
    async def strength_fire_mode(self, value: bool, channel: Channel, fire_strength: int, last_strength: Optional[StrengthData]) -> None:
        """开火模式强度控制"""
        if value and not self._fire_mode_disabled:
            # 计算目标强度
            current_strength = self._current_strength_a if channel == Channel.A else self._current_strength_b
            target_strength = min(current_strength + fire_strength, self._strength_limit)
            await self.adjust_strength(StrengthOperationType.SET_TO, target_strength, channel)
            logger.info(f"蓝牙开火模式: 通道{channel}强度设置为{target_strength}")
        else:
            logger.debug("蓝牙开火模式被禁用或未触发")
    
    # ==================== 数据更新接口 ====================
    
    def update_strength_data(self, strength_data: StrengthData) -> None:
        """更新强度数据"""
        self._last_strength = strength_data
        self._current_strength_a = strength_data.a
        self._current_strength_b = strength_data.b
        
        # 通知UI更新
        if self._core_interface:
            self._core_interface.update_status(strength_data)
    
    # ==================== 内部方法 ====================
    
    async def _set_mode_timer_handle(self, channel: Channel) -> None:
        """模式切换计时器处理"""
        try:
            # 使用更精确的延迟，避免不必要的轮询
            await asyncio.sleep(1.0)

            new_mode = not self._dynamic_bone_modes[channel]
            self.set_dynamic_bone_mode(channel, new_mode)
            mode_name = "可交互模式" if new_mode else "面板设置模式"
            logger.info(f"通道 {self._get_channel_name(channel)} 切换为{mode_name}")
            # 更新UI
            ui_feature = self._get_dynamic_bone_ui_feature(channel)
            if self._core_interface:
                self._core_interface.set_feature_state(ui_feature, new_mode, silent=True)
        except asyncio.CancelledError:
            logger.debug(f"通道 {self._get_channel_name(channel)} 模式切换计时器已取消")
            raise

    async def _initialize_device(self) -> None:
        """初始化设备设置"""
        if not self._dglab_instance:
            return
        
        try:
            # 设置系数 (强度上限, 强度系数, 频率系数)
            await self._dglab_instance.set_coefficient(self._strength_limit, self._strength_coefficient, self._frequency_coefficient, model_v3.ChannelA) # type: ignore
            await self._dglab_instance.set_coefficient(self._strength_limit, self._strength_coefficient, self._frequency_coefficient, model_v3.ChannelB) # type: ignore
            
            # 获取当前强度
            strength_a, strength_b = await self._dglab_instance.get_strength()
            self._current_strength_a = strength_a
            self._current_strength_b = strength_b
            
            # 更新强度数据
            self._last_strength = StrengthData(
                a=strength_a, 
                b=strength_b,
                a_limit=self._strength_limit,
                b_limit=self._strength_limit
            )
            
            # 初始化波形为静止状态
            await self._dglab_instance.set_wave_sync(0, 0, 0, 0, 0, 0)
            
            logger.info(f"设备初始化完成 - 当前强度 A:{strength_a}, B:{strength_b}")
            
        except Exception as e:
            logger.error(f"初始化设备设置失败: {e}")
    
    async def send_pulse_data(self, channel: Channel, data: List[PulseOperation]) -> None:
        """发送脉冲数据到设备"""
        if not self.is_connected() or not data:
            return
        
        try:
            # 将PulseOperation转换为pydglab的波形格式
            wave_set = self._convert_pulse_operations_to_wave_set(data)
            
            # 根据通道设置波形
            if self._dglab_instance:
                if channel == Channel.A:
                    await self._dglab_instance.set_wave_set(wave_set, model_v3.ChannelA) # type: ignore 
                else:
                    await self._dglab_instance.set_wave_set(wave_set, model_v3.ChannelB) # type: ignore
            
            logger.debug(f"蓝牙发送脉冲数据到通道{channel}: {len(data)}个操作")
            
        except Exception as e:
            logger.error(f"蓝牙发送脉冲数据失败: {e}")
    
    def _convert_pulse_operations_to_wave_set(self, operations: List[PulseOperation]) -> List[tuple[int, int, int]]:
        """将PulseOperation转换为pydglab的波形集合格式"""
        wave_set: List[tuple[int, int, int]] = []
        
        for op in operations:
            # 从PulseOperation中提取参数
            # PulseOperation是(freq_op, strength_op)的元组
            freq_op, strength_op = op
            
            # 提取频率和强度值（取第一个值作为代表）
            frequency = freq_op[0] if freq_op else 10
            strength = strength_op[0] if strength_op else 0
            
            # 转换为pydglab的波形格式 (waveX, waveY, waveZ)
            # waveX: 连续发出X个脉冲，每个脉冲持续1ms
            # waveY: 发出脉冲后停止Y个周期，每个周期持续1ms  
            # waveZ: 每个脉冲的宽度为Z*5us
            wave_x = min(max(1, frequency), 100)
            wave_y = min(max(1, 100), 1000)  # 固定持续时间
            wave_z = min(max(1, strength // 5), 200)
            
            wave_set.append((wave_x, wave_y, wave_z))
        
        # 如果没有有效的波形数据，返回静止波形
        if not wave_set:
            wave_set = [(0, 0, 0)]
        
        return wave_set

    def _get_channel_name(self, channel: Channel) -> str:
        """获取通道名称"""
        return "A" if channel == Channel.A else "B"

    def _get_dynamic_bone_ui_feature(self, channel: Channel) -> UIFeature:
        """获取动骨模式对应的UI特性"""
        return UIFeature.DYNAMIC_BONE_A if channel == Channel.A else UIFeature.DYNAMIC_BONE_B

    def _update_channel_pulse_tasks(self) -> None:
        """更新通道波形任务（当连接状态变化时）"""
        if self.is_connected():
            self._channel_pulse_tasks = {
                Channel.A: BluetoothChannelPulseTask(Channel.A, self),
                Channel.B: BluetoothChannelPulseTask(Channel.B, self)
            }
            logger.debug("通道波形任务已初始化")
        else:
            self._channel_pulse_tasks.clear()
            logger.debug("通道波形任务已清空")
