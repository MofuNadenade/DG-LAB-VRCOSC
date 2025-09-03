import functools
import logging
from typing import Optional, List



from config import default_load_settings, save_settings
from core import ServiceController, OSCOptionsProvider, Pulse
from core.registries import Registries
from gui.main_window import MainWindow
from gui.ui_interface import UIInterface
from i18n import set_language, translate
from models import OSCBool, OSCFloat, OSCInt, SettingsDict, ConnectionState, UIFeature, Channel, OSCBindingDict, StrengthData

logger = logging.getLogger(__name__)


class UIController(UIInterface):
    """UI控制器类，实现UIInterface接口"""

    def __init__(self) -> None:
        """初始化UI控制器
        """
        super().__init__()

        self.main_window: MainWindow

        # 加载设置
        self.settings: SettingsDict = default_load_settings()

        # 设置语言
        language: str = self.settings.get('language', 'zh')
        set_language(language)

        # 初始化控制器相关组件
        self.service_controller: Optional[ServiceController] = None
        self.registries: Registries = Registries()
        self.options_provider: OSCOptionsProvider = OSCOptionsProvider(self.registries)

        # 从配置加载所有数据
        self._load_all_settings()

        # 连接状态跟踪
        self._current_connection_state: ConnectionState = ConnectionState.DISCONNECTED

    def show(self) -> None:
        self.main_window = MainWindow(self)
        self.main_window.show()

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
        enable_chatbox = self.settings.get('controller', {}).get('enable_chatbox_status', False)
        self.set_feature_state(UIFeature.CHATBOX_STATUS, enable_chatbox)
        if self.service_controller is not None:
            self.service_controller.chatbox_service.set_enabled(enable_chatbox)

        # 强度步长
        fire_mode_strength_step = self.settings.get('controller', {}).get('fire_mode_strength_step', 30)
        self.set_fire_mode_strength_step(fire_mode_strength_step)
        if self.service_controller is not None:
            self.service_controller.osc_action_service.fire_mode_strength_step = fire_mode_strength_step

        # 其他设置
        fire_mode_disabled = self.settings.get('controller', {}).get('fire_mode_disabled', False)
        enable_panel_control = self.settings.get('controller', {}).get('enable_panel_control', True)
        disable_panel_pulse_setting = self.settings.get('controller', {}).get('disable_panel_pulse_setting', False)
        dynamic_bone_mode_a = self.settings.get('controller', {}).get('dynamic_bone_mode_a', False)
        dynamic_bone_mode_b = self.settings.get('controller', {}).get('dynamic_bone_mode_b', False)

        # 设置UI状态（静默方式，不触发事件）
        self.main_window.settings_tab.fire_mode_disabled_checkbox.blockSignals(True)
        self.main_window.settings_tab.fire_mode_disabled_checkbox.setChecked(fire_mode_disabled)
        self.main_window.settings_tab.fire_mode_disabled_checkbox.blockSignals(False)

        self.main_window.settings_tab.enable_panel_control_checkbox.blockSignals(True)
        self.main_window.settings_tab.enable_panel_control_checkbox.setChecked(enable_panel_control)
        self.main_window.settings_tab.enable_panel_control_checkbox.blockSignals(False)

        self.main_window.settings_tab.disable_panel_pulse_setting_checkbox.blockSignals(True)
        self.main_window.settings_tab.disable_panel_pulse_setting_checkbox.setChecked(disable_panel_pulse_setting)
        self.main_window.settings_tab.disable_panel_pulse_setting_checkbox.blockSignals(False)

        self.main_window.settings_tab.dynamic_bone_mode_a_checkbox.blockSignals(True)
        self.main_window.settings_tab.dynamic_bone_mode_a_checkbox.setChecked(dynamic_bone_mode_a)
        self.main_window.settings_tab.dynamic_bone_mode_a_checkbox.blockSignals(False)

        self.main_window.settings_tab.dynamic_bone_mode_b_checkbox.blockSignals(True)
        self.main_window.settings_tab.dynamic_bone_mode_b_checkbox.setChecked(dynamic_bone_mode_b)
        self.main_window.settings_tab.dynamic_bone_mode_b_checkbox.blockSignals(False)

        # 动骨模式范围设置
        dynamic_bone_min_value_a = self.settings.get('controller', {}).get('dynamic_bone_min_value_a', 0)
        dynamic_bone_max_value_a = self.settings.get('controller', {}).get('dynamic_bone_max_value_a', 100)
        dynamic_bone_min_value_b = self.settings.get('controller', {}).get('dynamic_bone_min_value_b', 0)
        dynamic_bone_max_value_b = self.settings.get('controller', {}).get('dynamic_bone_max_value_b', 100)

        # 设置UI状态（静默方式，不触发事件）
        self.main_window.settings_tab.dynamic_bone_range_a_min_spinbox.blockSignals(True)
        self.main_window.settings_tab.dynamic_bone_range_a_min_spinbox.setValue(dynamic_bone_min_value_a)
        self.main_window.settings_tab.dynamic_bone_range_a_min_spinbox.blockSignals(False)

        self.main_window.settings_tab.dynamic_bone_range_a_max_spinbox.blockSignals(True)
        self.main_window.settings_tab.dynamic_bone_range_a_max_spinbox.setValue(dynamic_bone_max_value_a)
        self.main_window.settings_tab.dynamic_bone_range_a_max_spinbox.blockSignals(False)

        self.main_window.settings_tab.dynamic_bone_range_b_min_spinbox.blockSignals(True)
        self.main_window.settings_tab.dynamic_bone_range_b_min_spinbox.setValue(dynamic_bone_min_value_b)
        self.main_window.settings_tab.dynamic_bone_range_b_min_spinbox.blockSignals(False)

        self.main_window.settings_tab.dynamic_bone_range_b_max_spinbox.blockSignals(True)
        self.main_window.settings_tab.dynamic_bone_range_b_max_spinbox.setValue(dynamic_bone_max_value_b)
        self.main_window.settings_tab.dynamic_bone_range_b_max_spinbox.blockSignals(False)

        # 波形选择
        current_pulse_a = self.settings.get('controller', {}).get('current_pulse_a', '无波形')
        current_pulse_b = self.settings.get('controller', {}).get('current_pulse_b', '无波形')

        a_index = self.main_window.settings_tab.current_pulse_a_combobox.findText(current_pulse_a)
        b_index = self.main_window.settings_tab.current_pulse_b_combobox.findText(current_pulse_b)

        # 处理找不到的情况
        if a_index < 0:
            logger.warning(f"波形模式A '{current_pulse_a}' 未找到，使用默认值")
            a_index = 0 if self.main_window.settings_tab.current_pulse_a_combobox.count() > 0 else -1

        if b_index < 0:
            logger.warning(f"波形模式B '{current_pulse_b}' 未找到，使用默认值")
            b_index = 0 if self.main_window.settings_tab.current_pulse_b_combobox.count() > 0 else -1

        # 安全设置索引
        if a_index >= 0:
            self.main_window.settings_tab.current_pulse_a_combobox.blockSignals(True)
            self.main_window.settings_tab.current_pulse_a_combobox.setCurrentIndex(a_index)
            self.main_window.settings_tab.current_pulse_a_combobox.blockSignals(False)

        if b_index >= 0:
            self.main_window.settings_tab.current_pulse_b_combobox.blockSignals(True)
            self.main_window.settings_tab.current_pulse_b_combobox.setCurrentIndex(b_index)
            self.main_window.settings_tab.current_pulse_b_combobox.blockSignals(False)

        # 同步控制器状态
        if self.service_controller is not None:
            self.service_controller.osc_action_service.fire_mode_disabled = fire_mode_disabled
            self.service_controller.osc_action_service.enable_panel_control = enable_panel_control
            self.service_controller.osc_action_service.disable_panel_pulse_setting = disable_panel_pulse_setting
            self.service_controller.osc_action_service.set_dynamic_bone_mode(Channel.A, dynamic_bone_mode_a)
            self.service_controller.osc_action_service.set_dynamic_bone_mode(Channel.B, dynamic_bone_mode_b)
            
            # 同步动骨模式范围设置
            self.service_controller.osc_action_service.set_dynamic_bone_min_value(Channel.A, dynamic_bone_min_value_a)
            self.service_controller.osc_action_service.set_dynamic_bone_max_value(Channel.A, dynamic_bone_max_value_a)
            self.service_controller.osc_action_service.set_dynamic_bone_min_value(Channel.B, dynamic_bone_min_value_b)
            self.service_controller.osc_action_service.set_dynamic_bone_max_value(Channel.B, dynamic_bone_max_value_b)

            # 同步波形设置并更新设备
            pulse_registry = self.registries.pulse_registry
            if a_index >= 0:
                pulse_id_a = self.main_window.settings_tab.current_pulse_a_combobox.itemData(a_index)
                if pulse_id_a is not None:
                    if pulse_id_a == -1:
                        self.service_controller.osc_action_service.set_current_pulse(Channel.A, None)
                    elif pulse_registry.is_valid_id(pulse_id_a):
                        pulse_a = pulse_registry.get_pulse_by_id(pulse_id_a)
                        if pulse_a is not None:
                            self.service_controller.osc_action_service.set_current_pulse(Channel.A, pulse_a)
            if b_index >= 0:
                pulse_id_b = self.main_window.settings_tab.current_pulse_b_combobox.itemData(b_index)
                if pulse_id_b is not None:
                    if pulse_id_b == -1:
                        self.service_controller.osc_action_service.set_current_pulse(Channel.B, None)
                    elif pulse_registry.is_valid_id(pulse_id_b):
                        pulse_b = pulse_registry.get_pulse_by_id(pulse_id_b)
                        if pulse_b is not None:
                            self.service_controller.osc_action_service.set_current_pulse(Channel.B, pulse_b)

        logger.info("Controller settings loaded from configuration")

    def save_settings(self) -> None:
        """保存设置到文件"""
        save_settings(self.settings)

    # === 控制器管理方法 ===

    def set_service_controller(self, service_controller: Optional[ServiceController]) -> None:
        """设置控制器实例（当服务器启动后调用）"""
        self.service_controller = service_controller

        if service_controller is not None:
            # 绑定控制器设置
            self.main_window.settings_tab.bind_settings()

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
        self.main_window.settings_tab.controller_group.setEnabled(available)

    # === OSC注册和绑定管理方法 ===

    def _register_basic_actions(self) -> None:
        """注册基础OSC动作（通道控制、面板控制、强度控制、ChatBox控制等）"""
        if self.service_controller is None:
            logger.warning("Controller not available, cannot register basic OSC actions")
            return

        # 清除现有动作（避免重复注册）
        self.registries.action_registry.clear_all_actions()

        osc_action_service = self.service_controller.osc_action_service
        chatbox_service = self.service_controller.chatbox_service

        # 注册通道控制操作
        async def osc_set_strength_a(*args: OSCFloat) -> None:
            await osc_action_service.osc_set_strength(args[0].value, Channel.A)
        self.registries.action_registry.register_action("设置A通道强度", osc_set_strength_a, OSCFloat)

        async def osc_set_strength_b(*args: OSCFloat) -> None:
            await osc_action_service.osc_set_strength(args[0].value, Channel.B)
        self.registries.action_registry.register_action("设置B通道强度", osc_set_strength_b, OSCFloat)

        async def osc_set_strength_current(*args: OSCFloat) -> None:
            current_channel = osc_action_service.get_current_channel()
            await osc_action_service.osc_set_strength(args[0].value, current_channel)
        self.registries.action_registry.register_action("设置当前通道强度", osc_set_strength_current, OSCFloat)

        # 注册面板控制操作
        async def osc_set_panel_control(*args: OSCBool) -> None:
            await osc_action_service.osc_set_panel_control(args[0].value)
        self.registries.action_registry.register_action("面板控制开关", osc_set_panel_control, OSCBool)

        async def osc_set_fire_mode_strength_step(*args: OSCFloat) -> None:
            await osc_action_service.osc_set_fire_mode_strength_step(args[0].value)
        self.registries.action_registry.register_action("设置开火强度步长", osc_set_fire_mode_strength_step, OSCFloat)

        async def osc_set_current_channel(*args: OSCInt) -> None:
            await osc_action_service.osc_set_current_channel(args[0].value)
        self.registries.action_registry.register_action("设置当前通道", osc_set_current_channel, OSCInt)

        # 注册强度控制操作
        async def osc_set_dynamic_bone_mode(*args: OSCBool) -> None:
            current_channel = osc_action_service.get_current_channel()
            await osc_action_service.osc_set_dynamic_bone_mode(args[0].value, current_channel)
        self.registries.action_registry.register_action("设置模式", osc_set_dynamic_bone_mode, OSCBool)

        async def osc_reset_strength(*args: OSCBool) -> None:
            current_channel = osc_action_service.get_current_channel()
            await osc_action_service.osc_reset_strength(args[0].value, current_channel)
        self.registries.action_registry.register_action("重置强度", osc_reset_strength, OSCBool)

        async def osc_decrease_strength(*args: OSCBool) -> None:
            current_channel = osc_action_service.get_current_channel()
            await osc_action_service.osc_decrease_strength(args[0].value, current_channel)
        self.registries.action_registry.register_action("降低强度", osc_decrease_strength, OSCBool)

        async def osc_increase_strength(*args: OSCBool) -> None:
            current_channel = osc_action_service.get_current_channel()
            await osc_action_service.osc_increase_strength(args[0].value, current_channel)
        self.registries.action_registry.register_action("增加强度", osc_increase_strength, OSCBool)

        async def osc_activate_fire_mode(*args: OSCBool) -> None:
            current_channel = osc_action_service.get_current_channel()
            await osc_action_service.osc_activate_fire_mode(args[0].value, current_channel)
        self.registries.action_registry.register_action("一键开火", osc_activate_fire_mode, OSCBool)

        # 注册ChatBox控制操作
        async def osc_toggle_chatbox(*args: OSCBool) -> None:
            await chatbox_service.osc_toggle_chatbox(args[0].value)
        self.registries.action_registry.register_action("ChatBox状态开关", osc_toggle_chatbox, OSCBool)

        logger.info("基础OSC动作注册完成")

    def _register_pulse_actions(self) -> None:
        """为控制器注册波形OSC操作"""
        if self.service_controller is None:
            logger.warning("Controller not available, cannot register pulse actions")
            return

        osc_action_service = self.service_controller.osc_action_service

        # 为所有波形注册OSC操作
        for pulse in self.registries.pulse_registry.pulses:
            async def osc_set_pulse(pulse: Pulse, *args: OSCInt | OSCFloat | OSCBool) -> None:
                current_channel = osc_action_service.get_current_channel()
                await osc_action_service.osc_set_pulse(current_channel, pulse)
            self.registries.action_registry.register_action(translate("main.action.set_pulse").format(pulse.name), functools.partial(osc_set_pulse, pulse), OSCInt, OSCFloat, OSCBool)

        # 更新波形下拉框
        self.main_window.settings_tab.update_pulse_comboboxes()

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

        self.main_window.osc_tab.refresh_binding_table()

        logger.info(f"Loaded {len(self.registries.binding_registry.bindings)} OSC bindings")

    # === 状态更新方法 ===

    def on_current_channel_updated(self, channel: Channel) -> None:
        """更新当前选择通道显示"""
        self.main_window.settings_tab.on_current_channel_updated(channel)

    def on_strength_data_updated(self, strength_data: StrengthData) -> None:
        """更新通道强度和波形"""
        self.main_window.settings_tab.on_strength_data_updated(strength_data)

    # === 连接状态管理方法 ===

    def set_connection_state(self, state: ConnectionState, message: str = "") -> None:
        """统一管理连接状态"""
        self._current_connection_state = state
        self.main_window.connection_tab.update_connection_state(state, message)

    def get_connection_state(self) -> ConnectionState:
        """获取当前连接状态"""
        return self._current_connection_state

    # === 当前波形管理方法 ===

    def set_current_pulse(self, channel: Channel, pulse: Optional[Pulse]) -> None:
        """统一管理当前波形设置"""
        combo = (self.main_window.settings_tab.current_pulse_a_combobox if channel == Channel.A
                else self.main_window.settings_tab.current_pulse_b_combobox)

        combo.blockSignals(True)

        # 根据pulse确定目标UserData值
        target_user_data = pulse.id if pulse else -1

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
            return self.main_window.settings_tab.current_pulse_a_combobox.currentText()
        else:
            return self.main_window.settings_tab.current_pulse_b_combobox.currentText()

    # === 功能开关管理方法 ===

    def set_feature_state(self, feature: UIFeature, enabled: bool) -> None:
        """统一管理功能开关"""
        feature_mapping = {
            UIFeature.PANEL_CONTROL: self.main_window.settings_tab.enable_panel_control_checkbox,
            UIFeature.CHATBOX_STATUS: self.main_window.settings_tab.enable_chatbox_status_checkbox,
            UIFeature.DYNAMIC_BONE_A: self.main_window.settings_tab.dynamic_bone_mode_a_checkbox,
            UIFeature.DYNAMIC_BONE_B: self.main_window.settings_tab.dynamic_bone_mode_b_checkbox,
        }

        checkbox = feature_mapping.get(feature)
        if checkbox:
            checkbox.blockSignals(True)
            checkbox.setChecked(enabled)
            checkbox.blockSignals(False)

    def get_feature_state(self, feature: UIFeature) -> bool:
        """获取功能开关状态"""
        feature_mapping = {
            UIFeature.PANEL_CONTROL: self.main_window.settings_tab.enable_panel_control_checkbox,
            UIFeature.CHATBOX_STATUS: self.main_window.settings_tab.enable_chatbox_status_checkbox,
            UIFeature.DYNAMIC_BONE_A: self.main_window.settings_tab.dynamic_bone_mode_a_checkbox,
            UIFeature.DYNAMIC_BONE_B: self.main_window.settings_tab.dynamic_bone_mode_b_checkbox,
        }

        checkbox = feature_mapping.get(feature)
        return checkbox.isChecked() if checkbox else False

    # === 强度步进管理方法 ===

    def set_fire_mode_strength_step(self, value: int) -> None:
        """统一管理强度步进设置"""
        spinbox = self.main_window.settings_tab.fire_mode_strength_step_spinbox

        spinbox.blockSignals(True)
        spinbox.setValue(value)
        spinbox.blockSignals(False)

    def get_fire_mode_strength_step(self) -> int:
        """获取强度步进值"""
        return self.main_window.settings_tab.fire_mode_strength_step_spinbox.value()

    # === 日志管理方法 ===

    def log_info(self, message: str) -> None:
        """记录信息日志"""
        self.main_window.debug_tab.log_text_edit.append(f"<span>INFO: {message}</span>")

    def log_warning(self, message: str) -> None:
        """记录警告日志"""
        self.main_window.debug_tab.log_text_edit.append(f"<b style='color:orange;'>WARNING: {message}</b>")

    def log_error(self, message: str) -> None:
        """记录错误日志"""
        self.main_window.debug_tab.log_text_edit.append(f"<b style='color:red;'>ERROR: {message}</b>")

    def clear_logs(self) -> None:
        """清空日志"""
        self.main_window.debug_tab.log_text_edit.clear()

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
