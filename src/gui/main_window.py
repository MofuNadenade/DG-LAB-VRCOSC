import functools
import logging
from typing import Optional, List

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QMainWindow, QTabWidget

from config import default_load_settings, save_settings
from core import OSCActionType, OSCOptionsProvider
from core.service_controller import ServiceController
from core.dglab_pulse import Pulse
from core.registries import Registries
from gui.about_tab import AboutTab
from gui.controller_settings_tab import ControllerSettingsTab
from gui.log_viewer_tab import LogViewerTab
from gui.network_config_tab import NetworkConfigTab
from gui.osc_address_tab import OSCAddressTab
from gui.pulse_editor_tab import PulseEditorTab
from gui.ton_damage_system_tab import TonDamageSystemTab
from i18n import translate, language_signals, set_language
from models import ConnectionState, StrengthData, Channel, SettingsDict, OSCValue, OSCBindingDict, UIFeature
from util import resource_path

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        # 加载设置
        self.settings: SettingsDict = default_load_settings()

        # 设置语言
        language: str = self.settings.get('language', 'zh')
        set_language(language)

        # 初始化控制器相关组件
        self.controller: Optional[ServiceController] = None
        self.registries: Registries = Registries()
        self.options_provider: OSCOptionsProvider = OSCOptionsProvider(self.registries)

        # 从配置加载所有数据
        self._load_all_settings()

        # GUI组件类型注解
        self.tab_widget: QTabWidget
        self.network_tab: 'NetworkConfigTab'
        self.controller_tab: 'ControllerSettingsTab'
        self.ton_tab: 'TonDamageSystemTab'
        self.osc_address_tab: 'OSCAddressTab'
        self.pulse_editor_tab: 'PulseEditorTab'
        self.log_tab: 'LogViewerTab'
        self.about_tab: 'AboutTab'

        self._init_ui()

        # 连接状态跟踪
        self._current_connection_state: ConnectionState = ConnectionState.DISCONNECTED

        # 连接语言变更信号
        language_signals.language_changed.connect(self.update_ui_texts)

    # === 用户界面初始化方法 ===

    def _init_ui(self) -> None:
        """初始化用户界面"""
        self.setWindowTitle(translate("main.title"))
        self.setWindowIcon(QIcon(resource_path("docs/images/fish-cake.ico")))
        self.resize(800, 600)

        # 创建标签页
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # 初始化各个选项卡
        self._init_tabs()

    def _init_tabs(self) -> None:
        """初始化所有选项卡"""
        # 连接设置选项卡
        self.network_tab = NetworkConfigTab(self, self.settings)
        self.tab_widget.addTab(self.network_tab, translate("main.tabs.connection"))

        # 设备控制选项卡
        self.controller_tab = ControllerSettingsTab(self, self.settings)
        self.tab_widget.addTab(self.controller_tab, translate("main.tabs.controller"))

        # 游戏联动选项卡
        self.ton_tab = TonDamageSystemTab(self, self.settings)
        self.tab_widget.addTab(self.ton_tab, translate("main.tabs.game"))

        # OSC地址管理选项卡
        self.osc_address_tab = OSCAddressTab(self, self.registries, self.options_provider)
        self.tab_widget.addTab(self.osc_address_tab, translate("main.tabs.osc_address"))

        # 波形编辑器选项卡
        self.pulse_editor_tab = PulseEditorTab(self)
        self.tab_widget.addTab(self.pulse_editor_tab, translate("main.tabs.pulse_editor"))

        # 调试选项卡
        self.log_tab = LogViewerTab(self, self.settings)
        self.tab_widget.addTab(self.log_tab, translate("main.tabs.debug"))

        # 关于选项卡
        self.about_tab = AboutTab(self, self.settings)
        self.tab_widget.addTab(self.about_tab, translate("main.tabs.about"))

    # === 配置和设置管理方法 ===

    def _load_all_settings(self) -> None:
        """从配置加载所有数据"""
        # 加载地址
        addresses = self.settings.get('addresses', [])
        self.registries.address_registry.load_from_config(addresses)

        # 加载波形
        pulses = self.settings.get('pulses', {})
        self.registries.pulse_registry.load_from_config(pulses)

        # 加载模板
        templates = self.settings.get('templates', [])
        self.registries.template_registry.load_from_config(templates)

        logger.info("All configurations loaded from settings")

    def _load_controller_settings(self) -> None:
        """从配置文件加载设备控制器设置"""
        # ChatBox状态
        enable_chatbox = self.settings.get('enable_chatbox_status', False)
        self.set_feature_state(UIFeature.CHATBOX_STATUS, enable_chatbox)
        if self.controller is not None:
            self.controller.chatbox_service.set_enabled(enable_chatbox)

        # 强度步长
        fire_mode_strength_step = self.settings.get('fire_mode_strength_step', 30)
        self.set_fire_mode_strength_step(fire_mode_strength_step)
        if self.controller is not None:
            self.controller.osc_action_service.fire_mode_strength_step = fire_mode_strength_step

        # 其他设置
        fire_mode_disabled = self.settings.get('fire_mode_disabled', False)
        enable_panel_control = self.settings.get('enable_panel_control', True)
        dynamic_bone_mode_a = self.settings.get('dynamic_bone_mode_a', False)
        dynamic_bone_mode_b = self.settings.get('dynamic_bone_mode_b', False)

        # 设置UI状态（静默方式，不触发事件）
        self.controller_tab.fire_mode_disabled_checkbox.blockSignals(True)
        self.controller_tab.fire_mode_disabled_checkbox.setChecked(fire_mode_disabled)
        self.controller_tab.fire_mode_disabled_checkbox.blockSignals(False)

        self.controller_tab.enable_panel_control_checkbox.blockSignals(True)
        self.controller_tab.enable_panel_control_checkbox.setChecked(enable_panel_control)
        self.controller_tab.enable_panel_control_checkbox.blockSignals(False)

        self.controller_tab.dynamic_bone_mode_a_checkbox.blockSignals(True)
        self.controller_tab.dynamic_bone_mode_a_checkbox.setChecked(dynamic_bone_mode_a)
        self.controller_tab.dynamic_bone_mode_a_checkbox.blockSignals(False)

        self.controller_tab.dynamic_bone_mode_b_checkbox.blockSignals(True)
        self.controller_tab.dynamic_bone_mode_b_checkbox.setChecked(dynamic_bone_mode_b)
        self.controller_tab.dynamic_bone_mode_b_checkbox.blockSignals(False)

        # 波形选择
        current_pulse_a = self.settings.get('current_pulse_a', '无波形')
        current_pulse_b = self.settings.get('current_pulse_b', '无波形')

        a_index = self.controller_tab.current_pulse_a_combobox.findText(current_pulse_a)
        b_index = self.controller_tab.current_pulse_b_combobox.findText(current_pulse_b)

        # 处理找不到的情况
        if a_index < 0:
            logger.warning(f"波形模式A '{current_pulse_a}' 未找到，使用默认值")
            a_index = 0 if self.controller_tab.current_pulse_a_combobox.count() > 0 else -1

        if b_index < 0:
            logger.warning(f"波形模式B '{current_pulse_b}' 未找到，使用默认值")
            b_index = 0 if self.controller_tab.current_pulse_b_combobox.count() > 0 else -1

        # 安全设置索引
        if a_index >= 0:
            self.controller_tab.current_pulse_a_combobox.blockSignals(True)
            self.controller_tab.current_pulse_a_combobox.setCurrentIndex(a_index)
            self.controller_tab.current_pulse_a_combobox.blockSignals(False)

        if b_index >= 0:
            self.controller_tab.current_pulse_b_combobox.blockSignals(True)
            self.controller_tab.current_pulse_b_combobox.setCurrentIndex(b_index)
            self.controller_tab.current_pulse_b_combobox.blockSignals(False)

        # 同步控制器状态
        if self.controller is not None:
            self.controller.osc_action_service.fire_mode_disabled = fire_mode_disabled
            self.controller.osc_action_service.enable_panel_control = enable_panel_control
            self.controller.osc_action_service.set_dynamic_bone_mode(Channel.A, dynamic_bone_mode_a)
            self.controller.osc_action_service.set_dynamic_bone_mode(Channel.B, dynamic_bone_mode_b)

            # 同步波形设置并更新设备
            pulse_registry = self.registries.pulse_registry
            if a_index >= 0:
                pulse_index_a = self.controller_tab.current_pulse_a_combobox.itemData(a_index)
                if pulse_index_a is not None:
                    if pulse_index_a == -1:
                        self.controller.osc_action_service.set_current_pulse(Channel.A, None)
                    elif pulse_registry.is_valid_index(pulse_index_a):
                        pulse_a = pulse_registry.get_pulse_by_index(pulse_index_a)
                        if pulse_a is not None:
                            self.controller.osc_action_service.set_current_pulse(Channel.A, pulse_a)
            if b_index >= 0:
                pulse_index_b = self.controller_tab.current_pulse_a_combobox.itemData(a_index)
                if pulse_index_b is not None:
                    if pulse_index_b == -1:
                        self.controller.osc_action_service.set_current_pulse(Channel.B, None)
                    elif pulse_registry.is_valid_index(pulse_index_b):
                        pulse_b = pulse_registry.get_pulse_by_index(pulse_index_b)
                        if pulse_b is not None:
                            self.controller.osc_action_service.set_current_pulse(Channel.B, pulse_b)

        logger.info("Controller settings loaded from configuration")

    def save_settings(self) -> None:
        """保存设置到文件"""
        save_settings(self.settings)

    # === 控制器管理方法 ===

    def set_controller(self, controller: Optional['ServiceController']) -> None:
        """设置控制器实例（当服务器启动后调用）"""
        self.controller = controller

        if controller is not None:
            # 绑定控制器设置
            self.controller_tab.bind_controller_settings()

            # 注册基础OSC动作（通道控制、面板控制、强度控制、ChatBox控制等）
            self._register_basic_actions()

            # 为控制器注册波形OSC操作
            self._register_pulse_actions()

            # 加载OSC地址绑定
            self._register_osc_bindings()

            # 从设置中加载设备控制器设置
            self._load_controller_settings()

            # 启用控制器相关UI
            self.set_controller_available(True)
        else:
            # 禁用控制器相关UI
            self.set_controller_available(False)

    def set_controller_available(self, available: bool) -> None:
        """设置控制器可用状态"""
        self.controller_tab.controller_group.setEnabled(available)

    # === OSC注册和绑定管理方法 ===

    def _register_basic_actions(self) -> None:
        """注册基础OSC动作（通道控制、面板控制、强度控制、ChatBox控制等）"""
        if self.controller is None:
            logger.warning("Controller not available, cannot register basic OSC actions")
            return

        # 清除现有动作（避免重复注册）
        self.registries.action_registry.clear_all_actions()

        osc_action_service = self.controller.osc_action_service
        chatbox_service = self.controller.chatbox_service

        # 注册通道控制操作
        async def set_float_output_channel_a(*args: OSCValue) -> None:
            if isinstance(args[0], float):
                await osc_action_service.set_float_output(args[0], Channel.A)
        self.registries.action_registry.register_action(
            "设置A通道强度",
            set_float_output_channel_a,
            OSCActionType.CHANNEL_CONTROL, {"channel_a", "touch"}
        )

        async def set_float_output_channel_b(*args: OSCValue) -> None:
            if isinstance(args[0], float):
                await osc_action_service.set_float_output(args[0], Channel.B)
        self.registries.action_registry.register_action(
            "设置B通道强度",
            set_float_output_channel_b,
            OSCActionType.CHANNEL_CONTROL, {"channel_b", "touch"}
        )

        async def set_float_output_channel_current(*args: OSCValue) -> None:
            if isinstance(args[0], float):
                current_channel = osc_action_service.get_current_channel()
                await osc_action_service.set_float_output(args[0], current_channel)
        self.registries.action_registry.register_action(
            "设置当前通道强度",
            set_float_output_channel_current,
            OSCActionType.CHANNEL_CONTROL, {"current_channel", "touch"}
        )

        # 注册面板控制操作
        async def set_panel_control(*args: OSCValue) -> None:
            if isinstance(args[0], float):
                await osc_action_service.set_panel_control(args[0])
        self.registries.action_registry.register_action(
            "面板控制开关",
            set_panel_control,
            OSCActionType.PANEL_CONTROL, {"panel"}
        )

        async def set_fire_mode_strength_step(*args: OSCValue) -> None:
            if isinstance(args[0], float):
                await osc_action_service.set_fire_mode_strength_step(args[0])
        self.registries.action_registry.register_action(
            "设置开火强度步长",
            set_fire_mode_strength_step,
            OSCActionType.PANEL_CONTROL, {"value_adjust"}
        )

        async def set_current_channel(*args: OSCValue) -> None:
            if isinstance(args[0], (int, float)):
                await osc_action_service.set_current_channel(args[0])
        self.registries.action_registry.register_action(
            "设置当前通道",
            set_current_channel,
            OSCActionType.PANEL_CONTROL, {"channel_adjust"}
        )

        # 注册强度控制操作
        async def set_dynamic_bone_mode_timer(*args: OSCValue) -> None:
            if isinstance(args[0], int):
                current_channel = osc_action_service.get_current_channel()
                await osc_action_service.set_dynamic_bone_mode_timer(args[0], current_channel)
        self.registries.action_registry.register_action(
            "设置模式",
            set_dynamic_bone_mode_timer,
            OSCActionType.STRENGTH_CONTROL, {"mode"}
        )

        async def reset_strength(*args: OSCValue) -> None:
            if isinstance(args[0], bool):
                current_channel = osc_action_service.get_current_channel()
                await osc_action_service.reset_strength(args[0], current_channel)
        self.registries.action_registry.register_action(
            "重置强度",
            reset_strength,
            OSCActionType.STRENGTH_CONTROL, {"reset"}
        )

        async def decrease_strength(*args: OSCValue) -> None:
            if isinstance(args[0], bool):
                current_channel = osc_action_service.get_current_channel()
                await osc_action_service.decrease_strength(args[0], current_channel)
        self.registries.action_registry.register_action(
            "降低强度",
            decrease_strength,
            OSCActionType.STRENGTH_CONTROL, {"decrease"}
        )

        async def increase_strength(*args: OSCValue) -> None:
            if isinstance(args[0], bool):
                current_channel = osc_action_service.get_current_channel()
                await osc_action_service.increase_strength(args[0], current_channel)
        self.registries.action_registry.register_action(
            "增加强度",
            increase_strength,
            OSCActionType.STRENGTH_CONTROL, {"increase"}
        )

        async def activate_fire_mode(*args: OSCValue) -> None:
            if isinstance(args[0], bool):
                current_channel = osc_action_service.get_current_channel()
                await osc_action_service.activate_fire_mode(args[0], current_channel)
        self.registries.action_registry.register_action(
            "一键开火",
            activate_fire_mode,
            OSCActionType.STRENGTH_CONTROL, {"fire"}
        )

        # 注册ChatBox控制操作
        async def toggle_chatbox(*args: OSCValue) -> None:
            if isinstance(args[0], int):
                await chatbox_service.toggle_chatbox(args[0])
        self.registries.action_registry.register_action(
            "ChatBox状态开关",
            toggle_chatbox,
            OSCActionType.CHATBOX_CONTROL, {"toggle"}
        )

        logger.info("基础OSC动作注册完成")

    def _register_pulse_actions(self) -> None:
        """为控制器注册波形OSC操作"""
        if self.controller is None:
            logger.warning("Controller not available, cannot register pulse actions")
            return
            
        osc_action_service = self.controller.osc_action_service

        # 为所有波形注册OSC操作
        for pulse in self.registries.pulse_registry.pulses:
            async def set_pulse(pulse: Pulse, *args: OSCValue) -> None:
                current_channel = osc_action_service.get_current_channel()
                await osc_action_service.set_pulse(current_channel, pulse)
            self.registries.action_registry.register_action(
                translate("main.action.set_pulse").format(pulse.name),
                functools.partial(set_pulse, pulse),
                OSCActionType.PULSE_CONTROL, {"pulse"})

        # 更新波形下拉框
        self.controller_tab.update_pulse_comboboxes()

    def _register_osc_bindings(self) -> None:
        """加载OSC地址绑定"""
        bindings: List[OSCBindingDict] = self.settings.get('bindings', [])

        for binding in bindings:
            address_name: Optional[str] = binding.get('address_name')
            action_name: Optional[str] = binding.get('action_name')

            if address_name and action_name:
                if address_name not in self.registries.address_registry.addresses_by_name:
                    logger.warning(f"未找到OSC地址：{address_name}")
                    continue

                if action_name not in self.registries.action_registry.actions_by_name:
                    logger.warning(f"未找到OSC操作：{action_name}")
                    continue

                address = self.registries.address_registry.get_address_by_name(address_name)
                action = self.registries.action_registry.get_action_by_name(action_name)
                if address is not None and action is not None:
                    self.registries.binding_registry.register_binding(address, action)

        self.osc_address_tab.refresh_binding_table()

        logger.info(f"Loaded {len(self.registries.binding_registry.bindings)} OSC bindings")

    # === 状态更新方法 ===

    def update_current_channel(self, channel: Channel) -> None:
        """更新当前选择通道显示"""
        self.controller_tab.update_current_channel(channel)

    def update_qrcode(self, qrcode_pixmap: QPixmap) -> None:
        """更新二维码并调整QLabel的大小"""
        self.network_tab.update_qrcode(qrcode_pixmap)

    def update_status(self, strength_data: StrengthData) -> None:
        """更新通道强度和波形"""
        self.controller_tab.update_status(strength_data)

    def update_ui_texts(self) -> None:
        """更新UI上的所有文本为当前语言"""
        self.setWindowTitle(translate("main.title"))

        # 更新标签页标题
        self.tab_widget.setTabText(0, translate("main.tabs.connection"))
        self.tab_widget.setTabText(1, translate("main.tabs.controller"))
        self.tab_widget.setTabText(2, translate("main.tabs.game"))
        self.tab_widget.setTabText(3, translate("main.tabs.osc_address"))
        self.tab_widget.setTabText(4, translate("main.tabs.pulse_editor"))
        self.tab_widget.setTabText(5, translate("main.tabs.debug"))
        self.tab_widget.setTabText(6, translate("main.tabs.about"))

        # 更新各个选项卡的文本
        self.network_tab.update_ui_texts()
        self.controller_tab.update_ui_texts()
        self.ton_tab.update_ui_texts()
        self.osc_address_tab.update_ui_texts()
        self.pulse_editor_tab.update_ui_texts()
        self.log_tab.update_ui_texts()
        self.about_tab.update_ui_texts()

    # === 连接状态管理方法 ===

    def set_connection_state(self, state: ConnectionState, message: str = "") -> None:
        """统一管理连接状态"""
        self._current_connection_state = state
        self.network_tab.update_connection_state(state, message)

    def get_connection_state(self) -> ConnectionState:
        """获取当前连接状态"""
        return self._current_connection_state

    # === 当前波形管理方法 ===

    def set_current_pulse(self, channel: Channel, pulse: Optional[Pulse]) -> None:
        """统一管理当前波形设置"""
        combo = (self.controller_tab.current_pulse_a_combobox if channel == Channel.A
                 else self.controller_tab.current_pulse_b_combobox)

        combo.blockSignals(True)

        # 根据pulse确定目标UserData值
        target_user_data = pulse.index if pulse else -1
        
        # 查找匹配UserData的项目
        found_index = -1
        for i in range(combo.count()):
            if combo.itemData(i) == target_user_data:
                found_index = i
                break
        
        if found_index >= 0:
            combo.setCurrentIndex(found_index)
        else:
            combo.setCurrentIndex(0)

        combo.blockSignals(False)

    def get_current_pulse(self, channel: Channel) -> str:
        """获取当前波形选择"""
        if channel == Channel.A:
            return self.controller_tab.current_pulse_a_combobox.currentText()
        else:
            return self.controller_tab.current_pulse_b_combobox.currentText()

    # === 功能开关管理方法 ===

    def set_feature_state(self, feature: UIFeature, enabled: bool) -> None:
        """统一管理功能开关"""
        feature_mapping = {
            UIFeature.PANEL_CONTROL: self.controller_tab.enable_panel_control_checkbox,
            UIFeature.CHATBOX_STATUS: self.controller_tab.enable_chatbox_status_checkbox,
            UIFeature.DYNAMIC_BONE_A: self.controller_tab.dynamic_bone_mode_a_checkbox,
            UIFeature.DYNAMIC_BONE_B: self.controller_tab.dynamic_bone_mode_b_checkbox,
        }

        checkbox = feature_mapping.get(feature)
        if checkbox:
            checkbox.blockSignals(True)
            checkbox.setChecked(enabled)
            checkbox.blockSignals(False)

    def get_feature_state(self, feature: UIFeature) -> bool:
        """获取功能开关状态"""
        feature_mapping = {
            UIFeature.PANEL_CONTROL: self.controller_tab.enable_panel_control_checkbox,
            UIFeature.CHATBOX_STATUS: self.controller_tab.enable_chatbox_status_checkbox,
            UIFeature.DYNAMIC_BONE_A: self.controller_tab.dynamic_bone_mode_a_checkbox,
            UIFeature.DYNAMIC_BONE_B: self.controller_tab.dynamic_bone_mode_b_checkbox,
        }

        checkbox = feature_mapping.get(feature)
        return checkbox.isChecked() if checkbox else False

    # === 强度步进管理方法 ===

    def set_fire_mode_strength_step(self, value: int) -> None:
        """统一管理强度步进设置"""
        spinbox = self.controller_tab.fire_mode_strength_step_spinbox

        spinbox.blockSignals(True)
        spinbox.setValue(value)
        spinbox.blockSignals(False)

    def get_fire_mode_strength_step(self) -> int:
        """获取强度步进值"""
        return self.controller_tab.fire_mode_strength_step_spinbox.value()

    # === 日志管理方法 ===

    def log_info(self, message: str) -> None:
        """记录信息日志"""
        self.log_tab.log_text_edit.append(f"<span>INFO: {message}</span>")

    def log_warning(self, message: str) -> None:
        """记录警告日志"""
        self.log_tab.log_text_edit.append(f"<b style='color:orange;'>WARNING: {message}</b>")

    def log_error(self, message: str) -> None:
        """记录错误日志"""
        self.log_tab.log_text_edit.append(f"<b style='color:red;'>ERROR: {message}</b>")

    def clear_logs(self) -> None:
        """清空日志"""
        self.log_tab.log_text_edit.clear()

    # === 连接状态回调方法 ===

    def on_client_connected(self) -> None:
        """客户端连接时的回调"""
        logger.info("客户端已连接")
        self.set_connection_state(ConnectionState.CONNECTED)

    def on_client_disconnected(self) -> None:
        """客户端断开连接时的回调"""
        logger.info("客户端已断开连接")
        self.set_connection_state(ConnectionState.WAITING)

    def on_client_reconnected(self) -> None:
        """客户端重新连接时的回调"""
        logger.info("客户端已重新连接")
        self.set_connection_state(ConnectionState.CONNECTED)
