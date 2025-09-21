import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QGroupBox, QLabel, QHeaderView, QCheckBox, QLineEdit,
    QRadioButton, QButtonGroup
)
from PySide6.QtCore import QTimer

from core import OSCOptionsProvider
from core.registries import Registries
from gui.ui_interface import UIInterface
from i18n import translate, language_signals
from gui.styles import CommonColors
from config import save_settings
from gui.address.osc_debug_filter import OSCDebugFilter
from models import OSCDebugFilterMode

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
        self.description_label: QLabel
        self.debug_display_checkbox: QCheckBox
        self.filter_enabled_checkbox: QCheckBox
        self.filter_text_edit: QLineEdit
        self.partial_match_radio: QRadioButton
        self.regex_radio: QRadioButton
        self.case_sensitive_checkbox: QCheckBox
        self.mode_button_group: QButtonGroup
        self.apply_timer: QTimer

        # 调试过滤器
        self.debug_filter: OSCDebugFilter = OSCDebugFilter()
        
        # 在UI创建完成后加载过滤器设置
        self._load_filter_settings_pending = True

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

        # 调试选项组
        self.create_debug_options_group(layout)

        # 描述标签
        self.create_description_label(layout)

        # 操作按钮组
        self.create_action_buttons_group(layout)

    def create_description_label(self, parent_layout: QVBoxLayout) -> None:
        """创建描述标签"""
        self.description_label = QLabel(translate("tabs.osc.info_description"))
        self.description_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 11px;
                padding: 6px 8px;
                font-style: italic;
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                margin: 8px 0px;
            }
        """)
        parent_layout.addWidget(self.description_label)

    def create_address_info_group(self, parent_layout: QVBoxLayout) -> None:
        """创建地址信息组"""
        self.address_info_group = QGroupBox(translate("tabs.osc.address_info"))
        group = self.address_info_group
        layout = QVBoxLayout(group)

        # 地址信息表格
        self.address_info_table = QTableWidget()
        self.address_info_table.setColumnCount(3)
        self.address_info_table.setHorizontalHeaderLabels([
            translate("tabs.osc.osc_code"),
            translate("tabs.osc.osc_types"),
            translate("tabs.osc.last_value")
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
        self.address_info_status_label = QLabel(translate("tabs.osc.no_address_info"))
        self.address_info_status_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 12px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.address_info_status_label)

        parent_layout.addWidget(group)

    def create_debug_options_group(self, parent_layout: QVBoxLayout) -> None:
        """创建调试选项组"""
        debug_group = QGroupBox(translate("tabs.osc.debug_options"))
        debug_layout = QVBoxLayout(debug_group)
        
        # 第一行：调试显示开关和启用过滤开关
        first_row_layout = QHBoxLayout()
        
        self.debug_display_checkbox = QCheckBox(translate("tabs.osc.enable_debug_display"))
        self.debug_display_checkbox.setToolTip(translate("tabs.osc.enable_debug_display_tooltip"))
        self.debug_display_checkbox.toggled.connect(self.on_debug_display_toggled)
        self.debug_display_checkbox.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                color: #333333;
                padding: 4px;
            }
            QCheckBox:hover {
                background-color: #f0f0f0;
                border-radius: 4px;
            }
        """)
        first_row_layout.addWidget(self.debug_display_checkbox)
        
        self.filter_enabled_checkbox = QCheckBox(translate("tabs.osc.enable_filter"))
        self.filter_enabled_checkbox.toggled.connect(self.on_filter_enabled_changed)
        self.filter_enabled_checkbox.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                color: #333333;
                padding: 4px;
            }
            QCheckBox:hover {
                background-color: #f0f0f0;
                border-radius: 4px;
            }
        """)
        first_row_layout.addWidget(self.filter_enabled_checkbox)
        first_row_layout.addStretch()
        
        debug_layout.addLayout(first_row_layout)
        
        # 过滤文本输入
        filter_text_layout = QHBoxLayout()
        filter_text_layout.addWidget(QLabel(translate("tabs.osc.filter_text") + ":"))
        
        self.filter_text_edit = QLineEdit()
        self.filter_text_edit.setPlaceholderText(translate("tabs.osc.filter_placeholder"))
        self.filter_text_edit.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                border: 2px solid #ddd;
                border-radius: 4px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
        """)
        self.filter_text_edit.textChanged.connect(self.on_filter_text_changed)
        filter_text_layout.addWidget(self.filter_text_edit, 1)
        
        debug_layout.addLayout(filter_text_layout)
        
        # 过滤模式和大小写敏感选项
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel(translate("tabs.osc.filter_mode") + ":"))
        
        self.partial_match_radio = QRadioButton(translate("tabs.osc.partial_match"))
        self.regex_radio = QRadioButton(translate("tabs.osc.regex_match"))
        
        self.mode_button_group = QButtonGroup()
        self.mode_button_group.addButton(self.partial_match_radio, 0)
        self.mode_button_group.addButton(self.regex_radio, 1)
        self.mode_button_group.buttonClicked.connect(self.on_filter_mode_changed)
        
        mode_layout.addWidget(self.partial_match_radio)
        mode_layout.addWidget(self.regex_radio)
        mode_layout.addStretch()
        
        self.case_sensitive_checkbox = QCheckBox(translate("tabs.osc.case_sensitive"))
        self.case_sensitive_checkbox.toggled.connect(self.on_case_sensitive_changed)
        mode_layout.addWidget(self.case_sensitive_checkbox)
        
        debug_layout.addLayout(mode_layout)
        
        parent_layout.addWidget(debug_group)
        
        # 初始化延迟应用定时器
        self.apply_timer = QTimer()
        self.apply_timer.setSingleShot(True)
        self.apply_timer.timeout.connect(self.apply_filter_delayed)
        
        # 在UI组件创建完成后加载设置
        if self._load_filter_settings_pending:
            self.load_debug_filter_settings()
            self._load_filter_settings_pending = False

    def create_action_buttons_group(self, parent_layout: QVBoxLayout) -> None:
        """创建操作按钮组"""
        button_layout = QHBoxLayout()

        # 刷新地址信息按钮
        self.refresh_address_info_btn = QPushButton(translate("tabs.osc.refresh_address_info"))
        self.refresh_address_info_btn.clicked.connect(self.refresh_address_info_table)
        self.refresh_address_info_btn.setStyleSheet(CommonColors.get_secondary_button_style())
        self.refresh_address_info_btn.setToolTip(translate("tabs.osc.refresh_address_info_tooltip"))
        button_layout.addWidget(self.refresh_address_info_btn)

        button_layout.addStretch()  # 添加弹性空间
        parent_layout.addLayout(button_layout)

    def refresh_address_info_table(self) -> None:
        """刷新地址信息表格"""
        # 获取OSC服务检测到的地址信息
        address_infos = {}
        if self.ui_interface.service_controller:
            address_infos = self.ui_interface.service_controller.osc_service.get_address_infos()

        if not address_infos:
            self.address_info_table.setRowCount(0)
            self.address_info_status_label.setText(translate("tabs.osc.no_address_info"))
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
            last_value = info["last_value"]
            last_value_text = ", ".join([str(value.value) for value in last_value])
            last_value_item = QTableWidgetItem(last_value_text)
            self.address_info_table.setItem(row, 2, last_value_item)

        # 更新状态标签
        if len(address_infos) > 0:
            self.address_info_status_label.setText \
                (translate("tabs.osc.address_info_count").format(len(address_infos)))
        else:
            self.address_info_status_label.setText(translate("tabs.osc.no_address_info"))

    def update_ui_texts(self) -> None:
        """更新UI文本"""
        # 更新分组框标题
        self.address_info_group.setTitle(translate("tabs.osc.address_info"))
        
        # 更新描述标签
        self.description_label.setText(translate("tabs.osc.info_description"))

        # 更新表格标题
        self.address_info_table.setHorizontalHeaderLabels([
            translate("tabs.osc.osc_code"),
            translate("tabs.osc.osc_types"),
            translate("tabs.osc.last_value")
        ])

        # 更新按钮文本
        self.refresh_address_info_btn.setText(translate("tabs.osc.refresh_address_info"))

        # 更新工具提示
        self.refresh_address_info_btn.setToolTip(translate("tabs.osc.refresh_address_info_tooltip"))

        # 更新调试选项文本
        debug_group_widget = self.debug_display_checkbox.parent()
        if debug_group_widget and isinstance(debug_group_widget, QGroupBox):
            debug_group_widget.setTitle(translate("tabs.osc.debug_options"))
        self.debug_display_checkbox.setText(translate("tabs.osc.enable_debug_display"))
        self.debug_display_checkbox.setToolTip(translate("tabs.osc.enable_debug_display_tooltip"))

        # 刷新表格内容
        self.refresh_address_info_table()
        
    def on_filter_enabled_changed(self, enabled: bool) -> None:
        """过滤启用状态变化"""
        self.debug_filter.enabled = enabled
        
        # 控制其他过滤器控件的启用状态
        debug_enabled = self.debug_display_checkbox.isChecked()
        self.filter_text_edit.setEnabled(debug_enabled and enabled)
        self.partial_match_radio.setEnabled(debug_enabled and enabled)
        self.regex_radio.setEnabled(debug_enabled and enabled)
        self.case_sensitive_checkbox.setEnabled(debug_enabled and enabled)
        
        self.on_debug_filter_changed()
    
    def on_filter_text_changed(self, text: str) -> None:
        """过滤文本变化（延迟应用）"""
        self.apply_timer.start(500)  # 500ms延迟
    
    def apply_filter_delayed(self) -> None:
        """延迟应用过滤"""
        text = self.filter_text_edit.text()
        if self.debug_filter.set_filter_text(text):
            self.on_debug_filter_changed()
    
    def on_filter_mode_changed(self) -> None:
        """过滤模式变化"""
        if self.partial_match_radio.isChecked():
            mode = OSCDebugFilterMode.PARTIAL_MATCH
        elif self.regex_radio.isChecked():
            mode = OSCDebugFilterMode.REGEX
        else:
            return
        
        if self.debug_filter.set_filter_mode(mode):
            self.on_debug_filter_changed()
    
    def on_case_sensitive_changed(self, sensitive: bool) -> None:
        """大小写敏感变化"""
        self.debug_filter.set_case_sensitive(sensitive)
        self.on_debug_filter_changed()
        
    def on_debug_display_toggled(self, checked: bool) -> None:
        """OSC调试显示开关切换事件"""
        if self.ui_interface.service_controller:
            osc_service = self.ui_interface.service_controller.osc_service
            osc_service.set_debug_display_enabled(checked)
            
            # 新增：设置过滤器
            osc_service.set_debug_filter(
                self.debug_filter if checked else None
            )
            
            if checked:
                logger.info("OSC调试显示已启用")
            else:
                logger.info("OSC调试显示已禁用")
        
        # 控制过滤器UI启用状态
        self.filter_enabled_checkbox.setEnabled(checked)
        self.filter_text_edit.setEnabled(checked and self.debug_filter.enabled)
        self.partial_match_radio.setEnabled(checked and self.debug_filter.enabled)
        self.regex_radio.setEnabled(checked and self.debug_filter.enabled)
        self.case_sensitive_checkbox.setEnabled(checked and self.debug_filter.enabled)

    def on_debug_filter_changed(self) -> None:
        """调试过滤器变化事件"""
        if self.ui_interface.service_controller:
            osc_service = self.ui_interface.service_controller.osc_service
            # 通知调试显示管理器更新过滤器
            debug_display_manager = osc_service.get_debug_display_manager()
            debug_display_manager.update_filter()
        
        # 保存配置
        self.save_debug_filter_settings()
    
    def save_debug_filter_settings(self) -> None:
        """保存调试过滤器设置"""
        # 确保debug字典存在
        if 'debug' not in self.ui_interface.settings:
            self.ui_interface.settings['debug'] = {}
            
        # 直接设置每个字段避免TypedDict类型错误
        debug_settings = self.ui_interface.settings['debug']
        if 'filter' not in debug_settings:
            debug_settings['filter'] = {}
        
        filter_dict = debug_settings['filter']
        filter_dict['enabled'] = self.debug_filter.enabled
        filter_dict['filter_text'] = self.debug_filter.filter_text
        filter_dict['filter_mode'] = self.debug_filter.filter_mode.value
        filter_dict['case_sensitive'] = self.debug_filter.case_sensitive
        save_settings(self.ui_interface.settings)
    
    def load_debug_filter_settings(self) -> None:
        """加载调试过滤器设置"""
        debug_settings = self.ui_interface.settings.get('debug', {})
        filter_settings = debug_settings.get('filter', {})
        
        self.debug_filter.enabled = filter_settings.get('enabled', False)
        self.debug_filter.filter_text = filter_settings.get('filter_text', '')
        mode_str = filter_settings.get('filter_mode', 'partial')
        if mode_str == "regex":
            self.debug_filter.filter_mode = OSCDebugFilterMode.REGEX
        else:
            self.debug_filter.filter_mode = OSCDebugFilterMode.PARTIAL_MATCH
        self.debug_filter.case_sensitive = filter_settings.get('case_sensitive', False)
        
        # 更新UI（在UI组件创建后调用）
        self.update_filter_ui_from_settings()
    
    def update_filter_ui_from_settings(self) -> None:
        """从设置更新过滤器UI状态"""
        self.filter_enabled_checkbox.setChecked(self.debug_filter.enabled)
        self.filter_text_edit.setText(self.debug_filter.filter_text)
        self.case_sensitive_checkbox.setChecked(self.debug_filter.case_sensitive)
        
        # 设置模式单选按钮
        if self.debug_filter.filter_mode == OSCDebugFilterMode.PARTIAL_MATCH:
            self.partial_match_radio.setChecked(True)
        elif self.debug_filter.filter_mode == OSCDebugFilterMode.REGEX:
            self.regex_radio.setChecked(True)
        
        # 更新控件启用状态
        debug_enabled = self.debug_display_checkbox.isChecked()
        filter_enabled = self.debug_filter.enabled
        self.filter_enabled_checkbox.setEnabled(debug_enabled)
        self.filter_text_edit.setEnabled(debug_enabled and filter_enabled)
        self.partial_match_radio.setEnabled(debug_enabled and filter_enabled)
        self.regex_radio.setEnabled(debug_enabled and filter_enabled)
        self.case_sensitive_checkbox.setEnabled(debug_enabled and filter_enabled)
