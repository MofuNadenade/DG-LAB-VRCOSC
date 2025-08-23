import asyncio
import math
from typing import Optional, List, Union, Dict
from pydglab_ws import DGLabLocalClient, PulseDataTooLong
from models import Channel, StrengthData, PulseOperation, StrengthOperationType
from core.dglab_pulse import Pulse
import logging
from gui.ui_interface import UIInterface, UIFeature

logger = logging.getLogger(__name__)


class ChannelPulseTask:
    def __init__(self, client: DGLabLocalClient, channel: Channel) -> None:
        self.client: DGLabLocalClient = client
        self.channel: Channel = channel
        self.pulse: Optional[Pulse] = None
        self.task: Optional[asyncio.Task[None]] = None
        self.data: List[PulseOperation] = []

    def set_pulse(self, pulse: Pulse) -> None:
        """设置波形"""
        old_pulse = self.pulse
        self.pulse = pulse
        if old_pulse is None or pulse.index != old_pulse.index:
            self.set_pulse_data(pulse.data)

    def set_pulse_data(self, data: List[PulseOperation]) -> None:
        """设置波形数据"""
        self.data = data
        if self.task and not self.task.cancelled() and not self.task.done():
            self.task.cancel()
        self.task = asyncio.create_task(self._internal_task(data))

    async def _internal_task(self, data: List[PulseOperation], send_duration: float = 5, send_interval: float = 1) -> None:
        try:
            await self.client.clear_pulses(self.channel)

            data_duration = len(data) * 0.1
            repeat_num = int(send_duration // data_duration)
            duration = repeat_num * data_duration
            pulse_num = int(50 // duration)
            pulse_data = data * repeat_num

            try:
                for _ in range(pulse_num):
                    await self.client.add_pulses(self.channel, *pulse_data)
                    await asyncio.sleep(send_interval)

                await asyncio.sleep(abs(data_duration - send_interval))
                while True:
                    await self.client.add_pulses(self.channel, *pulse_data)
                    await asyncio.sleep(data_duration)
            except PulseDataTooLong:
                logger.warning(f"发送失败，波形数据过长")
        except Exception as e:
            logger.error(f"send_pulse_task 任务中发生错误: {e}")


class DGLabService:
    """
    DGLab 硬件服务 - 统一的 DGLab 功能管理
    
    这个服务整合了所有与 DGLab 硬件相关的功能：
    
    1. 通道管理:
       - A/B 通道脉冲任务管理
       - 通道选择和切换
       
    2. 强度控制:
       - 强度调节（增加、减少、重置）
       - 动骨模式管理
       - 面板控制开关
       
    3. 波形管理:
       - 波形数据更新和切换
       - 波形模式管理
       
    4. 开火模式:
       - 一键开火功能
       - 强度步进设置
       
    5. 模式切换:
       - 交互模式与面板模式切换
       - UI 状态同步
    """
    
    def __init__(self, client: DGLabLocalClient, ui_interface: 'UIInterface') -> None:
        self._client: DGLabLocalClient = client
        self._ui_interface: 'UIInterface' = ui_interface
        
        # 通道管理
        self._current_select_channel: Channel = Channel.A
        self._channel_pulse_tasks: Dict[Channel, ChannelPulseTask] = {
            Channel.A: ChannelPulseTask(client, Channel.A),
            Channel.B: ChannelPulseTask(client, Channel.B)
        }
        
        # 强度管理
        self._last_strength: Optional[StrengthData] = None
        self._dynamic_bone_modes: Dict[Channel, bool] = {Channel.A: False, Channel.B: False}
        
        # 波形管理
        self._pulse_modes: Dict[Channel, int] = {Channel.A: 0, Channel.B: 0}
        
        # 开火模式管理
        self._fire_mode_disabled: bool = False
        self._fire_mode_strength_step: int = 30
        self._fire_mode_active: bool = False
        self._fire_mode_lock: asyncio.Lock = asyncio.Lock()
        self._data_updated_event: asyncio.Event = asyncio.Event()
        self._fire_mode_origin_strengths: Dict[Channel, int] = {Channel.A: 0, Channel.B: 0}
        
        # 模式切换管理
        self._set_mode_timer: Optional[asyncio.Task[None]] = None
        
        # 面板控制
        self._enable_panel_control: bool = True

    # 属性访问器
    @property
    def fire_mode_strength_step(self) -> int:
        """获取开火模式强度步进"""
        return self._fire_mode_strength_step
    
    @fire_mode_strength_step.setter
    def fire_mode_strength_step(self, value: int) -> None:
        """设置开火模式强度步进"""
        self._fire_mode_strength_step = value
        logger.info(f"Fire mode strength step set to: {value}")
    
    @property
    def fire_mode_disabled(self) -> bool:
        """获取开火模式禁用状态"""
        return self._fire_mode_disabled
    
    @fire_mode_disabled.setter
    def fire_mode_disabled(self, value: bool) -> None:
        """设置开火模式禁用状态"""
        self._fire_mode_disabled = value
        logger.info(f"Fire mode disabled set to: {value}")
    
    @property
    def enable_panel_control(self) -> bool:
        """获取面板控制启用状态"""
        return self._enable_panel_control
    
    @enable_panel_control.setter
    def enable_panel_control(self, value: bool) -> None:
        """设置面板控制启用状态"""
        self._enable_panel_control = value
        logger.info(f"Panel control enabled set to: {value}")

    # 通道相关方法
    def get_current_channel(self) -> Channel:
        """获取当前选中的通道"""
        return self._current_select_channel

    async def set_channel(self, value: Union[int, float]) -> Optional[Channel]:
        """选定当前调节对应的通道"""
        if value >= 0:
            self._current_select_channel = Channel.A if value <= 1 else Channel.B
            logger.info(f"set activate channel to: {self._current_select_channel}")
            # 更新 UI 显示
            if self._ui_interface:
                channel_name = self._get_channel_name(self._current_select_channel)
                self._ui_interface.update_current_channel_display(channel_name)
            return self._current_select_channel
        return None

    def _get_pulse_task(self, channel: Channel) -> ChannelPulseTask:
        """根据通道获取脉冲任务"""
        return self._channel_pulse_tasks[channel]

    # 强度相关方法
    def update_strength_data(self, strength_data: StrengthData) -> None:
        """更新强度数据"""
        self._last_strength = strength_data
        self._data_updated_event.set()

    def get_last_strength(self) -> Optional[StrengthData]:
        """获取最后一次的强度数据"""
        return self._last_strength

    def set_dynamic_bone_mode(self, channel: Channel, enabled: bool) -> None:
        """设置动骨模式"""
        self._dynamic_bone_modes[channel] = enabled

    def is_dynamic_bone_enabled(self, channel: Channel) -> bool:
        """检查动骨模式是否启用"""
        return self._dynamic_bone_modes[channel]

    async def set_float_output(self, value: float, channel: Channel) -> None:
        """动骨与碰撞体激活对应通道输出"""
        if not self._enable_panel_control:
            return

        if value >= 0.0 and self._last_strength and self._dynamic_bone_modes[channel]:
            # 根据通道获取对应的强度限制
            limit = self._last_strength.a_limit if channel == Channel.A else self._last_strength.b_limit
            final_output = math.ceil(self._map_value(value, limit * 0.2, limit))
            await self._client.set_strength(channel, StrengthOperationType.SET_TO, final_output)

    async def adjust_strength(self, operation_type: StrengthOperationType, value: int, channel: Channel) -> None:
        """调整强度
        
        Args:
            operation_type: 操作类型 (SET_TO, INCREASE, DECREASE)
            value: 操作值
            channel: 目标通道
        """
        await self._client.set_strength(channel, operation_type, value)

    async def reset_strength(self, value: bool, channel: Channel) -> None:
        """强度重置为 0"""
        if value:
            await self.adjust_strength(StrengthOperationType.SET_TO, 0, channel)

    async def increase_strength(self, value: bool, channel: Channel) -> None:
        """增大强度, 固定 1"""
        if value:
            await self.adjust_strength(StrengthOperationType.INCREASE, 1, channel)

    async def decrease_strength(self, value: bool, channel: Channel) -> None:
        """减小强度, 固定 1"""
        if value:
            await self.adjust_strength(StrengthOperationType.DECREASE, 1, channel)

    # 波形相关方法
    def get_pulse_mode(self, channel: Channel) -> int:
        """获取指定通道的波形模式"""
        return self._pulse_modes[channel]
    
    def set_pulse_mode(self, channel: Channel, value: int) -> None:
        """设置指定通道的波形模式"""
        self._pulse_modes[channel] = value
        channel_name = self._get_channel_name(channel)
        logger.info(f"Pulse mode {channel_name} set to: {value}")

    async def update_pulse_data(self) -> None:
        """更新波形数据"""
        pulse_a = self._ui_interface.pulse_registry.pulses[self._pulse_modes[Channel.A]]
        pulse_b = self._ui_interface.pulse_registry.pulses[self._pulse_modes[Channel.B]]
        logger.info(f"更新波形 A {pulse_a.name} B {pulse_b.name}")
        self._channel_pulse_tasks[Channel.A].set_pulse(pulse_a)
        self._channel_pulse_tasks[Channel.B].set_pulse(pulse_b)

    def _update_pulse_mode(self, channel: Channel, pulse_index: int) -> None:
        """更新通道的波形模式索引"""
        self._pulse_modes[channel] = pulse_index
    
    def _update_pulse_ui(self, channel: Channel, pulse_index: int) -> None:
        """更新波形模式的UI显示"""
        pulse_name = self._ui_interface.pulse_registry.pulses[pulse_index].name
        self._ui_interface.set_pulse_mode(channel, pulse_name, silent=True)

    async def set_pulse_data(self, _: bool, channel: Channel, pulse_index: int, update_ui: bool = True) -> None:
        """立即切换为当前指定波形，清空原有波形"""
        self._update_pulse_mode(channel, pulse_index)
        if update_ui:
            self._update_pulse_ui(channel, pulse_index)
        await self.update_pulse_data()

    def get_current_pulse_name(self, channel: Channel) -> str:
        """获取当前通道的波形名称"""
        pulse_index = self.get_pulse_mode(channel)
        return self._ui_interface.pulse_registry.pulses[pulse_index].name

    async def set_test_pulse(self, channel: Channel, pulse: Pulse) -> None:
        """设置测试波形到指定通道"""
        pulse_task = self._get_pulse_task(channel)
        pulse_task.set_pulse(pulse)
        logger.info(f"设置测试波形到通道 {channel}: {pulse.name}")

    # 开火模式相关方法
    async def set_strength_step(self, value: float) -> None:
        """开火模式步进值设定"""
        self._fire_mode_strength_step = math.floor(self._map_value(value, 0, 100))
        logger.info(f"current strength step: {self._fire_mode_strength_step}")
        # 更新 UI 组件
        self._ui_interface.set_strength_step(self._fire_mode_strength_step, silent=True)

    async def strength_fire_mode(self, value: bool, channel: Channel, fire_strength: int, last_strength: Optional[StrengthData]) -> None:
        """一键开火模式"""
        if self._fire_mode_disabled:
            return

        logger.info(f"Trigger FireMode: {value}")
        await asyncio.sleep(0.01)

        # 防止重复触发
        if value and self._fire_mode_active:
            logger.debug("已有开火操作在进行中，跳过本次开始请求")
            return
        if not value and not self._fire_mode_active:
            logger.debug("没有进行中的开火操作，跳过本次结束请求")
            return

        async with self._fire_mode_lock:
            if value:
                # 开始 fire mode
                self._fire_mode_active = True
                logger.debug(f"FIRE START {last_strength}")
                if last_strength:
                    # 获取当前通道的强度和限制
                    current_strength = last_strength.a if channel == Channel.A else last_strength.b
                    strength_limit = last_strength.a_limit if channel == Channel.A else last_strength.b_limit
                    
                    self._fire_mode_origin_strengths[channel] = current_strength
                    await self._client.set_strength(
                        channel,
                        StrengthOperationType.SET_TO,
                        min(self._fire_mode_origin_strengths[channel] + fire_strength, strength_limit)
                    )
                self._data_updated_event.clear()
                await self._data_updated_event.wait()
            else:
                await self._client.set_strength(channel, StrengthOperationType.SET_TO, self._fire_mode_origin_strengths[channel])
                # 等待数据更新
                self._data_updated_event.clear()
                await self._data_updated_event.wait()
                # 结束 fire mode
                logger.debug(f"FIRE END {last_strength}")
                self._fire_mode_active = False

    # 模式切换相关方法
    def _toggle_channel_mode(self, channel: Channel) -> bool:
        """切换指定通道的动骨模式
        
        Returns:
            bool: 切换后的新模式状态
        """
        new_mode = not self._dynamic_bone_modes[channel]
        self.set_dynamic_bone_mode(channel, new_mode)
        return new_mode
    
    def _update_mode_ui(self, channel: Channel, new_mode: bool) -> None:
        """更新模式切换的UI显示"""
        mode_name = "可交互模式" if new_mode else "面板设置模式"
        channel_name = self._get_channel_name(channel)
        logger.info(f"通道 {channel_name} 切换为{mode_name}")
        
        # 更新UI
        ui_feature = self._get_dynamic_bone_ui_feature(channel)
        self._ui_interface.set_feature_state(ui_feature, new_mode, silent=True)

    async def _set_mode_timer_handle(self, channel: Channel) -> None:
        """模式切换计时器处理"""
        await asyncio.sleep(1)
        new_mode = self._toggle_channel_mode(channel)
        self._update_mode_ui(channel, new_mode)

    async def set_mode(self, value: int, channel: Channel) -> None:
        """切换工作模式, 延时一秒触发，更改按下时对应的通道"""
        if value == 1:  # 按下按键
            if self._set_mode_timer is not None:
                self._set_mode_timer.cancel()
            self._set_mode_timer = asyncio.create_task(self._set_mode_timer_handle(channel))
        elif value == 0:  # 松开按键
            if self._set_mode_timer:
                self._set_mode_timer.cancel()
                self._set_mode_timer = None

    # 面板控制相关方法
    async def set_panel_control(self, value: float) -> None:
        """面板控制功能开关"""
        if value > 0:
            self._enable_panel_control = True
        else:
            self._enable_panel_control = False
        mode_name = "开启面板控制" if self._enable_panel_control else "已禁用面板控制"
        logger.info(f": {mode_name}")
        # 更新 UI 组件
        self._ui_interface.set_feature_state(UIFeature.PANEL_CONTROL, self._enable_panel_control, silent=True)

    # 工具方法
    def _get_channel_name(self, channel: Channel) -> str:
        """获取通道名称"""
        return "A" if channel == Channel.A else "B"
    
    def _get_dynamic_bone_ui_feature(self, channel: Channel) -> UIFeature:
        """获取动骨模式对应的UI特性"""
        return UIFeature.DYNAMIC_BONE_A if channel == Channel.A else UIFeature.DYNAMIC_BONE_B
    
    def _map_value(self, value: float, min_value: float, max_value: float) -> float:
        """将值映射到指定范围"""
        return min_value + value * (max_value - min_value)