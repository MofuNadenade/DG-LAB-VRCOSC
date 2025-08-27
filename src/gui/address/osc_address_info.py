import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QGroupBox, QLabel, QHeaderView
)

from core import OSCOptionsProvider
from core.registries import Registries
from gui.ui_interface import UIInterface
from i18n import translate, language_signals

logger = logging.getLogger(__name__)


class OSCAddressInfoTab(QWidget):
    """OSC地址信息标签页"""

    def __init__(self, ui_interface: UIInterface, registries: Registries, options_provider: OSCOptionsProvider) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.registries: Registries = registries
        self.options_provider: OSCOptionsProvider = options_provider

        # UI组件类型注解
        self.address_info_table: QTableWidget
        self.refresh_address_info_btn: QPushButton
        self.address_info_status_label: QLabel
        self.address_info_group: QGroupBox

        self.init_ui()

        # 初始化表格数据
        self.refresh_address_info_table()

        # 连接语言切换信号
        language_signals.language_changed.connect(self.update_ui_texts)

    def init_ui(self) -> None:
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 地址信息组
        self.create_address_info_group(layout)

        # 操作按钮组
        self.create_action_buttons_group(layout)

    def create_address_info_group(self, parent_layout: QVBoxLayout) -> None:
        """创建地址信息组"""
        self.address_info_group = QGroupBox(translate("osc_address_tab.address_info"))
        group = self.address_info_group
        layout = QVBoxLayout(group)

        # 地址信息表格
        self.address_info_table = QTableWidget()
        self.address_info_table.setColumnCount(3)
        self.address_info_table.setHorizontalHeaderLabels([
            translate("osc_address_tab.osc_code"),
            translate("osc_address_tab.osc_types"),
            translate("osc_address_tab.last_value")
        ])

        # 设置表格属性
        header = self.address_info_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # OSC地址列拉伸
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # 检测类型列拉伸
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # 最后值列拉伸

        self.address_info_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.address_info_table.setAlternatingRowColors(True)
        self.address_info_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
            }
            QTableWidget::item:selected {
                background-color: #e6f3ff;
                color: black;
            }
            QTableWidget::item:hover {
                background-color: #f0f8ff;
            }
        """)

        layout.addWidget(self.address_info_table)

        # 地址信息状态标签
        self.address_info_status_label = QLabel(translate("osc_address_tab.no_address_info"))
        self.address_info_status_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 12px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.address_info_status_label)

        parent_layout.addWidget(group)

    def create_action_buttons_group(self, parent_layout: QVBoxLayout) -> None:
        """创建操作按钮组"""
        button_layout = QHBoxLayout()

        # 刷新地址信息按钮
        self.refresh_address_info_btn = QPushButton(translate("osc_address_tab.refresh_address_info"))
        self.refresh_address_info_btn.clicked.connect(self.refresh_address_info_table)
        self.refresh_address_info_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        self.refresh_address_info_btn.setToolTip(translate("osc_address_tab.refresh_address_info_tooltip"))
        button_layout.addWidget(self.refresh_address_info_btn)

        button_layout.addStretch()  # 添加弹性空间
        parent_layout.addLayout(button_layout)

    def refresh_address_info_table(self) -> None:
        """刷新地址信息表格"""
        # 获取OSC服务检测到的地址信息
        address_infos = {}
        if self.ui_interface.controller:
            address_infos = self.ui_interface.controller.osc_service.get_address_infos()

        if not address_infos:
            self.address_info_table.setRowCount(0)
            self.address_info_status_label.setText(translate("osc_address_tab.no_address_info"))
            return

        # 对检测到的地址按地址排序
        sorted_address_infos = sorted(address_infos.items(), key=lambda x: x[0])

        # 设置表格行数
        self.address_info_table.setRowCount(len(sorted_address_infos))

        for row, (address, info) in enumerate(sorted_address_infos):
            # OSC地址
            address_item = QTableWidgetItem(address)
            self.address_info_table.setItem(row, 0, address_item)

            # 检测到的类型
            types_text = ", ".join(sorted([t.value for t in info["types"]]))
            types_item = QTableWidgetItem(types_text)
            self.address_info_table.setItem(row, 1, types_item)

            # 最后值
            last_value = info.get("last_value", "")
            last_value_text = str(last_value) if last_value is not None else ""
            last_value_item = QTableWidgetItem(last_value_text)
            self.address_info_table.setItem(row, 2, last_value_item)

        # 更新状态标签
        if len(address_infos) > 0:
            self.address_info_status_label.setText \
                (translate("osc_address_tab.address_info_count").format(len(address_infos)))
        else:
            self.address_info_status_label.setText(translate("osc_address_tab.no_address_info"))

    def update_ui_texts(self) -> None:
        """更新UI文本"""
        # 更新分组框标题
        self.address_info_group.setTitle(translate("osc_address_tab.address_info"))

        # 更新表格标题
        self.address_info_table.setHorizontalHeaderLabels([
            translate("osc_address_tab.osc_code"),
            translate("osc_address_tab.osc_types"),
            translate("osc_address_tab.last_value")
        ])

        # 更新按钮文本
        self.refresh_address_info_btn.setText(translate("osc_address_tab.refresh_address_info"))

        # 更新工具提示
        self.refresh_address_info_btn.setToolTip(translate("osc_address_tab.refresh_address_info_tooltip"))

        # 刷新表格内容
        self.refresh_address_info_table()
