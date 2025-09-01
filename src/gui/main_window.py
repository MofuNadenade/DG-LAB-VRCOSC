import logging

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QTabWidget

from gui.about.about_tab import AboutTab
from gui.settings.settings_tab import SettingsTab
from gui.debug.debug_tab import DebugTab
from gui.connection.connection_tab import ConnectionTab
from gui.osc.osc_tab import OSCTab
from gui.pulse.pulse_tab import PulseTab
from gui.ton.ton_tab import TonTab
from gui.ui_interface import UIInterface
from i18n import translate, language_signals
from util import resource_path

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()

        # GUI组件类型注解
        self.tab_widget: QTabWidget
        self.connection_tab: ConnectionTab
        self.settings_tab: SettingsTab
        self.ton_tab: TonTab
        self.osc_tab: OSCTab
        self.pulse_tab: PulseTab
        self.debug_tab: DebugTab
        self.about_tab: AboutTab

        self.ui_interface = ui_interface

        self._init_ui()

        # 连接语言变更信号
        language_signals.language_changed.connect(self.update_ui_texts)

    # === 用户界面初始化方法 ===

    def _init_ui(self) -> None:
        """初始化用户界面"""
        self.setWindowTitle(translate("main.title"))
        self.setWindowIcon(QIcon(resource_path("icon/fish-cake.ico")))
        self.resize(800, 600)

        # 创建标签页
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # 初始化各个选项卡
        self._init_tabs()

    def _init_tabs(self) -> None:
        """初始化所有选项卡"""
        # 连接设置选项卡
        self.connection_tab = ConnectionTab(self.ui_interface)
        self.tab_widget.addTab(self.connection_tab, translate("main.tabs.connection"))

        # 设备控制选项卡
        self.settings_tab = SettingsTab(self.ui_interface)
        self.tab_widget.addTab(self.settings_tab, translate("main.tabs.settings"))

        # 游戏联动选项卡
        self.ton_tab = TonTab(self.ui_interface)
        self.tab_widget.addTab(self.ton_tab, translate("main.tabs.ton"))

        # OSC地址管理选项卡
        self.osc_tab = OSCTab(self.ui_interface)
        self.tab_widget.addTab(self.osc_tab, translate("main.tabs.osc"))

        # 波形编辑器选项卡
        self.pulse_tab = PulseTab(self.ui_interface)
        self.tab_widget.addTab(self.pulse_tab, translate("main.tabs.pulse"))

        # 调试选项卡
        self.debug_tab = DebugTab(self.ui_interface)
        self.tab_widget.addTab(self.debug_tab, translate("main.tabs.debug"))

        # 关于选项卡
        self.about_tab = AboutTab(self.ui_interface)
        self.tab_widget.addTab(self.about_tab, translate("main.tabs.about"))

    # === 语言切换方法 ===

    def update_ui_texts(self) -> None:
        """更新界面文本（语言切换）"""
        self.setWindowTitle(translate("main.title"))

        # 更新标签页标题
        self.tab_widget.setTabText(0, translate("main.tabs.connection"))
        self.tab_widget.setTabText(1, translate("main.tabs.settings"))
        self.tab_widget.setTabText(2, translate("main.tabs.ton"))
        self.tab_widget.setTabText(3, translate("main.tabs.osc"))
        self.tab_widget.setTabText(4, translate("main.tabs.pulse"))
        self.tab_widget.setTabText(5, translate("main.tabs.debug"))
        self.tab_widget.setTabText(6, translate("main.tabs.about"))

        # 让各个选项卡更新自己的文本
        self.connection_tab.update_ui_texts()
        self.settings_tab.update_ui_texts()
        self.ton_tab.update_ui_texts()
        self.osc_tab.update_ui_texts()
        self.pulse_tab.update_ui_texts()
        self.debug_tab.update_ui_texts()
        self.about_tab.update_ui_texts()
