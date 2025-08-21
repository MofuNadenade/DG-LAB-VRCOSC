from pythonosc import udp_client
from typing import Any
import logging

from gui.ui_interface import UIInterface

logger = logging.getLogger(__name__)


class OSCService:
    def __init__(self, osc_client: udp_client.SimpleUDPClient, ui_callback: 'UIInterface') -> None:
        self.osc_client = osc_client
        self.ui_callback = ui_callback

    async def handle_osc_message(self, address: str, *args: Any) -> None:
        """
        处理 OSC 消息
        1. Bool: Bool 类型变量触发时，VRC 会先后发送 True 与 False, 回调中仅处理 True
        2. Float: -1.0 to 1.0， 但对于 Contact 与  Physbones 来说范围为 0.0-1.0
        """
        # Parameters Debug
        logger.debug(f"Received OSC message on {address} with arguments {args}")

        # 支持所有OSC地址 - 直接使用完整地址匹配
        if address in self.ui_callback.address_registry.addresses_by_code:
            address_obj = self.ui_callback.address_registry.addresses_by_code[address]
            await self.ui_callback.binding_registry.handle(address_obj, *args)

    def send_message_to_vrchat_chatbox(self, message: str) -> None:
        """
        /chatbox/input s b n Input text into the chatbox.
        """
        self.osc_client.send_message("/chatbox/input", [message, True, False])

    def send_value_to_vrchat(self, path: str, value: Any) -> None:
        """
        发送值到 VRChat
        """
        self.osc_client.send_message(path, value)