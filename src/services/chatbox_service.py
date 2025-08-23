import asyncio
from typing import Optional, TYPE_CHECKING
from pydglab_ws import Channel
import logging

from gui.ui_interface import UIInterface, UIFeature

if TYPE_CHECKING:
    from .osc_service import OSCService
    from .dglab_service import DGLabService

logger = logging.getLogger(__name__)


class ChatboxService:
    def __init__(self, dglab_service: 'DGLabService', osc_service: 'OSCService', ui_interface: 'UIInterface') -> None:
        self._dglab_service = dglab_service
        self._osc_service = osc_service
        self._ui_interface = ui_interface
        self.enable_chatbox_status: int = 1
        self._previous_chatbox_status: bool = True
        self._chatbox_toggle_timer: Optional[asyncio.Task[None]] = None
        self._send_status_task: Optional[asyncio.Task[None]] = None

    def start_periodic_status_update(self) -> None:
        """启动周期性状态更新任务"""
        if self._send_status_task is None or self._send_status_task.done():
            self._send_status_task = asyncio.create_task(self._periodic_status_update())

    async def _periodic_status_update(self) -> None:
        """
        周期性通过 ChatBox 发送当前的配置状态
        """
        while True:
            try:
                if self.enable_chatbox_status:
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

        self.enable_chatbox_status = not self.enable_chatbox_status
        mode_name = "开启" if self.enable_chatbox_status else "关闭"
        logger.info("ChatBox显示状态切换为:" + mode_name)
        # 若关闭 ChatBox, 则立即发送一次空字符串
        if not self.enable_chatbox_status:
            self._osc_service.send_message_to_vrchat_chatbox("")
        self._chatbox_toggle_timer = None
        # 更新UI
        self._ui_interface.set_feature_state(UIFeature.CHATBOX_STATUS, self.enable_chatbox_status, silent=True)

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
        last_strength = self._dglab_service.get_last_strength()
        if last_strength:
            mode_name_a = "交互" if self._dglab_service.is_dynamic_bone_enabled(Channel.A) else "面板"
            mode_name_b = "交互" if self._dglab_service.is_dynamic_bone_enabled(Channel.B) else "面板"
            current_channel = self._dglab_service.get_current_channel()
            channel_strength = f"[A]: {last_strength.a} B: {last_strength.b}" if current_channel == Channel.A else f"A: {last_strength.a} [B]: {last_strength.b}"
            pulse_name_a = self._dglab_service.get_current_pulse_name(Channel.A)
            pulse_name_b = self._dglab_service.get_current_pulse_name(Channel.B)
            
            self._osc_service.send_message_to_vrchat_chatbox(
                f"MAX A: {last_strength.a_limit} B: {last_strength.b_limit}\n"
                f"Mode A: {mode_name_a} B: {mode_name_b} \n"
                f"Pulse A: {pulse_name_a} B: {pulse_name_b} \n"
                f"Fire Step: {self._dglab_service.fire_mode_strength_step}\n"
                f"Current: {channel_strength} \n"
            )
        else:
            self._osc_service.send_message_to_vrchat_chatbox("未连接")