"""
DG-LAB WebSocket 设备服务实现

基于现有 DGLabService 的 WebSocket 连接实现。
"""

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
    """通道波形任务管理"""
    
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


class DGLabWebSocketService:
    """DG-LAB WebSocket 设备服务实现
    
    基于 WebSocket 连接的 DG-LAB 设备控制服务，包装现有的 WebSocket 功能。
    """
    
    def __init__(self, client: DGLabLocalClient, ui_interface: UIInterface) -> None:
        self._client: DGLabLocalClient = client
        self._ui_interface: UIInterface = ui_interface
        self._connected: bool = False
        
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

    # ============ 连接管理 ============
    
    async def connect(self) -> bool:
        """连接设备（WebSocket连接由外部管理）"""
        self._connected = True
        return True
    
    async def disconnect(self) -> None:
        """断开设备连接"""
        self._connected = False
        # 取消所有波形任务
        for task_manager in self._channel_pulse_tasks.values():
            if task_manager.task and not task_manager.task.done():
                task_manager.task.cancel()
        
        # 取消模式切换定时器
        if self._set_mode_timer:
            self._set_mode_timer.cancel()
            self._set_mode_timer = None
    
    def is_connected(self) -> bool:
        """检查设备连接状态"""
        return self._connected
    
    def get_connection_type(self) -> str:
        """获取连接类型标识"""
        return "websocket"

    # ============ 属性访问 ============
    
    @property
    def fire_mode_strength_step(self) -> int:
        """开火模式强度步进"""
        return self._fire_mode_strength_step

    @fire_mode_strength_step.setter
    def fire_mode_strength_step(self, value: int) -> None:
        self._fire_mode_strength_step = value

    @property
    def fire_mode_disabled(self) -> bool:
        """开火模式是否禁用"""
        return self._fire_mode_disabled

    @fire_mode_disabled.setter
    def fire_mode_disabled(self, value: bool) -> None:
        self._fire_mode_disabled = value

    @property
    def enable_panel_control(self) -> bool:
        """面板控制是否启用"""
        return self._enable_panel_control

    @enable_panel_control.setter
    def enable_panel_control(self, value: bool) -> None:
        self._enable_panel_control = value

    # ============ 状态查询 ============
    
    def get_current_channel(self) -> Channel:
        """获取当前选中的通道"""
        return self._current_select_channel
    
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
        """获取指定通道当前波形的名称"""
        pulse_index = self.get_pulse_mode(channel)
        return self._ui_interface.pulse_registry.pulses[pulse_index].name

    # ============ 通道控制 ============
    
    async def set_channel(self, value: Union[int, float]) -> Optional[Channel]:
        """设置当前活动通道"""
        if value >= 0:
            self._current_select_channel = Channel.A if value <= 1 else Channel.B
            logger.info(f"set activate channel to: {self._current_select_channel}")
            # 更新 UI 显示
            if self._ui_interface:
                channel_name = "A" if self._current_select_channel == Channel.A else "B"
                self._ui_interface.update_current_channel_display(channel_name)
            return self._current_select_channel
        return None

    # ============ 强度控制 ============
    
    async def set_float_output(self, value: float, channel: Channel) -> None:
        """设置浮点输出强度（用于动骨模式）"""
        if not self._enable_panel_control:
            return

        if value >= 0.0 and self._last_strength:
            if channel == Channel.A and self._dynamic_bone_modes[Channel.A]:
                final_output_a = math.ceil(self._map_value(value, self._last_strength.a_limit * 0.2, self._last_strength.a_limit))
                await self._client.set_strength(channel, StrengthOperationType.SET_TO, final_output_a)
            elif channel == Channel.B and self._dynamic_bone_modes[Channel.B]:
                final_output_b = math.ceil(self._map_value(value, self._last_strength.b_limit * 0.2, self._last_strength.b_limit))
                await self._client.set_strength(channel, StrengthOperationType.SET_TO, final_output_b)
    
    async def adjust_strength(self, operation_type: StrengthOperationType, value: int, channel: Channel) -> None:
        """调整通道强度"""
        await self._client.set_strength(channel, operation_type, value)
    
    async def reset_strength(self, value: bool, channel: Channel) -> None:
        """重置通道强度为0"""
        if value:
            await self._client.set_strength(channel, StrengthOperationType.SET_TO, 0)
    
    async def increase_strength(self, value: bool, channel: Channel) -> None:
        """增加通道强度"""
        if value:
            await self._client.set_strength(channel, StrengthOperationType.INCREASE, 1)
    
    async def decrease_strength(self, value: bool, channel: Channel) -> None:
        """减少通道强度"""
        if value:
            await self._client.set_strength(channel, StrengthOperationType.DECREASE, 1)

    # ============ 波形控制 ============
    
    async def update_pulse_data(self) -> None:
        """更新设备上的波形数据"""
        pulse_a = self._ui_interface.pulse_registry.pulses[self._pulse_modes[Channel.A]]
        pulse_b = self._ui_interface.pulse_registry.pulses[self._pulse_modes[Channel.B]]
        logger.info(f"更新波形 A {pulse_a.name} B {pulse_b.name}")
        self._channel_pulse_tasks[Channel.A].set_pulse(pulse_a)
        self._channel_pulse_tasks[Channel.B].set_pulse(pulse_b)
    
    async def set_pulse_data(self, _: bool, channel: Channel, pulse_index: int, update_ui: bool = True) -> None:
        """设置指定通道的波形数据"""
        self._update_pulse_mode(channel, pulse_index)
        if update_ui:
            self._update_pulse_ui(channel, pulse_index)
        await self.update_pulse_data()
    
    async def set_test_pulse(self, channel: Channel, pulse: Pulse) -> None:
        """在指定通道播放测试波形"""
        self._channel_pulse_tasks[channel].set_pulse(pulse)
    
    def set_pulse_mode(self, channel: Channel, value: int) -> None:
        """设置指定通道的波形模式"""
        self._update_pulse_mode(channel, value)
        self._update_pulse_ui(channel, value)

    # ============ 模式控制 ============
    
    def set_dynamic_bone_mode(self, channel: Channel, enabled: bool) -> None:
        """设置指定通道的动骨模式"""
        self._dynamic_bone_modes[channel] = enabled
    
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
        """设置面板控制功能开关"""
        self._enable_panel_control = value > 0
        mode_name = "开启面板控制" if self._enable_panel_control else "已禁用面板控制"
        logger.info(f": {mode_name}")
        # 更新 UI 组件
        self._ui_interface.set_feature_state(UIFeature.PANEL_CONTROL, self._enable_panel_control, silent=True)
    
    async def set_strength_step(self, value: float) -> None:
        """设置开火模式步进值"""
        self._fire_mode_strength_step = math.floor(self._map_value(value, 0, 100))
        logger.info(f"current strength step: {self._fire_mode_strength_step}")
        # 更新 UI 组件
        self._ui_interface.set_strength_step(self._fire_mode_strength_step, silent=True)

    # ============ 开火模式 ============
    
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
                    if channel == Channel.A:
                        self._fire_mode_origin_strengths[Channel.A] = last_strength.a
                        await self._client.set_strength(
                            channel,
                            StrengthOperationType.SET_TO,
                            min(self._fire_mode_origin_strengths[Channel.A] + fire_strength, last_strength.a_limit)
                        )
                    elif channel == Channel.B:
                        self._fire_mode_origin_strengths[Channel.B] = last_strength.b
                        await self._client.set_strength(
                            channel,
                            StrengthOperationType.SET_TO,
                            min(self._fire_mode_origin_strengths[Channel.B] + fire_strength, last_strength.b_limit)
                        )
                self._data_updated_event.clear()
                await self._data_updated_event.wait()
            else:
                if channel == Channel.A:
                    await self._client.set_strength(channel, StrengthOperationType.SET_TO, self._fire_mode_origin_strengths[Channel.A])
                elif channel == Channel.B:
                    await self._client.set_strength(channel, StrengthOperationType.SET_TO, self._fire_mode_origin_strengths[Channel.B])
                # 等待数据更新
                self._data_updated_event.clear()
                await self._data_updated_event.wait()
                # 结束 fire mode
                logger.debug(f"FIRE END {last_strength}")
                self._fire_mode_active = False

    # ============ 数据更新 ============
    
    def update_strength_data(self, strength_data: StrengthData) -> None:
        """更新强度数据（通常由连接层调用）"""
        self._last_strength = strength_data
        self._data_updated_event.set()

    # ============ 私有辅助方法 ============
    
    def _update_pulse_mode(self, channel: Channel, pulse_index: int) -> None:
        """更新波形模式索引"""
        self._pulse_modes[channel] = pulse_index
    
    def _update_pulse_ui(self, channel: Channel, pulse_index: int) -> None:
        """更新波形UI显示"""
        pulse_name = self._ui_interface.pulse_registry.pulses[pulse_index].name
        self._ui_interface.set_pulse_mode(channel, pulse_name, silent=True)
    
    async def _set_mode_timer_handle(self, channel: Channel) -> None:
        """模式切换计时器处理"""
        await asyncio.sleep(1)

        new_mode = not self._dynamic_bone_modes[channel]
        self.set_dynamic_bone_mode(channel, new_mode)
        mode_name = "可交互模式" if new_mode else "面板设置模式"
        logger.info(f"通道 {self._get_channel_name(channel)} 切换为{mode_name}")
        # 更新UI
        ui_feature = self._get_dynamic_bone_ui_feature(channel)
        self._ui_interface.set_feature_state(ui_feature, new_mode, silent=True)
    
    def _get_channel_name(self, channel: Channel) -> str:
        """获取通道名称"""
        return "A" if channel == Channel.A else "B"
    
    def _get_dynamic_bone_ui_feature(self, channel: Channel) -> UIFeature:
        """获取动骨模式对应的UI特性"""
        return UIFeature.DYNAMIC_BONE_A if channel == Channel.A else UIFeature.DYNAMIC_BONE_B
    
    def _map_value(self, value: float, min_value: float, max_value: float) -> float:
        """将值映射到指定范围"""
        return min_value + value * (max_value - min_value)
