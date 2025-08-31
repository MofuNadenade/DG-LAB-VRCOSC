import logging

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QTabWidget

from gui.about_tab import AboutTab
from gui.controller_settings_tab import ControllerSettingsTab
from gui.log_viewer_tab import LogViewerTab
from gui.network_config_tab import NetworkConfigTab
from gui.osc_address_tab import OSCAddressTab
from gui.pulse_editor_tab import PulseEditorTab
from gui.ton_damage_system_tab import TonDamageSystemTab
from gui.ui_interface import UIInterface
from i18n import translate, language_signals
from util import resource_path

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()

        # GUI组件类型注解
        self.tab_widget: QTabWidget
        self.network_tab: NetworkConfigTab
        self.controller_tab: ControllerSettingsTab
        self.ton_tab: TonDamageSystemTab
        self.osc_address_tab: OSCAddressTab
        self.pulse_editor_tab: PulseEditorTab
        self.log_tab: LogViewerTab
        self.about_tab: AboutTab

        self.ui_interface = ui_interface

        self._init_ui()

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
        self.network_tab = NetworkConfigTab(self.ui_interface, self.ui_interface.settings)
        self.tab_widget.addTab(self.network_tab, translate("main.tabs.connection"))

        # 设备控制选项卡
        self.controller_tab = ControllerSettingsTab(self.ui_interface, self.ui_interface.settings)
        self.tab_widget.addTab(self.controller_tab, translate("main.tabs.controller"))

        # 游戏联动选项卡
        self.ton_tab = TonDamageSystemTab(self.ui_interface, self.ui_interface.settings)
        self.tab_widget.addTab(self.ton_tab, translate("main.tabs.game"))

        # OSC地址管理选项卡
        self.osc_address_tab = OSCAddressTab(self.ui_interface, self.ui_interface.registries, self.ui_interface.options_provider)
        self.tab_widget.addTab(self.osc_address_tab, translate("main.tabs.osc_address"))

        # 波形编辑器选项卡
        self.pulse_editor_tab = PulseEditorTab(self.ui_interface)
        self.tab_widget.addTab(self.pulse_editor_tab, translate("main.tabs.pulse_editor"))

        # 调试选项卡
        self.log_tab = LogViewerTab(self.ui_interface, self.ui_interface.settings)
        self.tab_widget.addTab(self.log_tab, translate("main.tabs.debug"))

        # 关于选项卡
        self.about_tab = AboutTab(self.ui_interface, self.ui_interface.settings)
        self.tab_widget.addTab(self.about_tab, translate("main.tabs.about"))

    # === 语言切换方法 ===

    def update_ui_texts(self) -> None:
        """更新界面文本（语言切换）"""
        self.setWindowTitle(translate("main.title"))

        # 更新标签页标题
        self.tab_widget.setTabText(0, translate("main.tabs.connection"))
        self.tab_widget.setTabText(1, translate("main.tabs.controller"))
        self.tab_widget.setTabText(2, translate("main.tabs.game"))
        self.tab_widget.setTabText(3, translate("main.tabs.osc_address"))
        self.tab_widget.setTabText(4, translate("main.tabs.pulse_editor"))
        self.tab_widget.setTabText(5, translate("main.tabs.debug"))
        self.tab_widget.setTabText(6, translate("main.tabs.about"))

        # 让各个选项卡更新自己的文本
        self.network_tab.update_ui_texts()
        self.controller_tab.update_ui_texts()
        self.ton_tab.update_ui_texts()
        self.osc_address_tab.update_ui_texts()
        self.pulse_editor_tab.update_ui_texts()
        self.log_tab.update_ui_texts()
        self.about_tab.update_ui_texts()
