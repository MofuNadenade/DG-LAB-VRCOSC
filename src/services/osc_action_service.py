"""
OSC动作服务

统一管理所有OSC动作的业务逻辑实现，包含从DGLabWebSocketService迁移的共通业务逻辑。
支持多种设备连接方式（WebSocket、蓝牙等）的统一业务逻辑处理。
"""

import asyncio
import logging
import math
from typing import Optional, Dict

from core.core_interface import CoreInterface
from core.dglab_pulse import Pulse
from models import Channel, PlaybackMode, StrengthData, StrengthOperationType, UIFeature
from services.dglab_service_interface import IDGLabDeviceService
from services.service_interface import IService

logger = logging.getLogger(__name__)


class OSCActionService(IService):
    """OSC动作服务 - 统一实现所有OSC动作的业务逻辑
    
    职责：
    1. 实现所有OSC动作的业务逻辑（从DGLabWebSocketService迁移）
    2. 管理业务状态（动骨模式、开火模式、通道状态、波形状态等）
    3. 通过IDGLabService抽象访问设备，支持多种连接方式
    4. 提供智能化的业务方法（如自动处理动骨模式映射）
    """

    def __init__(self, dglab_device_service: IDGLabDeviceService, core_interface: CoreInterface) -> None:
        """
        初始化OSC动作服务
        
        Args:
            dglab_device_service: 设备服务抽象接口
            core_interface: 核心接口
        """
        super().__init__()
        
        self._dglab_device_service = dglab_device_service
        self._core_interface = core_interface
        
        # 通道管理
        self._current_channel: Channel = Channel.A

        # 波形管理
        self._current_pulse: Dict[Channel, Pulse] = {}
        
        # 动骨模式管理
        self._dynamic_bone_modes: Dict[Channel, bool] = {Channel.A: False, Channel.B: False}
        
        # 动骨模式范围配置
        self._dynamic_bone_min_values: Dict[Channel, int] = {Channel.A: 0, Channel.B: 0}
        self._dynamic_bone_max_values: Dict[Channel, int] = {Channel.A: 100, Channel.B: 100}
        
        # 开火模式管理
        self._fire_mode_disabled: bool = False
        self._fire_mode_strength_step: int = 30
        self._fire_mode_active: bool = False
        self._fire_mode_lock: asyncio.Lock = asyncio.Lock()
        self._data_updated_event: asyncio.Event = asyncio.Event()
        self._fire_mode_origin_strengths: Dict[Channel, int] = {Channel.A: 0, Channel.B: 0}
        
        # 模式切换管理
        self._set_dynamic_bone_mode_timer: Optional[asyncio.Task[None]] = None
        
        # 面板控制
        self._enable_panel_control: bool = True
        self._disable_panel_pulse_setting: bool = False
        
        # 服务状态
        self._is_running: bool = False
        
        # 强度缓存和防抖机制
        self._pending_strength_updates: Dict[Channel, int] = {}
        self._strength_update_task: Optional[asyncio.Task[None]] = None
        self._strength_debounce_interval: float = 0.1  # 防抖间隔，单位秒，默认100ms

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
    
    @property
    def disable_panel_pulse_setting(self) -> bool:
        """禁止面板设置波形"""
        return self._disable_panel_pulse_setting
    
    @disable_panel_pulse_setting.setter
    def disable_panel_pulse_setting(self, value: bool) -> None:
        self._disable_panel_pulse_setting = value
    
    @property
    def strength_debounce_interval(self) -> float:
        """强度防抖间隔（秒）"""
        return self._strength_debounce_interval
    
    @strength_debounce_interval.setter
    def strength_debounce_interval(self, value: float) -> None:
        """设置强度防抖间隔（秒）"""
        if value > 0:
            self._strength_debounce_interval = value

    # ============ 通道控制业务逻辑 ============

    def get_current_channel(self) -> Channel:
        """获取当前选中的通道"""
        return self._current_channel

    # ============ 强度控制业务逻辑 ============

    async def adjust_strength(self, operation_type: StrengthOperationType, value: int, channel: Channel) -> None:
        """调整通道强度（委托给设备服务）"""
        if not self._enable_panel_control:
            return

        await self._dglab_device_service.adjust_strength(operation_type, value, channel)

    # ============ 波形控制业务逻辑 ============

    def get_current_pulse(self, channel: Channel) -> Optional[Pulse]:
        """获取指定通道的波形"""
        return self._current_pulse.get(channel)

    def set_current_pulse(self, channel: Channel, pulse: Optional[Pulse]) -> None:
        """设置指定通道的波形"""
        if pulse:
            self._current_pulse[channel] = pulse
        elif channel in self._current_pulse:
            del self._current_pulse[channel]
        self._core_interface.set_current_pulse(channel, pulse)

    async def update_pulse(self) -> None:
        """更新波形"""
        pulse_a = self.get_current_pulse(Channel.A)
        pulse_b = self.get_current_pulse(Channel.B)
        if pulse_a:
            await self.send_pulse(Channel.A, pulse_a)
        if pulse_b:
            await self.send_pulse(Channel.B, pulse_b)

    async def set_pulse(self, channel: Channel, pulse: Optional[Pulse]) -> None:
        """设置指定通道的波形，并发送波形到设备"""
        if self._disable_panel_pulse_setting:
            logger.info(f"Panel pulse setting is disabled, ignoring pulse setting for channel {channel.name}")
            return
        
        self.set_current_pulse(channel, pulse)
        await self.send_pulse(channel, pulse)

    async def send_pulse(self, channel: Channel, pulse: Optional[Pulse]) -> None:
        """发送波形到设备"""
        self._dglab_device_service.set_playback_mode(PlaybackMode.LOOP)
        await self._dglab_device_service.set_pulse_data(channel, pulse)

    # ============ 模式控制业务逻辑 ============

    def is_dynamic_bone_enabled(self, channel: Channel) -> bool:
        """检查指定通道的动骨模式是否启用"""
        return self._dynamic_bone_modes[channel]

    def set_dynamic_bone_mode(self, channel: Channel, enabled: bool) -> None:
        """设置指定通道的动骨模式"""
        self._dynamic_bone_modes[channel] = enabled

    def get_dynamic_bone_min_value(self, channel: Channel) -> int:
        """获取指定通道动骨模式的最小值"""
        return self._dynamic_bone_min_values[channel]

    def set_dynamic_bone_min_value(self, channel: Channel, min_value: int) -> None:
        """设置指定通道动骨模式的最小值"""
        if min_value >= 0:
            self._dynamic_bone_min_values[channel] = min_value
            logger.info(f"通道 {self._get_channel_name(channel)} 动骨模式最小值设置为: {min_value}")

    def get_dynamic_bone_max_value(self, channel: Channel) -> int:
        """获取指定通道动骨模式的最大值"""
        return self._dynamic_bone_max_values[channel]

    def set_dynamic_bone_max_value(self, channel: Channel, max_value: int) -> None:
        """设置指定通道动骨模式的最大值"""
        if max_value > 0:
            self._dynamic_bone_max_values[channel] = max_value
            logger.info(f"通道 {self._get_channel_name(channel)} 动骨模式最大值设置为: {max_value}")

    # ============ OSC业务逻辑 ============

    async def osc_set_strength(self, value: float, channel: Channel) -> None:
        """设置浮点输出强度（自动处理动骨模式映射，带防抖机制）"""
        if not self._dynamic_bone_modes.get(channel):
            return

        last_strength = self.get_last_strength()
        if value >= 0.0 and last_strength:
            # 计算最终输出值
            min_val = self._dynamic_bone_min_values[channel]
            max_val = self._dynamic_bone_max_values[channel]
            limit = last_strength['strength_limit'][channel]
            final_output = min(self._map_unit_value(value, min_val, max_val), limit)

            # 缓存强度更新（转换为整数）
            self._pending_strength_updates[channel] = int(final_output)

    async def osc_reset_strength(self, value: bool, channel: Channel) -> None:
        """重置通道强度为0（委托给设备服务）"""
        if not self._enable_panel_control:
            return

        if value:
            await self._dglab_device_service.reset_strength(channel)

    async def osc_increase_strength(self, value: bool, channel: Channel) -> None:
        """增加通道强度（委托给设备服务）"""
        if not self._enable_panel_control:
            return

        if value:
            await self._dglab_device_service.increase_strength(channel)

    async def osc_decrease_strength(self, value: bool, channel: Channel) -> None:
        """减少通道强度（委托给设备服务）"""
        if not self._enable_panel_control:
            return

        if value:
            await self._dglab_device_service.decrease_strength(channel)

    async def osc_set_current_channel(self, value: int) -> Optional[Channel]:
        """设置当前活动通道"""
        if value >= 0:
            self._current_channel = Channel.A if value <= 1 else Channel.B
            logger.info(f"设置活动通道为: {self._current_channel}")
            self._core_interface.on_current_channel_updated(self._current_channel)
            return self._current_channel
        return None

    async def osc_set_pulse(self, channel: Channel, pulse: Optional[Pulse]) -> None:
        """OSC设置波形"""
        if not self._enable_panel_control:
            return

        await self.set_pulse(channel, pulse)

    async def osc_set_panel_control(self, value: bool) -> None:
        """设置面板控制功能开关"""
        self._enable_panel_control = value
        interaction_type = "开启面板控制" if self._enable_panel_control else "已禁用面板控制"
        logger.info(f"面板控制状态: {interaction_type}")
        # 更新 UI 组件
        self._core_interface.set_feature_state(UIFeature.PANEL_CONTROL, self._enable_panel_control)

    async def osc_set_dynamic_bone_mode(self, value: bool, channel: Channel) -> None:
        """切换工作模式（延时触发动骨模式切换）"""
        if not self._enable_panel_control:
            return

        if value:  # 按下按键
            if self._set_dynamic_bone_mode_timer is not None:
                self._set_dynamic_bone_mode_timer.cancel()
            self._set_dynamic_bone_mode_timer = asyncio.create_task(self._set_dynamic_bone_mode_timer_handle(channel))
        else:  # 松开按键
            if self._set_dynamic_bone_mode_timer:
                self._set_dynamic_bone_mode_timer.cancel()
                self._set_dynamic_bone_mode_timer = None

    async def osc_set_fire_mode_strength_step(self, value: float) -> None:
        """设置开火模式步进值"""
        self._fire_mode_strength_step = math.floor(self._map_unit_value(value, 0, 100))
        logger.info(f"当前强度步进值: {self._fire_mode_strength_step}")
        # 更新 UI 组件
        self._core_interface.set_fire_mode_strength_step(self._fire_mode_strength_step)

    async def osc_activate_fire_mode(self, value: bool, channel: Channel) -> None:
        """一键开火模式（完整业务逻辑实现）"""
        if not self._enable_panel_control:
            return

        fire_strength = self.fire_mode_strength_step
        last_strength = self.get_last_strength()

        if self._fire_mode_disabled:
            return

        logger.info(f"触发开火模式: {value}")

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
                logger.debug(f"开火模式开始 {last_strength}")
                if last_strength:
                    self._fire_mode_origin_strengths[channel] = last_strength['strength'][channel]
                    target_strength = min(
                        self._fire_mode_origin_strengths[channel] + fire_strength,
                        last_strength['strength_limit'][channel]
                    )
                    await self._dglab_device_service.adjust_strength(StrengthOperationType.SET_TO, target_strength, channel)
                self._data_updated_event.clear()
                await self._data_updated_event.wait()
            else:
                # 恢复原始强度
                # 简化：合并A/B通道处理逻辑
                await self._dglab_device_service.adjust_strength(
                    StrengthOperationType.SET_TO,
                    self._fire_mode_origin_strengths[channel],
                    channel
                )
                # 等待数据更新
                self._data_updated_event.clear()
                await self._data_updated_event.wait()
                # 结束 fire mode
                logger.debug(f"开火模式结束 {last_strength}")
                self._fire_mode_active = False

    # ============ 数据更新处理 ============

    def get_last_strength(self) -> Optional[StrengthData]:
        """获取最后的强度数据"""
        return self._dglab_device_service.get_last_strength()

    def update_strength_data(self, strength_data: StrengthData) -> None:
        """处理强度数据更新（用于开火模式同步）"""
        self._dglab_device_service.update_strength_data(strength_data)
        self._data_updated_event.set()

    # ============ 生命周期管理 ============
    
    async def start_service(self) -> bool:
        """启动OSC动作服务
        
        Returns:
            bool: 启动是否成功
        """
        if self._is_running:
            logger.warning("OSC动作服务已在运行")
            return True
        
        # 初始化服务状态
        self._is_running = True
        
        # 启动防抖强度更新任务
        self._strength_update_task = asyncio.create_task(self._debounced_strength_update())
        
        logger.info("OSC动作服务已启动")
        return True
    
    async def stop_service(self) -> None:
        """停止OSC动作服务"""
        if not self._is_running:
            return
        
        await self.cleanup()
        self._is_running = False
        logger.info("OSC动作服务已停止")
    
    def is_service_running(self) -> bool:
        """检查OSC动作服务运行状态"""
        return self._is_running

    async def cleanup(self) -> None:
        """清理资源"""
        # 取消模式切换定时器
        if self._set_dynamic_bone_mode_timer:
            self._set_dynamic_bone_mode_timer.cancel()
            self._set_dynamic_bone_mode_timer = None
        
        # 取消强度更新任务
        if self._strength_update_task and not self._strength_update_task.done():
            self._strength_update_task.cancel()
            self._strength_update_task = None
        
        logger.debug("OSC动作服务资源已清理")

    # ============ 私有辅助方法 ============

    async def _debounced_strength_update(self) -> None:
        """防抖强度更新后台任务（持续运行，可配置间隔）"""
        logger.debug(f"防抖强度更新任务已启动，间隔: {self._strength_debounce_interval}s")
        try:
            while self._is_running:
                # 等待配置的防抖间隔
                await asyncio.sleep(self._strength_debounce_interval)
                
                # 如果有待处理的更新，处理它们
                if self._pending_strength_updates:
                    pending_updates = self._pending_strength_updates.copy()
                    self._pending_strength_updates.clear()
                    
                    # 发送缓存的强度更新
                    for channel, strength_value in pending_updates.items():
                        await self._dglab_device_service.adjust_strength(StrengthOperationType.SET_TO, strength_value, channel)
                            
        except asyncio.CancelledError:
            logger.debug("防抖强度更新任务已取消")
            raise
        except Exception as e:
            logger.error(f"防抖强度更新任务异常: {e}")
        finally:
            logger.debug("防抖强度更新任务已结束")

    async def _set_dynamic_bone_mode_timer_handle(self, channel: Channel) -> None:
        """模式切换计时器处理"""
        try:
            await asyncio.sleep(1.0)

            new_mode = not self._dynamic_bone_modes[channel]
            self.set_dynamic_bone_mode(channel, new_mode)
            interaction_type = "可交互模式" if new_mode else "面板设置模式"
            logger.info(f"通道 {self._get_channel_name(channel)} 切换为{interaction_type}")
            # 更新UI
            ui_feature = self._get_dynamic_bone_ui_feature(channel)
            self._core_interface.set_feature_state(ui_feature, new_mode)
        except asyncio.CancelledError:
            logger.debug(f"通道 {self._get_channel_name(channel)} 模式切换计时器已取消")
            raise

    def _get_channel_name(self, channel: Channel) -> str:
        """获取通道名称"""
        return "A" if channel == Channel.A else "B"

    def _get_dynamic_bone_ui_feature(self, channel: Channel) -> UIFeature:
        """获取动骨模式对应的UI特性"""
        return UIFeature.DYNAMIC_BONE_A if channel == Channel.A else UIFeature.DYNAMIC_BONE_B

    def _map_unit_value(self, value: float, min_value: float, max_value: float) -> float:
        """将单位值映射到指定范围"""
        return min_value + max(0, min(1, value)) * (max_value - min_value)