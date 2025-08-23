import asyncio
import logging
from typing import Optional, Dict, List, Any, TYPE_CHECKING, Callable, Awaitable

from PySide6.QtWidgets import QMainWindow, QTabWidget
from PySide6.QtGui import QIcon, QPixmap
from pydglab_ws import StrengthData, Channel

from config import default_load_settings, save_settings
from i18n import translate as _, language_signals, set_language
from util import resource_path
from .ui_interface import ConnectionState, UIFeature
from core import OSCActionRegistry, OSCBindingRegistry, OSCAddressRegistry, OSCTemplateRegistry, OSCActionType, OSCOptionsProvider
from core.dglab_pulse import PulseRegistry

if TYPE_CHECKING:
    from core.dglab_controller import DGLabController

# Import GUI tabs
from gui.network_config_tab import NetworkConfigTab
from gui.controller_settings_tab import ControllerSettingsTab
from gui.ton_damage_system_tab import TonDamageSystemTab
from gui.log_viewer_tab import LogViewerTab
from gui.about_tab import AboutTab
from gui.osc_address_tab import OSCAddressTab
from gui.pulse_editor_tab import PulseEditorTab

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        
        # 加载设置
        self.settings: Dict[str, Any] = default_load_settings()
        
        # 设置语言
        language: str = self.settings.get('language', 'zh')
        set_language(language)
        
        # 初始化控制器相关组件
        self.controller: Optional['DGLabController'] = None
        self.pulse_registry: PulseRegistry = PulseRegistry()
        self.address_registry: OSCAddressRegistry = OSCAddressRegistry()
        self.action_registry: OSCActionRegistry = OSCActionRegistry()
        self.binding_registry: OSCBindingRegistry = OSCBindingRegistry()
        self.template_registry: OSCTemplateRegistry = OSCTemplateRegistry()
        self.options_provider: OSCOptionsProvider = OSCOptionsProvider(
            self.address_registry, self.action_registry, self.template_registry)
        
        # 从配置加载所有数据
        self.load_all_configs()
        
        # GUI组件类型注解
        self.tab_widget: QTabWidget
        self.network_tab: 'NetworkConfigTab'
        self.controller_tab: 'ControllerSettingsTab'
        self.ton_tab: 'TonDamageSystemTab'
        self.osc_address_tab: 'OSCAddressTab'
        self.pulse_editor_tab: 'PulseEditorTab'
        self.log_tab: 'LogViewerTab'
        self.about_tab: 'AboutTab'
        
        self.init_ui()
        
        # 连接状态跟踪
        self._current_connection_state: ConnectionState = ConnectionState.DISCONNECTED
        
        # 连接语言变更信号
        language_signals.language_changed.connect(self.update_ui_texts)

    def init_ui(self) -> None:
        """初始化用户界面"""
        self.setWindowTitle(_("main.title"))
        self.setWindowIcon(QIcon(resource_path("docs/images/fish-cake.ico")))
        self.resize(800, 600)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        # 初始化各个选项卡
        self.init_tabs()

    def init_tabs(self) -> None:
        """初始化所有选项卡"""
        # 连接设置选项卡
        self.network_tab = NetworkConfigTab(self, self.settings)
        self.tab_widget.addTab(self.network_tab, _("main.tabs.connection"))
        
        # 设备控制选项卡
        self.controller_tab = ControllerSettingsTab(self, self.settings)
        self.tab_widget.addTab(self.controller_tab, _("main.tabs.controller"))
        
        # 游戏联动选项卡
        self.ton_tab = TonDamageSystemTab(self, self.settings)
        self.tab_widget.addTab(self.ton_tab, _("main.tabs.game"))
        
        # OSC地址管理选项卡
        self.osc_address_tab = OSCAddressTab(self)
        self.tab_widget.addTab(self.osc_address_tab, _("main.tabs.osc_address"))
        
        # 波形编辑器选项卡
        self.pulse_editor_tab = PulseEditorTab(self)
        self.tab_widget.addTab(self.pulse_editor_tab, _("main.tabs.pulse_editor"))
        
        # 调试选项卡
        self.log_tab = LogViewerTab(self, self.settings)
        self.tab_widget.addTab(self.log_tab, _("main.tabs.debug"))
        
        # 关于选项卡
        self.about_tab = AboutTab(self, self.settings)
        self.tab_widget.addTab(self.about_tab, _("main.tabs.about"))

    def set_controller(self, controller: Optional['DGLabController']) -> None:
        """设置控制器实例（当服务器启动后调用）"""
        self.controller = controller
        
        if controller is not None:
            # 绑定控制器设置
            self.controller_tab.bind_controller_settings()
            
            # 为控制器注册脉冲OSC操作
            self.register_pulse_actions()
            
            # 注册OSC操作（现在控制器可用）
            self.register_osc_actions()
            
            # 加载OSC地址绑定（在操作注册后）
            self.load_osc_address_bindings()
            
            # 初始化OSC地址管理面板
            self.osc_address_tab.set_registries(
                self.address_registry, 
                self.action_registry, 
                self.binding_registry
            )
            # 设置下拉列表数据提供者
            self.osc_address_tab.set_options_provider(self.options_provider)
            
            # 启用控制器相关UI
            self.controller_tab.controller_group.setEnabled(True)
            
            # 从设置中加载设备控制器设置
            self.load_controller_settings()
            
            # 注意：不自动启用ton_tab的damage_group，让用户手动控制
        else:
            # 禁用控制器相关UI
            self.controller_tab.controller_group.setEnabled(False)
            # 注意：不自动禁用ton_tab的damage_group，保持用户的选择状态

    def load_all_configs(self) -> None:
        """从配置加载所有数据"""
        # 加载地址
        addresses = self.settings.get('addresses', [])
        self.address_registry.load_from_config(addresses)
        
        # 加载脉冲
        pulses = self.settings.get('pulses', {})
        self.pulse_registry.load_from_config(pulses)
        
        # 加载模板
        templates = self.settings.get('templates', [])
        self.template_registry.load_from_config(templates)
        
        logger.info("All configurations loaded from settings")
    
    def register_pulse_actions(self) -> None:
        """为控制器注册脉冲OSC操作"""
        if self.controller is None:
            logger.warning("Controller not available, cannot register pulse actions")
            return
        
        # 为所有脉冲注册OSC操作
        for pulse in self.pulse_registry.pulses:
            controller = self.controller
            pulse_index = pulse.index
            
            def make_pulse_action(idx: int, ctrl: Optional['DGLabController']) -> Callable[..., Awaitable[None]]:
                async def pulse_action(*args: Any) -> None:
                    if ctrl:
                        await ctrl.dglab_service.set_pulse_data(args[0], ctrl.dglab_service.get_current_channel(), idx)
                return pulse_action
            
            self.action_registry.register_action(_("main.action.set_pulse").format(pulse.name), 
                make_pulse_action(pulse_index, controller),
                OSCActionType.PULSE_CONTROL, {"pulse"})
        
        # 更新波形下拉框
        self.update_pulse_comboboxes()
    
    def load_controller_settings(self) -> None:
        """从配置文件加载设备控制器设置"""
        # ChatBox状态
        enable_chatbox = self.settings.get('enable_chatbox_status', False)
        self.set_feature_state(UIFeature.CHATBOX_STATUS, enable_chatbox, silent=True)
        if self.controller is not None:
            self.controller.chatbox_service.enable_chatbox_status = enable_chatbox
        
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
        if a_index >= 0:
            self.controller_tab.pulse_mode_a_combobox.blockSignals(True)
            self.controller_tab.pulse_mode_a_combobox.setCurrentIndex(a_index)
            self.controller_tab.pulse_mode_a_combobox.blockSignals(False)
        
        b_index = self.controller_tab.pulse_mode_b_combobox.findText(pulse_mode_b)
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

    def update_pulse_comboboxes(self) -> None:
        """更新控制器选项卡中的波形下拉框"""
        self.controller_tab.update_pulse_comboboxes()

    def register_osc_actions(self) -> None:
        """在控制器可用时注册OSC操作"""
        if not self.controller:
            return
            
        # 通道控制操作
        self.action_registry.register_action("A通道触碰", 
            lambda *args: self.controller.dglab_service.set_float_output(args[0], Channel.A),
            OSCActionType.CHANNEL_CONTROL, {"channel_a", "touch"})
        self.action_registry.register_action("B通道触碰", 
            lambda *args: self.controller.dglab_service.set_float_output(args[0], Channel.B),
            OSCActionType.CHANNEL_CONTROL, {"channel_b", "touch"})
        self.action_registry.register_action("当前通道触碰", 
            lambda *args: self.controller.dglab_service.set_float_output(args[0], self.controller.dglab_service.get_current_channel()),
            OSCActionType.CHANNEL_CONTROL, {"current_channel", "touch"})
        
        # 面板控制操作
        self.action_registry.register_action("面板控制", 
            lambda *args: self.controller.dglab_service.set_panel_control(args[0]),
            OSCActionType.PANEL_CONTROL, {"panel"})
        self.action_registry.register_action("数值调节", 
            lambda *args: self.controller.dglab_service.set_strength_step(args[0]),
            OSCActionType.PANEL_CONTROL, {"value_adjust"})
        self.action_registry.register_action("通道调节", 
            lambda *args: self.controller.dglab_service.set_channel(args[0]),
            OSCActionType.PANEL_CONTROL, {"channel_adjust"})
        
        # 强度控制操作
        self.action_registry.register_action("设置模式", 
            lambda *args: self.controller.dglab_service.set_mode(args[0], self.controller.dglab_service.get_current_channel()),
            OSCActionType.STRENGTH_CONTROL, {"mode"})
        self.action_registry.register_action("重置强度", 
            lambda *args: self.controller.dglab_service.reset_strength(args[0], self.controller.dglab_service.get_current_channel()),
            OSCActionType.STRENGTH_CONTROL, {"reset"})
        self.action_registry.register_action("降低强度", 
            lambda *args: self.controller.dglab_service.decrease_strength(args[0], self.controller.dglab_service.get_current_channel()),
            OSCActionType.STRENGTH_CONTROL, {"decrease"})
        self.action_registry.register_action("增加强度", 
            lambda *args: self.controller.dglab_service.increase_strength(args[0], self.controller.dglab_service.get_current_channel()),
            OSCActionType.STRENGTH_CONTROL, {"increase"})
        self.action_registry.register_action("一键开火", 
            lambda *args: self.controller.dglab_service.strength_fire_mode(args[0], self.controller.dglab_service.get_current_channel(), self.controller.dglab_service.fire_mode_strength_step, self.controller.dglab_service.get_last_strength()),
            OSCActionType.STRENGTH_CONTROL, {"fire"})
        self.action_registry.register_action("ChatBox状态开关", 
            lambda *args: self.controller.chatbox_service.toggle_chatbox(args[0]),
            OSCActionType.CHATBOX_CONTROL, {"toggle"})

    def load_osc_address_bindings(self) -> None:
        """加载OSC地址绑定"""
        bindings: List[Dict[str, str]] = self.settings.get('bindings', [])
        
        for binding in bindings:
            address_name: Optional[str] = binding.get('address_name')
            action_name: Optional[str] = binding.get('action_name')
            
            if address_name and action_name:
                if address_name not in self.address_registry.addresses_by_name:
                    logger.warning(f"未找到OSC地址：{address_name}")
                    continue
                    
                if action_name not in self.action_registry.actions_by_name:
                    logger.warning(f"未找到OSC操作：{action_name}")
                    continue
                
                address = self.address_registry.addresses_by_name[address_name]
                action = self.action_registry.actions_by_name[action_name]
                self.binding_registry.register_binding(address, action)
        
        logger.info(f"Loaded {len(self.binding_registry.bindings)} OSC bindings")

    # UIInterface interface implementation
    def update_current_channel_display(self, channel_name: str) -> None:
        """更新当前选择通道显示"""
        self.controller_tab.update_current_channel_display(channel_name)

    def update_qrcode(self, qrcode_pixmap: QPixmap) -> None:
        """更新二维码并调整QLabel的大小"""
        self.network_tab.update_qrcode(qrcode_pixmap)

    def bind_controller_settings(self) -> None:
        """将GUI设置与DGLabController变量绑定 - 这个方法在服务器启动时被调用"""
        # 这个方法现在什么都不做，因为控制器设置会在set_controller中处理
        pass

    def update_connection_status(self, is_online: bool) -> None:
        """根据设备连接状态更新标签的文本和颜色"""
        self.network_tab.update_connection_status(is_online)

    def update_status(self, strength_data: StrengthData) -> None:
        """更新通道强度和波形"""
        self.controller_tab.update_status(strength_data)

    def update_ui_texts(self) -> None:
        """更新UI上的所有文本为当前语言"""
        self.setWindowTitle(_("main.title"))
        
        # 更新标签页标题
        self.tab_widget.setTabText(0, _("main.tabs.connection"))
        self.tab_widget.setTabText(1, _("main.tabs.controller"))
        self.tab_widget.setTabText(2, _("main.tabs.game"))
        self.tab_widget.setTabText(3, _("main.tabs.osc_address"))
        self.tab_widget.setTabText(4, _("main.tabs.pulse_editor"))
        self.tab_widget.setTabText(5, _("main.tabs.debug"))
        self.tab_widget.setTabText(6, _("main.tabs.about"))
        
        # 更新各个选项卡的文本
        self.network_tab.update_ui_texts()
        self.controller_tab.update_ui_texts()
        self.ton_tab.update_ui_texts()
        self.osc_address_tab.update_ui_texts()
        self.pulse_editor_tab.update_ui_texts()
        self.log_tab.update_ui_texts()
        self.about_tab.update_ui_texts()
    
    def save_settings(self) -> None:
        """保存设置到文件"""
        save_settings(self.settings)

    # === 统一UI管理方法实现 ===
    
    def set_connection_state(self, state: ConnectionState, message: str = "") -> None:
        """统一管理连接状态"""
        self._current_connection_state = state
        button = self.network_tab.start_button
        
        state_config = {
            ConnectionState.DISCONNECTED: {
                'text': _('connection_tab.connect'),
                'style': 'background-color: green; color: white;',
                'enabled': True
            },
            ConnectionState.CONNECTING: {
                'text': _('connection_tab.cancel'),
                'style': 'background-color: orange; color: white;',
                'enabled': True
            },
            ConnectionState.WAITING: {
                'text': _('connection_tab.disconnect'),
                'style': 'background-color: blue; color: white;',
                'enabled': True
            },
            ConnectionState.CONNECTED: {
                'text': _('connection_tab.disconnect'),
                'style': 'background-color: red; color: white;',
                'enabled': True
            },
            ConnectionState.FAILED: {
                'text': message or _('connection_tab.failed'),
                'style': 'background-color: red; color: white;',
                'enabled': True
            },
            ConnectionState.ERROR: {
                'text': message or _('connection_tab.error'),
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

    def set_pulse_mode(self, channel: Channel, mode_name: str, silent: bool = False) -> None:
        """统一管理脉冲模式设置"""
        if channel == Channel.A:
            combo = self.controller_tab.pulse_mode_a_combobox
        else:
            combo = self.controller_tab.pulse_mode_b_combobox
        
        if silent:
            combo.blockSignals(True)
        
        # 查找并设置索引
        index = combo.findText(mode_name)
        if index >= 0:
            combo.setCurrentIndex(index)
        
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

    def set_controller_available(self, available: bool) -> None:
        """设置控制器可用状态"""
        self.controller_tab.controller_group.setEnabled(available)
    
    # === 连接状态通知回调实现 ===
    
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