import asyncio
import math
from typing import Optional, List, Union
from pydglab_ws import DGLabLocalClient, Channel, StrengthData, StrengthOperationType, PulseDataTooLong
from pydglab_ws.typing import PulseOperation
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
        self.task = asyncio.create_task(self.internal_task(data))

    async def internal_task(self, data: List[PulseOperation], send_duration: float = 5, send_interval: float = 1) -> None:
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
    
    def __init__(self, client: DGLabLocalClient, ui_callback: 'UIInterface') -> None:
        self.client: DGLabLocalClient = client
        self.ui_callback: 'UIInterface' = ui_callback
        
        # 通道管理
        self.current_select_channel: Channel = Channel.A
        self.channel_a_pulse_task: ChannelPulseTask = ChannelPulseTask(client, Channel.A)
        self.channel_b_pulse_task: ChannelPulseTask = ChannelPulseTask(client, Channel.B)
        
        # 强度管理
        self.last_strength: Optional[StrengthData] = None
        self.is_dynamic_bone_mode_a: bool = False
        self.is_dynamic_bone_mode_b: bool = False
        
        # 波形管理
        self.pulse_mode_a: int = 0
        self.pulse_mode_b: int = 0
        
        # 开火模式管理
        self.fire_mode_disabled: bool = False
        self.fire_mode_strength_step: int = 30
        self.fire_mode_active: bool = False
        self.fire_mode_lock: asyncio.Lock = asyncio.Lock()
        self.data_updated_event: asyncio.Event = asyncio.Event()
        self.fire_mode_origin_strength_a: int = 0
        self.fire_mode_origin_strength_b: int = 0
        
        # 模式切换管理
        self.set_mode_timer: Optional[asyncio.Task[None]] = None
        
        # 面板控制
        self.enable_panel_control: bool = True

    # 通道相关方法
    def get_current_channel(self) -> Channel:
        """获取当前选中的通道"""
        return self.current_select_channel

    async def set_channel(self, value: Union[int, float]) -> Optional[Channel]:
        """选定当前调节对应的通道"""
        if value >= 0:
            self.current_select_channel = Channel.A if value <= 1 else Channel.B
            logger.info(f"set activate channel to: {self.current_select_channel}")
            # 更新 UI 显示
            if self.ui_callback:
                channel_name = "A" if self.current_select_channel == Channel.A else "B"
                self.ui_callback.update_current_channel_display(channel_name)
            return self.current_select_channel
        return None

    def get_pulse_task(self, channel: Channel) -> ChannelPulseTask:
        """根据通道获取脉冲任务"""
        if channel == Channel.A:
            return self.channel_a_pulse_task
        else:
            return self.channel_b_pulse_task

    # 强度相关方法
    def update_strength_data(self, strength_data: StrengthData) -> None:
        """更新强度数据"""
        self.last_strength = strength_data
        self.data_updated_event.set()

    def get_last_strength(self) -> Optional[StrengthData]:
        """获取最后一次的强度数据"""
        return self.last_strength

    def set_dynamic_bone_mode(self, channel: Channel, enabled: bool) -> None:
        """设置动骨模式"""
        if channel == Channel.A:
            self.is_dynamic_bone_mode_a = enabled
        else:
            self.is_dynamic_bone_mode_b = enabled

    def is_dynamic_bone_enabled(self, channel: Channel) -> bool:
        """检查动骨模式是否启用"""
        if channel == Channel.A:
            return self.is_dynamic_bone_mode_a
        else:
            return self.is_dynamic_bone_mode_b

    async def set_float_output(self, value: float, channel: Channel) -> None:
        """动骨与碰撞体激活对应通道输出"""
        if not self.enable_panel_control:
            return

        if value >= 0.0 and self.last_strength:
            if channel == Channel.A and self.is_dynamic_bone_mode_a:
                final_output_a = math.ceil(self.map_value(value, self.last_strength.a_limit * 0.2, self.last_strength.a_limit))
                await self.client.set_strength(channel, StrengthOperationType.SET_TO, final_output_a)
            elif channel == Channel.B and self.is_dynamic_bone_mode_b:
                final_output_b = math.ceil(self.map_value(value, self.last_strength.b_limit * 0.2, self.last_strength.b_limit))
                await self.client.set_strength(channel, StrengthOperationType.SET_TO, final_output_b)

    async def reset_strength(self, value: bool, channel: Channel) -> None:
        """强度重置为 0"""
        if value:
            await self.client.set_strength(channel, StrengthOperationType.SET_TO, 0)

    async def increase_strength(self, value: bool, channel: Channel) -> None:
        """增大强度, 固定 1"""
        if value:
            await self.client.set_strength(channel, StrengthOperationType.INCREASE, 1)

    async def decrease_strength(self, value: bool, channel: Channel) -> None:
        """减小强度, 固定 1"""
        if value:
            await self.client.set_strength(channel, StrengthOperationType.DECREASE, 1)

    # 波形相关方法
    def get_pulse_mode(self, channel: Channel) -> int:
        """获取指定通道的波形模式"""
        if channel == Channel.A:
            return self.pulse_mode_a
        else:
            return self.pulse_mode_b

    async def update_pulse_data(self) -> None:
        """更新波形数据"""
        pulse_a = self.ui_callback.pulse_registry.pulses[self.pulse_mode_a]
        pulse_b = self.ui_callback.pulse_registry.pulses[self.pulse_mode_b]
        logger.info(f"更新波形 A {pulse_a.name} B {pulse_b.name}")
        self.channel_a_pulse_task.set_pulse(pulse_a)
        self.channel_b_pulse_task.set_pulse(pulse_b)

    async def set_pulse_data(self, _: bool, channel: Channel, pulse_index: int, update_ui: bool = True) -> None:
        """立即切换为当前指定波形，清空原有波形"""
        if channel == Channel.A:
            self.pulse_mode_a = pulse_index
            if update_ui:
                pulse_name = self.ui_callback.pulse_registry.pulses[pulse_index].name
                self.ui_callback.set_pulse_mode(Channel.A, pulse_name, silent=True)
        else:
            self.pulse_mode_b = pulse_index
            if update_ui:
                pulse_name = self.ui_callback.pulse_registry.pulses[pulse_index].name
                self.ui_callback.set_pulse_mode(Channel.B, pulse_name, silent=True)
        await self.update_pulse_data()

    def get_current_pulse_name(self, channel: Channel) -> str:
        """获取当前通道的波形名称"""
        pulse_index = self.get_pulse_mode(channel)
        return self.ui_callback.pulse_registry.pulses[pulse_index].name

    # 开火模式相关方法
    async def set_strength_step(self, value: float) -> None:
        """开火模式步进值设定"""
        self.fire_mode_strength_step = math.floor(self.map_value(value, 0, 100))
        logger.info(f"current strength step: {self.fire_mode_strength_step}")
        # 更新 UI 组件
        self.ui_callback.set_strength_step(self.fire_mode_strength_step, silent=True)

    async def strength_fire_mode(self, value: bool, channel: Channel, fire_strength: int, last_strength: Optional[StrengthData]) -> None:
        """一键开火模式"""
        if self.fire_mode_disabled:
            return

        logger.info(f"Trigger FireMode: {value}")
        await asyncio.sleep(0.01)

        # 防止重复触发
        if value and self.fire_mode_active:
            logger.debug("已有开火操作在进行中，跳过本次开始请求")
            return
        if not value and not self.fire_mode_active:
            logger.debug("没有进行中的开火操作，跳过本次结束请求")
            return

        async with self.fire_mode_lock:
            if value:
                # 开始 fire mode
                self.fire_mode_active = True
                logger.debug(f"FIRE START {last_strength}")
                if last_strength:
                    if channel == Channel.A:
                        self.fire_mode_origin_strength_a = last_strength.a
                        await self.client.set_strength(
                            channel,
                            StrengthOperationType.SET_TO,
                            min(self.fire_mode_origin_strength_a + fire_strength, last_strength.a_limit)
                        )
                    elif channel == Channel.B:
                        self.fire_mode_origin_strength_b = last_strength.b
                        await self.client.set_strength(
                            channel,
                            StrengthOperationType.SET_TO,
                            min(self.fire_mode_origin_strength_b + fire_strength, last_strength.b_limit)
                        )
                self.data_updated_event.clear()
                await self.data_updated_event.wait()
            else:
                if channel == Channel.A:
                    await self.client.set_strength(channel, StrengthOperationType.SET_TO, self.fire_mode_origin_strength_a)
                elif channel == Channel.B:
                    await self.client.set_strength(channel, StrengthOperationType.SET_TO, self.fire_mode_origin_strength_b)
                # 等待数据更新
                self.data_updated_event.clear()
                await self.data_updated_event.wait()
                # 结束 fire mode
                logger.debug(f"FIRE END {last_strength}")
                self.fire_mode_active = False

    # 模式切换相关方法
    async def set_mode_timer_handle(self, channel: Channel) -> None:
        """模式切换计时器处理"""
        await asyncio.sleep(1)

        if channel == Channel.A:
            new_mode = not self.is_dynamic_bone_mode_a
            self.set_dynamic_bone_mode(Channel.A, new_mode)
            mode_name = "可交互模式" if new_mode else "面板设置模式"
            logger.info("通道 A 切换为" + mode_name)
            # 更新UI
            self.ui_callback.set_feature_state(UIFeature.DYNAMIC_BONE_A, new_mode, silent=True)
        elif channel == Channel.B:
            new_mode = not self.is_dynamic_bone_mode_b
            self.set_dynamic_bone_mode(Channel.B, new_mode)
            mode_name = "可交互模式" if new_mode else "面板设置模式"
            logger.info("通道 B 切换为" + mode_name)
            # 更新UI
            self.ui_callback.set_feature_state(UIFeature.DYNAMIC_BONE_B, new_mode, silent=True)

    async def set_mode(self, value: int, channel: Channel) -> None:
        """切换工作模式, 延时一秒触发，更改按下时对应的通道"""
        if value == 1:  # 按下按键
            if self.set_mode_timer is not None:
                self.set_mode_timer.cancel()
            self.set_mode_timer = asyncio.create_task(self.set_mode_timer_handle(channel))
        elif value == 0:  # 松开按键
            if self.set_mode_timer:
                self.set_mode_timer.cancel()
                self.set_mode_timer = None

    # 面板控制相关方法
    async def set_panel_control(self, value: float) -> None:
        """面板控制功能开关"""
        if value > 0:
            self.enable_panel_control = True
        else:
            self.enable_panel_control = False
        mode_name = "开启面板控制" if self.enable_panel_control else "已禁用面板控制"
        logger.info(f": {mode_name}")
        # 更新 UI 组件
        self.ui_callback.set_feature_state(UIFeature.PANEL_CONTROL, self.enable_panel_control, silent=True)

    # 工具方法
    def map_value(self, value: float, min_value: float, max_value: float) -> float:
        """将值映射到指定范围"""
        return min_value + value * (max_value - min_value)