"""
OSC动作服务

统一管理所有OSC动作的业务逻辑实现，包含从DGLabWebSocketService迁移的共通业务逻辑。
支持多种设备连接方式（WebSocket、蓝牙等）的统一业务逻辑处理。
"""

import asyncio
import logging
import math
from typing import Optional, Dict, Union

from core.core_interface import CoreInterface
from core.dglab_pulse import Pulse
from models import Channel, StrengthData, StrengthOperationType, UIFeature
from services.dglab_service_interface import IDGLabDeviceService

logger = logging.getLogger(__name__)


class OSCActionService:
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
        
        # 服务状态
        self._is_running: bool = False

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

    # ============ 通道控制业务逻辑 ============

    def get_current_channel(self) -> Channel:
        """获取当前选中的通道"""
        return self._current_channel

    async def set_current_channel(self, value: Union[int, float]) -> Optional[Channel]:
        """设置当前活动通道"""
        if value >= 0:
            self._current_channel = Channel.A if value <= 1 else Channel.B
            logger.info(f"设置活动通道为: {self._current_channel}")
            self._core_interface.update_current_channel(self._current_channel)
            return self._current_channel
        return None

    # ============ 强度控制业务逻辑 ============

    async def set_float_output(self, value: float, channel: Channel) -> None:
        """设置浮点输出强度（自动处理动骨模式映射）"""
        if not self._enable_panel_control:
            return

        last_strength = self._dglab_device_service.get_last_strength()
        if value >= 0.0 and last_strength:
            if channel == Channel.A and self._dynamic_bone_modes[Channel.A]:
                final_output_a = math.ceil(
                    self._map_value(value, last_strength.a_limit * 0.2, last_strength.a_limit))
                await self._dglab_device_service.set_float_output(final_output_a, channel)
            elif channel == Channel.B and self._dynamic_bone_modes[Channel.B]:
                final_output_b = math.ceil(
                    self._map_value(value, last_strength.b_limit * 0.2, last_strength.b_limit))
                await self._dglab_device_service.set_float_output(final_output_b, channel)
            else:
                # 非动骨模式，直接设置
                await self._dglab_device_service.set_float_output(value, channel)

    async def adjust_strength(self, operation_type: StrengthOperationType, value: int, channel: Channel) -> None:
        """调整通道强度（委托给设备服务）"""
        await self._dglab_device_service.adjust_strength(operation_type, value, channel)

    async def reset_strength(self, value: bool, channel: Channel) -> None:
        """重置通道强度为0（委托给设备服务）"""
        await self._dglab_device_service.reset_strength(value, channel)

    async def increase_strength(self, value: bool, channel: Channel) -> None:
        """增加通道强度（委托给设备服务）"""
        await self._dglab_device_service.increase_strength(value, channel)

    async def decrease_strength(self, value: bool, channel: Channel) -> None:
        """减少通道强度（委托给设备服务）"""
        await self._dglab_device_service.decrease_strength(value, channel)

    # ============ 波形控制业务逻辑 ============

    def get_current_pulse(self, channel: Channel) -> Optional[Pulse]:
        """获取指定通道的波形模式索引"""
        return self._current_pulse.get(channel)

    def set_current_pulse(self, channel: Channel, pulse: Pulse) -> None:
        """设置指定通道的波形模式"""
        self._current_pulse[channel] = pulse
        self._core_interface.set_current_pulse(channel, pulse.name)

    async def update_pulse(self) -> None:
        """将当前A、B通道的波形数据同步到设备"""
        pulse_a = self._current_pulse.get(Channel.A)
        pulse_b = self._current_pulse.get(Channel.B)
        if pulse_a:
            await self.send_pulse(Channel.A, pulse_a)
        if pulse_b:
            await self.send_pulse(Channel.B, pulse_b)

    async def set_pulse(self, channel: Channel, pulse: Pulse) -> None:
        """设置指定通道的波形"""
        self.set_current_pulse(channel, pulse)
        await self.send_pulse(channel, pulse)

    async def send_pulse(self, channel: Channel, pulse: Pulse) -> None:
        """在指定通道播放波形"""
        await self._dglab_device_service.set_pulse_data(channel, pulse)

    # ============ 模式控制业务逻辑 ============

    def is_dynamic_bone_enabled(self, channel: Channel) -> bool:
        """检查指定通道的动骨模式是否启用"""
        return self._dynamic_bone_modes[channel]

    def set_dynamic_bone_mode(self, channel: Channel, enabled: bool) -> None:
        """设置指定通道的动骨模式"""
        self._dynamic_bone_modes[channel] = enabled

    async def set_mode(self, value: int, channel: Channel) -> None:
        """切换工作模式（延时触发动骨模式切换）"""
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
        logger.info(f"面板控制状态: {mode_name}")
        # 更新 UI 组件
        self._core_interface.set_feature_state(UIFeature.PANEL_CONTROL, self._enable_panel_control, silent=True)

    # ============ 开火模式业务逻辑 ============

    async def set_strength_step(self, value: float) -> None:
        """设置开火模式步进值"""
        self._fire_mode_strength_step = math.floor(self._map_value(value, 0, 100))
        logger.info(f"当前强度步进值: {self._fire_mode_strength_step}")
        # 更新 UI 组件
        self._core_interface.set_strength_step(self._fire_mode_strength_step, silent=True)

    async def strength_fire_mode(self, value: bool, channel: Channel) -> None:
        """一键开火模式（完整业务逻辑实现）"""
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
                    if channel == Channel.A:
                        self._fire_mode_origin_strengths[Channel.A] = last_strength.a
                        target_strength = min(
                            self._fire_mode_origin_strengths[Channel.A] + fire_strength, 
                            last_strength.a_limit
                        )
                        await self._dglab_device_service.adjust_strength(StrengthOperationType.SET_TO, target_strength, channel)
                    elif channel == Channel.B:
                        self._fire_mode_origin_strengths[Channel.B] = last_strength.b
                        target_strength = min(
                            self._fire_mode_origin_strengths[Channel.B] + fire_strength, 
                            last_strength.b_limit
                        )
                        await self._dglab_device_service.adjust_strength(StrengthOperationType.SET_TO, target_strength, channel)
                self._data_updated_event.clear()
                await self._data_updated_event.wait()
            else:
                # 恢复原始强度
                if channel == Channel.A:
                    await self._dglab_device_service.adjust_strength(
                        StrengthOperationType.SET_TO, 
                        self._fire_mode_origin_strengths[Channel.A], 
                        channel
                    )
                elif channel == Channel.B:
                    await self._dglab_device_service.adjust_strength(
                        StrengthOperationType.SET_TO, 
                        self._fire_mode_origin_strengths[Channel.B], 
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
        
        try:
            # 初始化服务状态
            self._is_running = True
            logger.info("OSC动作服务已启动")
            return True
        except Exception as e:
            logger.error(f"OSC动作服务启动失败: {e}")
            return False
    
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
        if self._set_mode_timer:
            self._set_mode_timer.cancel()
            self._set_mode_timer = None
        
        logger.debug("OSC动作服务资源已清理")

    # ============ 私有辅助方法 ============

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
            self._core_interface.set_feature_state(ui_feature, new_mode, silent=True)
        except asyncio.CancelledError:
            logger.debug(f"通道 {self._get_channel_name(channel)} 模式切换计时器已取消")
            raise

    def _get_channel_name(self, channel: Channel) -> str:
        """获取通道名称"""
        return "A" if channel == Channel.A else "B"

    def _get_dynamic_bone_ui_feature(self, channel: Channel) -> UIFeature:
        """获取动骨模式对应的UI特性"""
        return UIFeature.DYNAMIC_BONE_A if channel == Channel.A else UIFeature.DYNAMIC_BONE_B

    def _map_value(self, value: float, min_value: float, max_value: float) -> float:
        """将值映射到指定范围"""
        return min_value + value * (max_value - min_value)