import asyncio
from typing import Optional, TYPE_CHECKING, Any
from pydglab_ws import Channel
import logging

from gui.ui_interface import UIInterface, UIFeature

if TYPE_CHECKING:
    from .osc_service import OSCService

logger = logging.getLogger(__name__)


class ChatboxService:
    def __init__(self, osc_service: 'OSCService', ui_callback: 'UIInterface') -> None:
        self.osc_service = osc_service
        self.ui_callback = ui_callback
        self.dglab_service: Optional[Any] = None  # 稍后设置
        self.enable_chatbox_status: int = 1
        self.previous_chatbox_status: bool = True
        self.chatbox_toggle_timer: Optional[asyncio.Task[None]] = None
        self.send_status_task: Optional[asyncio.Task[None]] = None

    def start_periodic_status_update(self) -> None:
        """启动周期性状态更新任务"""
        if self.send_status_task is None or self.send_status_task.done():
            self.send_status_task = asyncio.create_task(self.periodic_status_update())

    async def periodic_status_update(self) -> None:
        """
        周期性通过 ChatBox 发送当前的配置状态
        """
        while True:
            try:
                if self.enable_chatbox_status:
                    await self.send_strength_status(self.dglab_service)
                    self.previous_chatbox_status = True
                elif self.previous_chatbox_status:  # clear chatbox
                    self.osc_service.send_message_to_vrchat_chatbox("")
                    self.previous_chatbox_status = False
            except Exception as e:
                logger.error(f"periodic_status_update 任务中发生错误: {e}")
                await asyncio.sleep(5)
            await asyncio.sleep(3)

    async def chatbox_toggle_timer_handle(self) -> None:
        """1秒计时器 计时结束后切换 Chatbox 状态"""
        await asyncio.sleep(1)

        self.enable_chatbox_status = not self.enable_chatbox_status
        mode_name = "开启" if self.enable_chatbox_status else "关闭"
        logger.info("ChatBox显示状态切换为:" + mode_name)
        # 若关闭 ChatBox, 则立即发送一次空字符串
        if not self.enable_chatbox_status:
            self.osc_service.send_message_to_vrchat_chatbox("")
        self.chatbox_toggle_timer = None
        # 更新UI
        self.ui_callback.set_feature_state(UIFeature.CHATBOX_STATUS, self.enable_chatbox_status, silent=True)

    async def toggle_chatbox(self, value: int) -> None:
        """开关 ChatBox 内容发送"""
        if value == 1:  # 按下按键
            if self.chatbox_toggle_timer is not None:
                self.chatbox_toggle_timer.cancel()
            self.chatbox_toggle_timer = asyncio.create_task(self.chatbox_toggle_timer_handle())
        elif value == 0:  # 松开按键
            if self.chatbox_toggle_timer:
                self.chatbox_toggle_timer.cancel()
                self.chatbox_toggle_timer = None

    async def send_strength_status(self, dglab_service: Optional[Any] = None) -> None:
        """通过 ChatBox 发送当前强度数值"""
        if dglab_service and dglab_service.get_last_strength():
            last_strength = dglab_service.get_last_strength()
            mode_name_a = "交互" if dglab_service.is_dynamic_bone_enabled(Channel.A) else "面板"
            mode_name_b = "交互" if dglab_service.is_dynamic_bone_enabled(Channel.B) else "面板"
            current_channel = dglab_service.get_current_channel()
            channel_strength = f"[A]: {last_strength.a} B: {last_strength.b}" if current_channel == Channel.A else f"A: {last_strength.a} [B]: {last_strength.b}"
            pulse_name_a = dglab_service.get_current_pulse_name(Channel.A)
            pulse_name_b = dglab_service.get_current_pulse_name(Channel.B)
            
            self.osc_service.send_message_to_vrchat_chatbox(
                f"MAX A: {last_strength.a_limit} B: {last_strength.b_limit}\n"
                f"Mode A: {mode_name_a} B: {mode_name_b} \n"
                f"Pulse A: {pulse_name_a} B: {pulse_name_b} \n"
                f"Fire Step: {dglab_service.fire_mode_strength_step}\n"
                f"Current: {channel_strength} \n"
            )
        else:
            self.osc_service.send_message_to_vrchat_chatbox("未连接")