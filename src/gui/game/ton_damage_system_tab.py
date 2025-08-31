import asyncio
import json
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
                               QCheckBox, QLabel, QProgressBar, QSlider, QSpinBox, QToolTip)

from core.service_controller import ServiceController
from i18n import translate, language_signals
from models import Channel, SettingsDict
from websocket_client import WebSocketClient
from gui.ui_interface import UIInterface

logger = logging.getLogger(__name__)


class TonDamageSystemTab(QWidget):
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.settings: SettingsDict = ui_interface.settings
        self.websocket_client: Optional[WebSocketClient] = None

        # 累计伤害减免定时器
        self.damage_reduction_timer: QTimer = QTimer()
        self.damage_reduction_timer.timeout.connect(self.reduce_damage)
        self.damage_reduction_timer.start(1000)  # 每秒执行一次

        # UI组件类型注解
        self.damage_group: QGroupBox
        self.enable_damage_checkbox: QCheckBox
        self.display_name_label: QLabel
        self.websocket_status_label: QLabel
        self.damage_progress_bar: QProgressBar
        self.damage_reduction_label: QLabel
        self.damage_reduction_slider: QSlider
        self.damage_strength_label: QLabel
        self.damage_strength_slider: QSlider
        self.death_penalty_strength_label: QLabel
        self.death_penalty_strength_slider: QSlider
        self.death_penalty_time_spinbox: QSpinBox
        self.accumulated_damage_label: QLabel
        self.death_penalty_time_label: QLabel
        self.damage_controls: List[QWidget]

        self.init_ui()

        # 连接语言变更信号
        language_signals.language_changed.connect(self.update_ui_texts)

    @property
    def controller(self) -> Optional[ServiceController]:
        """通过UIInterface获取当前控制器"""
        return self.ui_interface.service_controller

    def init_ui(self) -> None:
        """初始化游戏联动选项卡UI"""
        layout = QVBoxLayout()

        # ToN Damage System
        damage_group = QGroupBox(translate("game_tab.title"))
        self.damage_group = damage_group  # 保持引用
        damage_layout = QFormLayout()

        damage_info_layout = QHBoxLayout()
        self.enable_damage_checkbox = QCheckBox(translate("game_tab.enable_damage_system"))
        self.enable_damage_checkbox.stateChanged.connect(self.toggle_damage_system)
        damage_info_layout.addWidget(self.enable_damage_checkbox)

        self.display_name_label = QLabel(f"{translate('game_tab.user_display_name')}: {translate('game_tab.unknown')}")
        damage_info_layout.addWidget(self.display_name_label)

        self.websocket_status_label = QLabel(
            f"{translate('game_tab.websocket_status')}: {translate('game_tab.disconnected')}")
        damage_info_layout.addWidget(self.websocket_status_label)

        damage_layout.addRow(damage_info_layout)

        # Damage Progress Bar
        self.damage_progress_bar = QProgressBar()
        self.damage_progress_bar.setRange(0, 100)
        self.damage_progress_bar.setValue(0)
        self.accumulated_damage_label = QLabel(translate("game_tab.accumulated_damage_label"))
        damage_layout.addRow(self.accumulated_damage_label, self.damage_progress_bar)

        # 配置滑动条
        slider_max_width = 450

        # 伤害减免滑动条
        damage_reduction_layout = QHBoxLayout()
        self.damage_reduction_label = QLabel(f"{translate('game_tab.damage_reduction')}: 2 / 10")
        self.damage_reduction_slider = QSlider(Qt.Orientation.Horizontal)
        self.damage_reduction_slider.setRange(0, 10)
        self.damage_reduction_slider.setValue(2)
        self.damage_reduction_slider.setMaximumWidth(slider_max_width)
        self.damage_reduction_slider.valueChanged.connect(self.update_damage_reduction_label)
        self.damage_reduction_slider.valueChanged.connect(lambda: self.show_tooltip(self.damage_reduction_slider))
        damage_reduction_layout.addWidget(self.damage_reduction_label)
        damage_reduction_layout.addWidget(self.damage_reduction_slider)
        damage_reduction_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        damage_layout.addRow(damage_reduction_layout)

        # 伤害强度滑动条
        damage_strength_layout = QHBoxLayout()
        self.damage_strength_label = QLabel(f"{translate('game_tab.damage_strength')}: 60 / 200")
        self.damage_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.damage_strength_slider.setRange(0, 200)
        self.damage_strength_slider.setValue(60)
        self.damage_strength_slider.setMaximumWidth(slider_max_width)
        self.damage_strength_slider.valueChanged.connect(self.update_damage_strength_label)
        self.damage_strength_slider.valueChanged.connect(lambda: self.show_tooltip(self.damage_strength_slider))
        damage_strength_layout.addWidget(self.damage_strength_label)
        damage_strength_layout.addWidget(self.damage_strength_slider)
        damage_strength_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        damage_layout.addRow(damage_strength_layout)

        # 死亡惩罚强度滑动条
        death_penalty_strength_layout = QHBoxLayout()
        self.death_penalty_strength_label = QLabel(f"{translate('game_tab.death_penalty')}: 30 / 100")
        self.death_penalty_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.death_penalty_strength_slider.setRange(0, 100)
        self.death_penalty_strength_slider.setValue(30)
        self.death_penalty_strength_slider.setMaximumWidth(slider_max_width)
        self.death_penalty_strength_slider.valueChanged.connect(self.update_death_penalty_label)
        self.death_penalty_strength_slider.valueChanged.connect(
            lambda: self.show_tooltip(self.death_penalty_strength_slider))
        death_penalty_strength_layout.addWidget(self.death_penalty_strength_label)
        death_penalty_strength_layout.addWidget(self.death_penalty_strength_slider)
        death_penalty_strength_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        damage_layout.addRow(death_penalty_strength_layout)

        # 死亡惩罚持续时间
        self.death_penalty_time_spinbox = QSpinBox()
        self.death_penalty_time_spinbox.setRange(0, 60)
        self.death_penalty_time_spinbox.setValue(5)
        self.death_penalty_time_label = QLabel(translate("game_tab.death_penalty_time_label"))
        damage_layout.addRow(self.death_penalty_time_label, self.death_penalty_time_spinbox)

        damage_group.setLayout(damage_layout)
        layout.addWidget(damage_group)
        layout.addStretch()

        self.setLayout(layout)

        # 创建需要控制启用/禁用状态的组件列表（不包括复选框和标签）
        self.damage_controls = [
            self.damage_progress_bar,
            self.damage_reduction_slider,
            self.damage_strength_slider,
            self.death_penalty_strength_slider,
            self.death_penalty_time_spinbox
        ]

        # 初始状态：禁用控件
        self.set_damage_controls_enabled(False)

    def show_tooltip(self, slider: QSlider) -> None:
        """显示滑动条当前值的工具提示在滑块上方"""
        if slider:
            value = slider.value()

            # 简化的工具提示显示，直接显示在鼠标位置附近
            # 获取滑块的全局位置
            global_pos = slider.mapToGlobal(slider.rect().center())
            tooltip_pos = QPoint(global_pos.x(), global_pos.y() - 30)

            QToolTip.showText(tooltip_pos, f"{value}", slider)

    def set_damage_controls_enabled(self, enabled: bool) -> None:
        """启用或禁用伤害系统控件（不包括复选框和状态标签）"""
        control: QWidget
        for control in self.damage_controls:
            control.setEnabled(enabled)

    def toggle_damage_system(self, checked: bool) -> None:
        """Enable or disable the damage system, including WebSocket connection."""
        if checked:
            logger.info("Enabling damage system and starting WebSocket connection.")
            self.set_damage_controls_enabled(True)
            self.websocket_client = WebSocketClient("ws://localhost:11398")

            # Connect signals
            self.websocket_client.message_received.connect(self.handle_websocket_message)
            self.websocket_client.status_update_signal.connect(self.update_websocket_status)
            self.websocket_client.error_signal.connect(self.handle_websocket_error)

            # Start the WebSocket connection
            asyncio.create_task(self.websocket_client.start_connection())
        else:
            logger.info("Disabling damage system and closing WebSocket connection.")
            self.set_damage_controls_enabled(False)
            if self.websocket_client:
                # Schedule the async close operation
                asyncio.create_task(self.websocket_client.close())
                self.websocket_client = None

            # Reset WebSocket status display
            self.websocket_status_label.setText(
                f"{translate('game_tab.websocket_status')}: {translate('game_tab.disconnected')}")
            self.websocket_status_label.setStyleSheet("color: red;")

    def reduce_damage(self) -> None:
        """Reduce the accumulated damage based on the set reduction strength every second."""
        reduction_strength = self.damage_reduction_slider.value()
        current_value = self.damage_progress_bar.value()

        if current_value > 0:
            new_value = max(0, current_value - reduction_strength)
            self.damage_progress_bar.setValue(new_value)

            if self.controller and new_value != current_value:
                # TODO: Implement damage intensity control via dglab_service
                # self.controller.set_damage_intensity(new_value)
                pass

            logger.info(f"Damage reduced by {reduction_strength}%. Current damage: {new_value}%")

    def handle_websocket_message(self, message: str) -> None:
        """Handle incoming WebSocket messages and update status or damage accordingly."""
        logger.info(f"Received WebSocket message: {message}")

        # Parse message as JSON
        try:
            parsed_message = json.loads(message)
        except json.JSONDecodeError:
            try:
                parsed_message = eval(message)  # Fallback for dictionary-like strings
            except:
                logger.error("Received message is not valid JSON format.")
                return

        # Handle different message types
        if parsed_message.get("Type") == "DAMAGED":
            damage_value = parsed_message.get("Value", 0)  # 确保获取大小写正确的 "Value"
            self.accumulate_damage(damage_value)
        elif parsed_message.get("Type") == "SAVED":
            self.reset_damage()
            logger.info("存档更新，重置强度")
        elif parsed_message.get("Type") == "ALIVE":
            is_alive = parsed_message.get("Value", 0)
            if is_alive == 0:  # Player is dead
                self.trigger_death_penalty()
                logger.info("已死亡，触发死亡惩罚")
        elif parsed_message.get("Type") == "STATS":
            if parsed_message.get("DisplayName"):
                user_display_name = parsed_message.get("DisplayName")
                self.display_name_label.setText(f"{translate('game_tab.user_display_name')}: {user_display_name}")
        elif parsed_message.get("Type") == "CONNECTED":
            if parsed_message.get("DisplayName"):
                user_display_name = parsed_message.get("DisplayName")
                self.display_name_label.setText(f"{translate('game_tab.user_display_name')}: {user_display_name}")

    def update_websocket_status(self, status: str) -> None:
        """Update WebSocket status label based on connection status."""
        logger.info(f"WebSocket status updated: {status}")

        if status.lower() == "connected":
            self.websocket_status_label.setText(
                f"{translate('game_tab.websocket_status')}: {translate('game_tab.connected')}")
            self.websocket_status_label.setStyleSheet("color: green;")
        elif status.lower() == "disconnected":
            self.websocket_status_label.setText(
                f"{translate('game_tab.websocket_status')}: {translate('game_tab.disconnected')}")
            self.websocket_status_label.setStyleSheet("color: red;")
        else:
            logger.warning(f"Unexpected WebSocket status: {status}")
            self.websocket_status_label.setText(
                f"{translate('game_tab.websocket_status')}: {translate('websocket.error_status')} - {status}")
            self.websocket_status_label.setStyleSheet("color: orange;")

    def handle_websocket_error(self, error_message: str) -> None:
        """Handle WebSocket errors by displaying an error message."""
        logger.error(f"WebSocket error: {error_message}")
        self.websocket_status_label.setText(
            f"{translate('game_tab.websocket_status')}: {translate('websocket.error_status')} - {error_message}")
        self.websocket_status_label.setStyleSheet("color: orange;")

    def accumulate_damage(self, value: int) -> None:
        """Accumulate damage based on incoming value."""
        current_value = self.damage_progress_bar.value()
        max_damage = min(100, current_value + value)
        new_value = max_damage
        self.damage_progress_bar.setValue(new_value)
        logger.info(f"Accumulated damage by {value}%. Current damage: {new_value}%")

    def reset_damage(self) -> None:
        """Reset the damage accumulation."""
        logger.info("Resetting damage accumulation.")
        self.damage_progress_bar.setValue(0)

        if self.controller:
            # TODO: Implement damage intensity control via dglab_service
            # self.controller.set_damage_intensity(0)
            pass

    def trigger_death_penalty(self) -> None:
        """Trigger death penalty by setting damage to 100% and applying penalty."""
        penalty_strength = self.death_penalty_strength_slider.value()
        penalty_time = self.death_penalty_time_spinbox.value()

        # Set damage to 100%
        self.damage_progress_bar.setValue(100)

        logger.warning(f"Death penalty triggered: Strength={penalty_strength}, Time={penalty_time}s")

        last_strength_mod = self.controller.osc_action_service.get_last_strength() if self.controller else None
        if self.controller and last_strength_mod:
            logger.warning(f"Death penalty triggered: a {last_strength_mod['strength'][Channel.A]} fire {penalty_strength}")

            # Apply death penalty for specified time
            asyncio.create_task(self._apply_death_penalty_async(penalty_strength, penalty_time))

    async def _apply_death_penalty_async(self, _strength: int, duration: int) -> None:
        """Apply death penalty asynchronously for the specified duration."""
        if self.controller:
            # Apply penalty strength
            # TODO: Implement damage intensity control via dglab_service  
            # self.controller.set_damage_intensity(100)
            await asyncio.sleep(duration)
            # Reset after penalty time
            # TODO: Implement damage intensity control via dglab_service
            # self.controller.set_damage_intensity(0)
            self.damage_progress_bar.setValue(0)

    def update_damage_reduction_label(self) -> None:
        """更新伤害减免标签"""
        value = self.damage_reduction_slider.value()
        self.damage_reduction_label.setText(f"{translate('game_tab.damage_reduction')}: {value} / 10")

    def update_damage_strength_label(self) -> None:
        """更新伤害强度标签"""
        value = self.damage_strength_slider.value()
        self.damage_strength_label.setText(f"{translate('game_tab.damage_strength')}: {value} / 200")

    def update_death_penalty_label(self) -> None:
        """更新死亡惩罚标签"""
        value = self.death_penalty_strength_slider.value()
        self.death_penalty_strength_label.setText(f"{translate('game_tab.death_penalty')}: {value} / 100")

    def update_ui_texts(self) -> None:
        """更新UI文本为当前语言"""
        self.damage_group.setTitle(translate("game_tab.title"))
        self.enable_damage_checkbox.setText(translate("game_tab.enable_damage_system"))

        # 更新显示名称标签 - 保持当前显示的用户名
        current_display_text = self.display_name_label.text()
        if ": " in current_display_text:
            # 提取当前显示的用户名
            current_name = current_display_text.split(": ", 1)[1]
            self.display_name_label.setText(f"{translate('game_tab.user_display_name')}: {current_name}")
        else:
            # 如果没有用户名，显示默认值
            self.display_name_label.setText(
                f"{translate('game_tab.user_display_name')}: {translate('game_tab.unknown')}")

        # 更新WebSocket状态标签 - 保持当前连接状态
        current_status_text = self.websocket_status_label.text()
        if ": " in current_status_text:
            # 从当前文本中提取状态部分，但需要重新翻译
            if "connected" in current_status_text.lower() or "已连接" in current_status_text or "接続済み" in current_status_text:
                self.websocket_status_label.setText(
                    f"{translate('game_tab.websocket_status')}: {translate('game_tab.connected')}")
            elif "error" in current_status_text.lower() or "错误" in current_status_text or "エラー" in current_status_text:
                # 保持错误信息，只更新前缀
                error_part = current_status_text.split(": ", 1)[1]
                self.websocket_status_label.setText(f"{translate('game_tab.websocket_status')}: {error_part}")
            else:
                self.websocket_status_label.setText(
                    f"{translate('game_tab.websocket_status')}: {translate('game_tab.disconnected')}")
        else:
            self.websocket_status_label.setText(
                f"{translate('game_tab.websocket_status')}: {translate('game_tab.disconnected')}")

        # 更新滑动条标签 - 使用当前滑动条的值
        damage_reduction_value = self.damage_reduction_slider.value()
        self.damage_reduction_label.setText(f"{translate('game_tab.damage_reduction')}: {damage_reduction_value} / 10")

        damage_strength_value = self.damage_strength_slider.value()
        self.damage_strength_label.setText(f"{translate('game_tab.damage_strength')}: {damage_strength_value} / 200")

        death_penalty_value = self.death_penalty_strength_slider.value()
        self.death_penalty_strength_label.setText(f"{translate('game_tab.death_penalty')}: {death_penalty_value} / 100")

        # 更新其他标签
        self.accumulated_damage_label.setText(translate("game_tab.accumulated_damage_label"))
        self.death_penalty_time_label.setText(translate("game_tab.death_penalty_time_label"))
