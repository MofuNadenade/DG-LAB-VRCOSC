import logging

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget

from core import OSCOptionsProvider
from core.registries import Registries
from i18n import translate, language_signals
from gui.address.osc_address_info import OSCAddressInfoTab
from gui.address.osc_address_table import OSCAddressTableTab
from gui.address.osc_binding_table import OSCBindingTableTab
from gui.ui_interface import UIInterface

logger = logging.getLogger(__name__)


class OSCTab(QWidget):
    """OSC地址管理面板 - 包含地址列表、绑定管理和检测类型的标签页"""

    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.registries: Registries = ui_interface.registries
        self.options_provider: OSCOptionsProvider = ui_interface.options_provider

        # UI组件类型注解
        self.tab_widget: QTabWidget
        self.binding_table_tab: OSCBindingTableTab
        self.address_table_tab: OSCAddressTableTab
        self.address_info_tab: OSCAddressInfoTab

        self.init_ui()

        # 连接语言切换信号
        language_signals.language_changed.connect(self.update_ui_texts)

    def init_ui(self) -> None:
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 创建内部标签页
        self.tab_widget = QTabWidget()

        # 绑定列表标签页
        self.binding_table_tab = OSCBindingTableTab(self.ui_interface, self.registries, self.options_provider)
        self.tab_widget.addTab(self.binding_table_tab, translate("tabs.osc.binding_list"))

        # 地址列表标签页
        self.address_table_tab = OSCAddressTableTab(self.ui_interface, self.registries, self.options_provider)
        self.tab_widget.addTab(self.address_table_tab, translate("tabs.osc.address_list"))

        # 地址信息标签页
        self.address_info_tab = OSCAddressInfoTab(self.ui_interface, self.registries, self.options_provider)
        self.tab_widget.addTab(self.address_info_tab, translate("tabs.osc.address_info"))

        layout.addWidget(self.tab_widget)

    def refresh_address_table(self) -> None:
        """刷新地址表格"""
        self.address_table_tab.refresh_address_table()

    def refresh_binding_table(self) -> None:
        """刷新绑定表格"""
        self.binding_table_tab.refresh_binding_table()

    def refresh_address_info_table(self) -> None:
        """刷新地址信息表格"""
        self.address_info_tab.refresh_address_info_table()

    def update_ui_texts(self) -> None:
        """更新UI文本"""
        # 更新内部标签页标题
        self.tab_widget.setTabText(0, translate("tabs.osc.binding_list"))
        self.tab_widget.setTabText(1, translate("tabs.osc.address_list"))
        self.tab_widget.setTabText(2, translate("tabs.osc.address_info"))

        # 更新子标签页的文本
        self.address_table_tab.update_ui_texts()
        self.binding_table_tab.update_ui_texts()
        self.address_info_tab.update_ui_texts()
