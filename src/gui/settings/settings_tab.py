import asyncio
import logging
from typing import Optional

from PySide6.QtCore import Qt, QPoint, QLocale
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
                               QComboBox, QSpinBox, QLabel, QCheckBox, QSlider, QToolTip,
                               QPushButton, QMessageBox)

from core.service_controller import ServiceController
from core.dglab_pulse import PulseRegistry
from i18n import translate, language_signals
from models import Channel, StrengthData, StrengthOperationType, SettingsDict
from gui.ui_interface import UIInterface
from gui.widgets import EditableComboBox

logger = logging.getLogger(__name__)


class SettingsTab(QWidget):
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.settings: SettingsDict = ui_interface.settings

        # 防止重复绑定的标志
        self._signals_connected: bool = False

        # UI组件类型注解
        self.controller_group: QGroupBox
        self.a_channel_label: QLabel
        self.a_channel_slider: QSlider
        self.b_channel_label: QLabel
        self.b_channel_slider: QSlider
        self.fire_mode_disabled_checkbox: QCheckBox
        self.enable_panel_control_checkbox: QCheckBox
        self.enable_chatbox_status_checkbox: QCheckBox
        self.dynamic_bone_mode_a_checkbox: QCheckBox
        self.dynamic_bone_mode_b_checkbox: QCheckBox
        self.current_channel_label: QLabel
        self.current_pulse_a_combobox: QComboBox
        self.current_pulse_b_combobox: QComboBox
        self.fire_mode_strength_step_spinbox: QSpinBox
        self.save_settings_btn: QPushButton
        self.current_pulse_a_label: QLabel
        self.current_pulse_b_label: QLabel
        self.fire_mode_strength_step_label: QLabel

        self.init_ui()

        # 连接语言变更信号
        language_signals.language_changed.connect(self.update_ui_texts)

    @property
    def service_controller(self) -> Optional[ServiceController]:
        """通过UIInterface获取当前控制器"""
        return self.ui_interface.service_controller

    @property
    def pulse_registry(self) -> PulseRegistry:
        """通过UIInterface获取波形注册表"""
        return self.ui_interface.registries.pulse_registry

    def init_ui(self) -> None:
        """初始化设备控制选项卡UI"""
        layout = QVBoxLayout()

        # 控制器参数设置
        controller_group = QGroupBox(translate("controller_tab.title"))
        self.controller_group = controller_group  # 保持引用以便启用/禁用
        controller_group.setEnabled(False)  # 默认禁用
        controller_form = QFormLayout()

        # 添加 A 通道滑动条和标签
        self.a_channel_label = QLabel(f"A {translate('controller_tab.channel_intensity')}: 0 / 100")
        self.a_channel_slider = QSlider(Qt.Orientation.Horizontal)
        self.a_channel_slider.setRange(0, 100)
        self.a_channel_slider.valueChanged.connect(self.set_a_channel_strength)
        self.a_channel_slider.valueChanged.connect(lambda: self.show_tooltip(self.a_channel_slider))
        controller_form.addRow(self.a_channel_label)
        controller_form.addRow(self.a_channel_slider)

        # 添加 B 通道滑动条和标签
        self.b_channel_label = QLabel(f"B {translate('controller_tab.channel_intensity')}: 0 / 100")
        self.b_channel_slider = QSlider(Qt.Orientation.Horizontal)
        self.b_channel_slider.setRange(0, 100)
        self.b_channel_slider.valueChanged.connect(self.set_b_channel_strength)
        self.b_channel_slider.valueChanged.connect(lambda: self.show_tooltip(self.b_channel_slider))
        controller_form.addRow(self.b_channel_label)
        controller_form.addRow(self.b_channel_slider)

        # 功能选项
        self.fire_mode_disabled_checkbox = QCheckBox(translate("controller_tab.disable_fire_mode"))
        self.fire_mode_disabled_checkbox.setChecked(False)
        controller_form.addRow(self.fire_mode_disabled_checkbox)

        self.enable_panel_control_checkbox = QCheckBox(translate("controller_tab.enable_panel_control"))
        self.enable_panel_control_checkbox.setChecked(True)
        controller_form.addRow(self.enable_panel_control_checkbox)

        self.enable_chatbox_status_checkbox = QCheckBox(translate("controller_tab.enable_chatbox"))
        self.enable_chatbox_status_checkbox.setChecked(False)  # 默认关闭ChatBox
        controller_form.addRow(self.enable_chatbox_status_checkbox)

        # 动骨模式和当前通道显示
        dynamic_bone_layout = QHBoxLayout()
        self.dynamic_bone_mode_a_checkbox = QCheckBox(f"A{translate('controller_tab.interaction_mode')}")
        self.dynamic_bone_mode_b_checkbox = QCheckBox(f"B{translate('controller_tab.interaction_mode')}")
        self.current_channel_label = QLabel(
            f"{translate('controller_tab.current_panel_channel')}: {translate('controller_tab.not_set')}")

        dynamic_bone_layout.addWidget(self.dynamic_bone_mode_a_checkbox)
        dynamic_bone_layout.addWidget(self.dynamic_bone_mode_b_checkbox)
        dynamic_bone_layout.addWidget(self.current_channel_label)

        controller_form.addRow(dynamic_bone_layout)

        # 波形模式选择
        pulse_options = list(self.pulse_registry.pulses_by_name.keys())

        self.current_pulse_a_combobox = EditableComboBox(pulse_options, allow_manual_input=False)
        # 强制使用英文区域设置，避免数字显示为繁体中文
        self.current_pulse_a_combobox.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))

        self.current_pulse_b_combobox = EditableComboBox(pulse_options, allow_manual_input=False)
        # 强制使用英文区域设置，避免数字显示为繁体中文
        self.current_pulse_b_combobox.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.current_pulse_a_label = QLabel(f"A{translate('controller_tab.pulse')}:")
        self.current_pulse_b_label = QLabel(f"B{translate('controller_tab.pulse')}:")
        controller_form.addRow(self.current_pulse_a_label, self.current_pulse_a_combobox)
        controller_form.addRow(self.current_pulse_b_label, self.current_pulse_b_combobox)

        # 强度步长
        self.fire_mode_strength_step_spinbox = QSpinBox()
        # 强制使用英文区域设置，避免数字显示为繁体中文
        self.fire_mode_strength_step_spinbox.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.fire_mode_strength_step_spinbox.setRange(0, 100)
        self.fire_mode_strength_step_spinbox.setValue(30)
        self.fire_mode_strength_step_label = QLabel(translate("controller_tab.fire_mode_strength_step_label"))
        controller_form.addRow(self.fire_mode_strength_step_label, self.fire_mode_strength_step_spinbox)

        # 添加保存设置按钮
        self.save_settings_btn = QPushButton(translate("osc_address_tab.save_config"))
        self.save_settings_btn.clicked.connect(self.save_settings)
        self.save_settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.save_settings_btn.setToolTip(translate("controller_tab.save_settings_tooltip"))
        controller_form.addRow(self.save_settings_btn)

        controller_group.setLayout(controller_form)
        layout.addWidget(controller_group)
        layout.addStretch()

        self.setLayout(layout)

    def update_pulse_comboboxes(self) -> None:
        """更新波形下拉框选项"""
        # 清空现有选项
        self.current_pulse_a_combobox.clear()
        self.current_pulse_b_combobox.clear()

        self.current_pulse_a_combobox.blockSignals(True)
        self.current_pulse_b_combobox.blockSignals(True)

        # 添加"无波形"选项，UserData为-1
        no_waveform_text = translate("controller_tab.no_waveform")
        self.current_pulse_a_combobox.addItem(no_waveform_text, -1)
        self.current_pulse_b_combobox.addItem(no_waveform_text, -1)

        # 重新添加所有波形选项（包括自定义波形），UserData为pulse的index
        for pulse in self.pulse_registry.pulses:
            self.current_pulse_a_combobox.addItem(pulse.name, pulse.index)
            self.current_pulse_b_combobox.addItem(pulse.name, pulse.index)

        self.current_pulse_a_combobox.blockSignals(False)
        self.current_pulse_b_combobox.blockSignals(False)

    def bind_settings(self) -> None:
        """将GUI设置与ServiceController变量绑定"""
        if self.service_controller:
            # 防止重复绑定信号槽
            if self._signals_connected:
                logger.debug("信号槽已连接，跳过重复绑定")
                return

            self.fire_mode_disabled_checkbox.toggled.connect(self.on_fire_mode_disabled_changed)
            self.enable_panel_control_checkbox.toggled.connect(self.on_panel_control_enabled_changed)
            self.dynamic_bone_mode_a_checkbox.toggled.connect(self.on_dynamic_bone_mode_a_changed)
            self.dynamic_bone_mode_b_checkbox.toggled.connect(self.on_dynamic_bone_mode_b_changed)
            self.current_pulse_a_combobox.currentIndexChanged.connect(self.on_current_pulse_a_changed)
            self.current_pulse_b_combobox.currentIndexChanged.connect(self.on_current_pulse_b_changed)
            self.enable_chatbox_status_checkbox.toggled.connect(self.on_chatbox_status_enabled_changed)
            self.fire_mode_strength_step_spinbox.valueChanged.connect(self.on_strength_step_changed)

            # 标记信号槽已连接
            self._signals_connected = True
            logger.info("ServiceController 参数已绑定")
        else:
            logger.warning("Controller is not initialized yet.")

    def on_strength_step_changed(self, value: int) -> None:
        """当强度步长发生变化时更新控制器"""
        if self.service_controller:
            self.service_controller.osc_action_service.fire_mode_strength_step = value
            logger.info(f"Updated strength step to {value}")
            self.service_controller.osc_service.send_value_to_vrchat("/avatar/parameters/SoundPad/Volume", 0.01 * value)

    def on_fire_mode_disabled_changed(self, state: bool) -> None:
        """当禁用火力模式复选框状态改变时"""
        if self.service_controller:
            self.service_controller.osc_action_service.fire_mode_disabled = state
            logger.info(f"Fire mode disabled: {self.service_controller.osc_action_service.fire_mode_disabled}")

    def on_panel_control_enabled_changed(self, state: bool) -> None:
        """当启用面板控制复选框状态改变时"""
        if self.service_controller:
            self.service_controller.osc_action_service.enable_panel_control = state
            logger.info(f"Panel control enabled: {self.service_controller.osc_action_service.enable_panel_control}")
            self.service_controller.osc_service.send_value_to_vrchat("/avatar/parameters/SoundPad/PanelControl", bool(state))

    def on_dynamic_bone_mode_a_changed(self, state: bool) -> None:
        """当动骨模式A复选框状态改变时"""
        if self.service_controller:
            self.service_controller.osc_action_service.set_dynamic_bone_mode(Channel.A, state)
            logger.info(f"Dynamic bone mode A: {self.service_controller.osc_action_service.is_dynamic_bone_enabled(Channel.A)}")

    def on_dynamic_bone_mode_b_changed(self, state: bool) -> None:
        """当动骨模式B复选框状态改变时"""
        if self.service_controller:
            self.service_controller.osc_action_service.set_dynamic_bone_mode(Channel.B, state)
            logger.info(f"Dynamic bone mode B: {self.service_controller.osc_action_service.is_dynamic_bone_enabled(Channel.B)}")

    def on_current_pulse_a_changed(self, index: int) -> None:
        """当波形A模式发生变化时"""
        if not self.service_controller:
            return

        # 获取UserData（pulse的真实index）
        pulse_index = self.current_pulse_a_combobox.currentData()
        if pulse_index is None:
            logger.warning("A通道波形索引为空")
            return

        # 如果是"无波形"选项（UserData为-1）
        if pulse_index == -1:
            # 设置为None表示无波形
            asyncio.create_task(self.service_controller.osc_action_service.set_pulse(Channel.A, None))
            logger.info("A通道波形模式已更新为 无波形")
            return

        # 验证索引有效性
        if not self.pulse_registry.is_valid_index(pulse_index):
            logger.warning(f"A通道波形索引无效: {pulse_index}")
            return

        # 获取 Pulse 对象
        pulse = self.pulse_registry.get_pulse_by_index(pulse_index)
        if pulse is None:
            logger.warning(f"A通道未找到索引为{pulse_index}的波形")
            return

        asyncio.create_task(self.service_controller.osc_action_service.set_pulse(Channel.A, pulse))
        logger.info(f"A通道波形模式已更新为 {pulse.name}")

    def on_current_pulse_b_changed(self, index: int) -> None:
        """当波形B模式发生变化时"""
        if not self.service_controller:
            return

        # 获取UserData（pulse的真实index）
        pulse_index = self.current_pulse_b_combobox.currentData()
        if pulse_index is None:
            logger.warning("B通道波形索引为空")
            return

        # 如果是"无波形"选项（UserData为-1）
        if pulse_index == -1:
            # 设置为None表示无波形
            asyncio.create_task(self.service_controller.osc_action_service.set_pulse(Channel.B, None))
            logger.info("B通道波形模式已更新为 无波形")
            return

        # 验证索引有效性
        if not self.pulse_registry.is_valid_index(pulse_index):
            logger.warning(f"B通道波形索引无效: {pulse_index}")
            return

        # 获取 Pulse 对象
        pulse = self.pulse_registry.get_pulse_by_index(pulse_index)
        if pulse is None:
            logger.warning(f"B通道未找到索引为{pulse_index}的波形")
            return

        asyncio.create_task(self.service_controller.osc_action_service.set_pulse(Channel.B, pulse))
        logger.info(f"B通道波形模式已更新为 {pulse.name}")

    def on_chatbox_status_enabled_changed(self, state: bool) -> None:
        """当ChatBox状态启用复选框状态改变时"""
        if self.service_controller:
            self.service_controller.chatbox_service.set_enabled(state)
            logger.info(f"ChatBox status enabled: {self.service_controller.chatbox_service.is_enabled}")

    def save_settings(self) -> None:
        """保存设备控制器设置到配置文件"""
        try:
            # 确保controller字典存在
            if 'controller' not in self.settings:
                self.settings['controller'] = {}
            
            # 保存ChatBox状态
            self.settings['controller']['enable_chatbox_status'] = self.enable_chatbox_status_checkbox.isChecked()

            # 保存强度步长
            self.settings['controller']['fire_mode_strength_step'] = self.fire_mode_strength_step_spinbox.value()

            # 保存其他可配置的设置
            self.settings['controller']['fire_mode_disabled'] = self.fire_mode_disabled_checkbox.isChecked()
            self.settings['controller']['enable_panel_control'] = self.enable_panel_control_checkbox.isChecked()
            self.settings['controller']['dynamic_bone_mode_a'] = self.dynamic_bone_mode_a_checkbox.isChecked()
            self.settings['controller']['dynamic_bone_mode_b'] = self.dynamic_bone_mode_b_checkbox.isChecked()

            # 保存波形选择
            self.settings['controller']['current_pulse_a'] = self.current_pulse_a_combobox.currentText()
            self.settings['controller']['current_pulse_b'] = self.current_pulse_b_combobox.currentText()

            # 调用UIInterface的保存方法
            self.ui_interface.save_settings()

            # 显示成功消息
            QMessageBox.information(self, translate("common.save_success"),
                                    translate("controller_tab.settings_saved"))
            logger.info("Controller settings saved successfully")

        except Exception as e:
            error_msg = translate("controller_tab.save_failed").format(str(e))
            logger.error(error_msg)
            QMessageBox.critical(self, translate("common.save_failed"), error_msg)

    def set_a_channel_strength(self, value: int) -> None:
        """根据滑动条的值设定 A 通道强度"""
        if self.service_controller:
            asyncio.create_task(
                self.service_controller.osc_action_service.adjust_strength(StrengthOperationType.SET_TO, value, Channel.A))
            last_strength = self.service_controller.osc_action_service.get_last_strength()
            if last_strength:
                last_strength['strength'][Channel.A] = value  # 同步更新 last_strength 的 A 通道值

        self.a_channel_slider.setToolTip(f"SET A {translate('channel.strength_display')}: {value}")

    def set_b_channel_strength(self, value: int) -> None:
        """根据滑动条的值设定 B 通道强度"""
        if self.service_controller:
            asyncio.create_task(
                self.service_controller.osc_action_service.adjust_strength(StrengthOperationType.SET_TO, value, Channel.B))
            last_strength = self.service_controller.osc_action_service.get_last_strength()
            if last_strength:
                last_strength['strength'][Channel.B] = value  # 同步更新 last_strength 的 B 通道值

        self.b_channel_slider.setToolTip(f"SET B {translate('channel.strength_display')}: {value}")

    def show_tooltip(self, slider: QSlider) -> None:
        """显示滑动条当前值的工具提示在滑块上方"""
        if slider:
            value = slider.value()

            # 简化的工具提示显示，直接显示在鼠标位置附近
            # 获取滑块的全局位置
            global_pos = slider.mapToGlobal(slider.rect().center())
            tooltip_pos = QPoint(global_pos.x(), global_pos.y() - 30)

            QToolTip.showText(tooltip_pos, f"{value}", slider)

    def on_current_channel_updated(self, channel: Channel) -> None:
        """更新当前选择通道显示"""
        channel_name = "A" if channel == Channel.A else "B"
        self.current_channel_label.setText(f"{translate('channel.current_control')}: {channel_name}")

    def on_strength_data_updated(self, strength_data: StrengthData) -> None:
        """更新通道强度"""
        logger.info(f"通道状态已更新 - A通道强度: {strength_data['strength'][Channel.A]}, B通道强度: {strength_data['strength'][Channel.B]}")

        last_strength = self.service_controller.osc_action_service.get_last_strength() if self.service_controller else None
        if self.service_controller and last_strength:
            self.a_channel_slider.blockSignals(True)
            self.a_channel_slider.setRange(0, last_strength['strength_limit'][Channel.A])  # 根据限制更新范围
            self.a_channel_slider.setValue(last_strength['strength'][Channel.A])
            self.a_channel_slider.blockSignals(False)
            pulse_a = self.service_controller.osc_action_service.get_current_pulse(Channel.A)
            pulse_a_name = pulse_a.name if pulse_a else translate("controller_tab.no_waveform")
            self.a_channel_label.setText(
                f"A {translate('channel.strength_display')}: {last_strength['strength'][Channel.A]} {translate('channel.strength_limit')}: {last_strength['strength_limit'][Channel.A]}  {translate('channel.pulse')}: {pulse_a_name}")

            self.b_channel_slider.blockSignals(True)
            self.b_channel_slider.setRange(0, last_strength['strength_limit'][Channel.B])  # 根据限制更新范围
            self.b_channel_slider.setValue(last_strength['strength'][Channel.B])
            self.b_channel_slider.blockSignals(False)
            pulse_b = self.service_controller.osc_action_service.get_current_pulse(Channel.B)
            pulse_b_name = pulse_b.name if pulse_b else translate("controller_tab.no_waveform")
            self.b_channel_label.setText(
                f"B {translate('channel.strength_display')}: {last_strength['strength'][Channel.B]} {translate('channel.strength_limit')}: {last_strength['strength_limit'][Channel.B]}  {translate('channel.pulse')}: {pulse_b_name}")

    def update_ui_texts(self) -> None:
        """更新UI文本为当前语言"""
        self.controller_group.setTitle(translate("controller_tab.title"))
        self.fire_mode_disabled_checkbox.setText(translate("controller_tab.disable_fire_mode"))
        self.enable_panel_control_checkbox.setText(translate("controller_tab.enable_panel_control"))
        self.enable_chatbox_status_checkbox.setText(translate("controller_tab.enable_chatbox"))
        self.dynamic_bone_mode_a_checkbox.setText(f"A{translate('controller_tab.interaction_mode')}")
        self.dynamic_bone_mode_b_checkbox.setText(f"B{translate('controller_tab.interaction_mode')}")
        self.save_settings_btn.setText(translate("osc_address_tab.save_config"))

        # 更新通道强度标签
        a_value = self.a_channel_slider.value()
        b_value = self.b_channel_slider.value()
        self.a_channel_label.setText(f"A {translate('controller_tab.channel_intensity')}: {a_value} / 100")
        self.b_channel_label.setText(f"B {translate('controller_tab.channel_intensity')}: {b_value} / 100")

        # 更新当前通道标签 - 保持当前显示的通道名
        current_channel_text = self.current_channel_label.text()
        if ": " in current_channel_text:
            # 提取当前显示的通道名
            current_channel = current_channel_text.split(": ", 1)[1]
            # 如果通道名不是翻译键，保持原样；否则重新翻译
            if current_channel in [translate('controller_tab.not_set'), "not_set", "未设置", "未設定"]:
                self.current_channel_label.setText(
                    f"{translate('controller_tab.current_panel_channel')}: {translate('controller_tab.not_set')}")
            else:
                self.current_channel_label.setText(
                    f"{translate('controller_tab.current_panel_channel')}: {current_channel}")
        else:
            self.current_channel_label.setText(
                f"{translate('controller_tab.current_panel_channel')}: {translate('controller_tab.not_set')}")

        # 更新表单行标签
        self.current_pulse_a_label.setText(f"A{translate('controller_tab.pulse')}:")
        self.current_pulse_b_label.setText(f"B{translate('controller_tab.pulse')}:")
        self.fire_mode_strength_step_label.setText(translate("controller_tab.fire_mode_strength_step_label"))

        # 更新工具提示
        self.save_settings_btn.setToolTip(translate("controller_tab.save_settings_tooltip"))
