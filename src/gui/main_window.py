import asyncio
import logging
from typing import Optional, List, Callable, Awaitable

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QMainWindow, QTabWidget

from config import default_load_settings, save_settings
from core import OSCActionType, OSCOptionsProvider
from core.dglab_controller import DGLabController
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
        self.controller: Optional[DGLabController] = None
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

        # 加载脉冲
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
        self.set_feature_state(UIFeature.CHATBOX_STATUS, enable_chatbox, silent=True)
        if self.controller is not None:
            self.controller.chatbox_service.set_enabled(enable_chatbox)

        # 强度步长
        strength_step = self.settings.get('strength_step', 30)
        self.set_strength_step(strength_step, silent=True)
        if self.controller is not None:
            self.controller.dglab_service.fire_mode_strength_step = strength_step

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
        pulse_mode_a = self.settings.get('pulse_mode_a', '连击')
        pulse_mode_b = self.settings.get('pulse_mode_b', '连击')

        a_index = self.controller_tab.pulse_mode_a_combobox.findText(pulse_mode_a)
        b_index = self.controller_tab.pulse_mode_b_combobox.findText(pulse_mode_b)

        # 处理找不到的情况
        if a_index < 0:
            logger.warning(f"波形模式A '{pulse_mode_a}' 未找到，使用默认值")
            a_index = 0 if self.controller_tab.pulse_mode_a_combobox.count() > 0 else -1

        if b_index < 0:
            logger.warning(f"波形模式B '{pulse_mode_b}' 未找到，使用默认值")
            b_index = 0 if self.controller_tab.pulse_mode_b_combobox.count() > 0 else -1

        # 安全设置索引
        if a_index >= 0:
            self.controller_tab.pulse_mode_a_combobox.blockSignals(True)
            self.controller_tab.pulse_mode_a_combobox.setCurrentIndex(a_index)
            self.controller_tab.pulse_mode_a_combobox.blockSignals(False)

        if b_index >= 0:
            self.controller_tab.pulse_mode_b_combobox.blockSignals(True)
            self.controller_tab.pulse_mode_b_combobox.setCurrentIndex(b_index)
            self.controller_tab.pulse_mode_b_combobox.blockSignals(False)

        # 同步控制器状态
        if self.controller is not None:
            self.controller.dglab_service.fire_mode_disabled = fire_mode_disabled
            self.controller.dglab_service.enable_panel_control = enable_panel_control
            self.controller.dglab_service.set_dynamic_bone_mode(Channel.A, dynamic_bone_mode_a)
            self.controller.dglab_service.set_dynamic_bone_mode(Channel.B, dynamic_bone_mode_b)

            # 同步波形设置并更新设备
            if a_index >= 0:
                self.controller.dglab_service.set_pulse_mode(Channel.A, a_index)
            if b_index >= 0:
                self.controller.dglab_service.set_pulse_mode(Channel.B, b_index)

            # 立即更新设备上的波形数据
            asyncio.create_task(self.controller.dglab_service.update_pulse_data())

        logger.info("Controller settings loaded from configuration")

    def save_settings(self) -> None:
        """保存设置到文件"""
        save_settings(self.settings)

    # === 控制器管理方法 ===

    def set_controller(self, controller: Optional['DGLabController']) -> None:
        """设置控制器实例（当服务器启动后调用）"""
        self.controller = controller

        if controller is not None:
            # 绑定控制器设置
            self.controller_tab.bind_controller_settings()

            # 注册基础OSC动作（通道控制、面板控制、强度控制、ChatBox控制等）
            self._register_basic_actions()

            # 为控制器注册脉冲OSC操作
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

        dglab_service = self.controller.dglab_service
        chatbox_service = self.controller.chatbox_service

        # 注册通道控制操作
        self.registries.action_registry.register_action(
            "A通道触碰",
            self._create_async_wrapper(lambda *args: dglab_service.set_float_output(args[0], Channel.A)),
            OSCActionType.CHANNEL_CONTROL, {"channel_a", "touch"}
        )

        self.registries.action_registry.register_action(
            "B通道触碰",
            self._create_async_wrapper(lambda *args: dglab_service.set_float_output(args[0], Channel.B)),
            OSCActionType.CHANNEL_CONTROL, {"channel_b", "touch"}
        )

        self.registries.action_registry.register_action(
            "当前通道触碰",
            self._create_async_wrapper(lambda *args: dglab_service.set_float_output(
                args[0], dglab_service.get_current_channel()
            )),
            OSCActionType.CHANNEL_CONTROL, {"current_channel", "touch"}
        )

        # 注册面板控制操作
        self.registries.action_registry.register_action(
            "面板控制",
            self._create_async_wrapper(lambda *args: dglab_service.set_panel_control(args[0])),
            OSCActionType.PANEL_CONTROL, {"panel"}
        )

        self.registries.action_registry.register_action(
            "数值调节",
            self._create_async_wrapper(lambda *args: dglab_service.set_strength_step(args[0])),
            OSCActionType.PANEL_CONTROL, {"value_adjust"}
        )

        async def set_channel_wrapper(*args: OSCValue) -> None:
            if isinstance(args[0], (int, float)):
                await dglab_service.set_channel(args[0])

        self.registries.action_registry.register_action(
            "通道调节",
            set_channel_wrapper,
            OSCActionType.PANEL_CONTROL, {"channel_adjust"}
        )

        # 注册强度控制操作
        self.registries.action_registry.register_action(
            "设置模式",
            self._create_async_wrapper(lambda *args: dglab_service.set_mode(
                args[0], dglab_service.get_current_channel()
            )),
            OSCActionType.STRENGTH_CONTROL, {"mode"}
        )

        self.registries.action_registry.register_action(
            "重置强度",
            self._create_async_wrapper(lambda *args: dglab_service.reset_strength(
                args[0], dglab_service.get_current_channel()
            )),
            OSCActionType.STRENGTH_CONTROL, {"reset"}
        )

        self.registries.action_registry.register_action(
            "降低强度",
            self._create_async_wrapper(lambda *args: dglab_service.decrease_strength(
                args[0], dglab_service.get_current_channel()
            )),
            OSCActionType.STRENGTH_CONTROL, {"decrease"}
        )

        self.registries.action_registry.register_action(
            "增加强度",
            self._create_async_wrapper(lambda *args: dglab_service.increase_strength(
                args[0], dglab_service.get_current_channel()
            )),
            OSCActionType.STRENGTH_CONTROL, {"increase"}
        )

        self.registries.action_registry.register_action(
            "一键开火",
            self._create_async_wrapper(lambda *args: dglab_service.strength_fire_mode(
                args[0],
                dglab_service.get_current_channel(),
                dglab_service.fire_mode_strength_step,
                dglab_service.get_last_strength()
            )),
            OSCActionType.STRENGTH_CONTROL, {"fire"}
        )

        # 注册ChatBox控制操作
        self.registries.action_registry.register_action(
            "ChatBox状态开关",
            self._create_async_wrapper(lambda *args: chatbox_service.toggle_chatbox(args[0])),
            OSCActionType.CHATBOX_CONTROL, {"toggle"}
        )

        logger.info("基础OSC动作注册完成")

    def _create_async_wrapper(self, func: Callable[..., Awaitable[None]]) -> Callable[..., Awaitable[None]]:
        """创建异步包装器"""
        async def wrapper(*args: OSCValue) -> None:
            try:
                await func(*args)
            except Exception as e:
                logger.error(f"OSC动作执行失败: {e}")

        return wrapper

    def _register_pulse_actions(self) -> None:
        """为控制器注册脉冲OSC操作"""
        if self.controller is None:
            logger.warning("Controller not available, cannot register pulse actions")
            return

        # 为所有脉冲注册OSC操作
        for pulse in self.registries.pulse_registry.pulses:
            controller = self.controller
            pulse_index = pulse.index

            def make_pulse_action(idx: int, ctrl: Optional['DGLabController']) -> Callable[..., Awaitable[None]]:
                async def pulse_action(*args: OSCValue) -> None:
                    if ctrl and isinstance(args[0], bool):
                        await ctrl.dglab_service.set_pulse_data(args[0], ctrl.dglab_service.get_current_channel(), idx)

                return pulse_action

            self.registries.action_registry.register_action(translate("main.action.set_pulse").format(pulse.name),
                                                            make_pulse_action(pulse_index, controller),
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

                address = self.registries.address_registry.addresses_by_name[address_name]
                action = self.registries.action_registry.actions_by_name[action_name]
                self.registries.binding_registry.register_binding(address, action)

        self.osc_address_tab.refresh_binding_table()

        logger.info(f"Loaded {len(self.registries.binding_registry.bindings)} OSC bindings")

    # === 状态更新方法 ===

    def update_current_channel_display(self, channel_name: str) -> None:
        """更新当前选择通道显示"""
        self.controller_tab.update_current_channel_display(channel_name)

    def update_qrcode(self, qrcode_pixmap: QPixmap) -> None:
        """更新二维码并调整QLabel的大小"""
        self.network_tab.update_qrcode(qrcode_pixmap)

    def update_connection_status(self, is_online: bool) -> None:
        """根据设备连接状态更新标签的文本和颜色"""
        self.network_tab.update_connection_status(is_online)

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
        button = self.network_tab.start_button

        state_config = {
            ConnectionState.DISCONNECTED: {
                'text': translate('connection_tab.connect'),
                'style': 'background-color: green; color: white;',
                'enabled': True
            },
            ConnectionState.CONNECTING: {
                'text': translate('connection_tab.cancel'),
                'style': 'background-color: orange; color: white;',
                'enabled': True
            },
            ConnectionState.WAITING: {
                'text': translate('connection_tab.disconnect'),
                'style': 'background-color: blue; color: white;',
                'enabled': True
            },
            ConnectionState.CONNECTED: {
                'text': translate('connection_tab.disconnect'),
                'style': 'background-color: red; color: white;',
                'enabled': True
            },
            ConnectionState.FAILED: {
                'text': message or translate('connection_tab.failed'),
                'style': 'background-color: red; color: white;',
                'enabled': True
            },
            ConnectionState.ERROR: {
                'text': message or translate('connection_tab.error'),
                'style': 'background-color: darkred; color: white;',
                'enabled': True
            }
        }

        config = state_config[state]
        button.setText(str(config['text']))
        button.setStyleSheet(str(config['style']))
        button.setEnabled(bool(config['enabled']))

        # 记录错误日志
        if state in [ConnectionState.FAILED, ConnectionState.ERROR] and message:
            self.log_error(message)

    def get_connection_state(self) -> ConnectionState:
        """获取当前连接状态"""
        return self._current_connection_state

    # === 脉冲模式管理方法 ===

    def set_pulse_mode(self, channel: Channel, mode_name: str, silent: bool = False) -> None:
        """统一管理脉冲模式设置"""
        combo = (self.controller_tab.pulse_mode_a_combobox if channel == Channel.A
                 else self.controller_tab.pulse_mode_b_combobox)

        if silent:
            combo.blockSignals(True)

        # 查找并设置索引
        index = combo.findText(mode_name)
        if index >= 0:
            combo.setCurrentIndex(index)
        elif combo.count() > 0:
            # 如果找不到，设置为第一项
            logger.warning(f"波形模式 '{mode_name}' 未找到，使用第一个可用选项")
            combo.setCurrentIndex(0)
        else:
            logger.error("组合框中没有可用的波形模式")

        if silent:
            combo.blockSignals(False)

    def get_pulse_mode(self, channel: Channel) -> str:
        """获取脉冲模式选择"""
        if channel == Channel.A:
            return self.controller_tab.pulse_mode_a_combobox.currentText()
        else:
            return self.controller_tab.pulse_mode_b_combobox.currentText()

    def update_pulse_modes_list(self, pulse_names: list[str]) -> None:
        """更新脉冲模式列表"""
        self.controller_tab.pulse_mode_a_combobox.clear()
        self.controller_tab.pulse_mode_b_combobox.clear()

        for pulse_name in pulse_names:
            self.controller_tab.pulse_mode_a_combobox.addItem(pulse_name)
            self.controller_tab.pulse_mode_b_combobox.addItem(pulse_name)

    # === 功能开关管理方法 ===

    def set_feature_state(self, feature: UIFeature, enabled: bool, silent: bool = False) -> None:
        """统一管理功能开关"""
        feature_mapping = {
            UIFeature.PANEL_CONTROL: self.controller_tab.enable_panel_control_checkbox,
            UIFeature.CHATBOX_STATUS: self.controller_tab.enable_chatbox_status_checkbox,
            UIFeature.DYNAMIC_BONE_A: self.controller_tab.dynamic_bone_mode_a_checkbox,
            UIFeature.DYNAMIC_BONE_B: self.controller_tab.dynamic_bone_mode_b_checkbox,
        }

        checkbox = feature_mapping.get(feature)
        if checkbox:
            if silent:
                checkbox.blockSignals(True)
            checkbox.setChecked(enabled)
            if silent:
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

    def set_strength_step(self, value: int, silent: bool = False) -> None:
        """统一管理强度步进设置"""
        spinbox = self.controller_tab.strength_step_spinbox

        if silent:
            spinbox.blockSignals(True)
        spinbox.setValue(value)
        if silent:
            spinbox.blockSignals(False)

    def get_strength_step(self) -> int:
        """获取强度步进值"""
        return self.controller_tab.strength_step_spinbox.value()

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
        self.update_connection_status(True)

    def on_client_disconnected(self) -> None:
        """客户端断开连接时的回调"""
        logger.info("客户端已断开连接")
        self.set_connection_state(ConnectionState.WAITING)  # 等待重新连接
        self.update_connection_status(False)

    def on_client_reconnected(self) -> None:
        """客户端重新连接时的回调"""
        logger.info("客户端已重新连接")
        self.set_connection_state(ConnectionState.CONNECTED)
        self.update_connection_status(True)
