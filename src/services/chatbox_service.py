import asyncio
import logging
from typing import Optional

from core.core_interface import CoreInterface
from models import Channel, UIFeature
from .osc_action_service import OSCActionService
from .osc_service import OSCService

logger = logging.getLogger(__name__)


class ChatboxService:
    def __init__(self, core_interface: CoreInterface, osc_service: OSCService, osc_action_service: OSCActionService) -> None:
        super().__init__()
        self._core_interface = core_interface
        self._osc_service = osc_service
        self._osc_action_service = osc_action_service
        self._enable_chatbox_status: bool = True
        self._previous_chatbox_status: bool = True
        self._chatbox_toggle_timer: Optional[asyncio.Task[None]] = None
        self._send_status_task: Optional[asyncio.Task[None]] = None

    @property
    def is_enabled(self) -> bool:
        """获取ChatBox状态是否启用"""
        return self._enable_chatbox_status

    def set_enabled(self, enabled: bool) -> None:
        """设置ChatBox状态启用/禁用"""
        if self._enable_chatbox_status != enabled:
            self._enable_chatbox_status = enabled
            chatbox_status = "开启" if enabled else "关闭"
            logger.info(f"ChatBox显示状态设置为: {chatbox_status}")
            # 更新UI
            self._core_interface.set_feature_state(UIFeature.CHATBOX_STATUS, enabled)
            # 如果禁用，立即清空chatbox
            if not enabled:
                self._osc_service.send_message_to_vrchat_chatbox("")

    async def start_service(self) -> bool:
        """启动状态更新任务"""
        try:
            if self._send_status_task is None or self._send_status_task.done():
                self._send_status_task = asyncio.create_task(self._periodic_status_update())
            logger.info("ChatBox服务已启动")
            return True
        except Exception as e:
            logger.error(f"ChatBox服务启动失败: {e}")
            return False

    async def stop_service(self) -> None:
        """停止状态更新任务"""
        if self._send_status_task and not self._send_status_task.done():
            self._send_status_task.cancel()
            try:
                await self._send_status_task
            except asyncio.CancelledError:
                pass
            self._send_status_task = None
        logger.info("ChatBox服务已停止")

    def is_service_running(self) -> bool:
        """检查服务是否正在运行"""
        return (
            self._send_status_task is not None and 
            not self._send_status_task.done()
        )

    async def _periodic_status_update(self) -> None:
        """
        周期性通过 ChatBox 发送当前的配置状态
        """
        while True:
            try:
                if self._enable_chatbox_status:
                    await self.send_strength_status()
                    self._previous_chatbox_status = True
                elif self._previous_chatbox_status:  # clear chatbox
                    self._osc_service.send_message_to_vrchat_chatbox("")
                    self._previous_chatbox_status = False
            except Exception as e:
                logger.error(f"periodic_status_update 任务中发生错误: {e}")
                await asyncio.sleep(5)
            await asyncio.sleep(3)

    async def _chatbox_toggle_timer_handle(self) -> None:
        """1秒计时器 计时结束后切换 Chatbox 状态"""
        await asyncio.sleep(1)

        # 使用API方法切换状态
        self.set_enabled(not self._enable_chatbox_status)
        self._chatbox_toggle_timer = None

    async def toggle_chatbox(self, value: int) -> None:
        """开关 ChatBox 内容发送"""
        if value == 1:  # 按下按键
            if self._chatbox_toggle_timer is not None:
                self._chatbox_toggle_timer.cancel()
            self._chatbox_toggle_timer = asyncio.create_task(self._chatbox_toggle_timer_handle())
        elif value == 0:  # 松开按键
            if self._chatbox_toggle_timer:
                self._chatbox_toggle_timer.cancel()
                self._chatbox_toggle_timer = None

    async def send_strength_status(self) -> None:
        """通过 ChatBox 发送当前强度数值"""
        last_strength = self._osc_action_service.get_last_strength()
        if last_strength:
            interaction_type_a = "交互" if self._osc_action_service.is_dynamic_bone_enabled(Channel.A) else "面板"
            interaction_type_b = "交互" if self._osc_action_service.is_dynamic_bone_enabled(Channel.B) else "面板"
            current_channel = self._osc_action_service.get_current_channel()
            channel_strength = f"[A]: {last_strength.a} B: {last_strength.b}" if current_channel == Channel.A else f"A: {last_strength.a} [B]: {last_strength.b}"
            pulse_a = self._osc_action_service.get_current_pulse(Channel.A)
            pulse_b = self._osc_action_service.get_current_pulse(Channel.B)
            pulse_name_a = pulse_a.name if pulse_a else "未知波形"
            pulse_name_b = pulse_b.name if pulse_b else "未知波形"

            self._osc_service.send_message_to_vrchat_chatbox(
                f"MAX A: {last_strength.a_limit} B: {last_strength.b_limit}\n" +
                f"Mode A: {interaction_type_a} B: {interaction_type_b} \n" +
                f"Pulse A: {pulse_name_a} B: {pulse_name_b} \n" +
                f"Fire Step: {self._osc_action_service.fire_mode_strength_step}\n" +
                f"Current: {channel_strength} \n"
            )
        else:
            self._osc_service.send_message_to_vrchat_chatbox("未连接")
