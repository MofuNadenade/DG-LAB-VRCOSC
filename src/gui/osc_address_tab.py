import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QGroupBox, QFormLayout, QLabel,
    QHeaderView, QMessageBox, QDialog, QDialogButtonBox, QTabWidget, QComboBox
)

from core import OSCOptionsProvider
from core.osc_common import OSCAction, OSCAddress
from core.registries import Registries
from i18n import translate, language_signals
from .ui_interface import UIInterface
from .widgets import OSCTableDelegate, OSCBindingTableDelegate, EditableComboBox

logger = logging.getLogger(__name__)


class AddBindingDialog(QDialog):
    """添加OSC地址绑定的对话框"""
    
    def __init__(self, parent: Optional[QWidget], registries: Registries) -> None:
        super().__init__(parent)
        self.registries = registries
        
        # UI组件类型注解
        self.address_combo: QComboBox
        self.action_combo: QComboBox
        
        self.setWindowTitle(translate("osc_address_tab.add_binding"))
        self.setModal(True)
        self.resize(450, 200)
        
        # 设置对话框样式
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                font-weight: bold;
                color: #333;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # 表单布局
        form_layout = QFormLayout()
        
        # 地址选择
        address_options = [addr.name for addr in self.registries.address_registry.addresses]
        self.address_combo = EditableComboBox(address_options, allow_manual_input = False)
        form_layout.addRow(translate("osc_address_tab.address_name_label"), self.address_combo)
        
        # 动作选择
        action_options = [action.name for action in self.registries.action_registry.actions]
        self.action_combo = EditableComboBox(action_options, allow_manual_input = False)
        form_layout.addRow(translate("osc_address_tab.action_name_label"), self.action_combo)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # 连接语言切换信号
        language_signals.language_changed.connect(self.update_ui_texts)
    
    def update_ui_texts(self) -> None:
        """更新UI文本"""
        self.setWindowTitle(translate("osc_address_tab.add_binding"))
    
    def get_binding_data(self) -> tuple[str, str]:
        """获取选中的绑定数据"""
        return self.address_combo.currentText(), self.action_combo.currentText()
    
    def validate_input(self) -> bool:
        """验证输入"""
        address_name, action_name = self.get_binding_data()
        if not address_name or not action_name:
            QMessageBox.warning(self, translate("osc_address_tab.input_error"), 
                              translate("osc_address_tab.select_address_action"))
            return False
        return True


class AddAddressDialog(QDialog):
    """添加OSC地址的对话框"""
    
    def __init__(self, options_provider: OSCOptionsProvider, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.options_provider = options_provider
        
        # UI组件类型注解
        self.name_combo: EditableComboBox
        self.code_combo: EditableComboBox
        
        self.setWindowTitle(translate("osc_address_tab.add_address"))
        self.setModal(True)
        self.resize(450, 250)
        
        # 设置对话框样式
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                font-weight: bold;
                color: #333;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # 表单布局
        form_layout = QFormLayout()
        
        # 地址名称 - 可编辑下拉列表
        address_name_options = self.options_provider.get_address_name_options()
        self.name_combo = EditableComboBox(address_name_options)
        self.name_combo.setCurrentText("")  # 默认为空，让用户输入
        name_line_edit = self.name_combo.lineEdit()
        if name_line_edit:
            name_line_edit.setPlaceholderText(translate("osc_address_tab.address_name_placeholder"))
        form_layout.addRow(translate("osc_address_tab.address_name_label"), self.name_combo)
        
        # OSC地址/代码 - 可编辑下拉列表
        osc_code_options = self.options_provider.get_osc_code_options()
        self.code_combo = EditableComboBox(osc_code_options)
        self.code_combo.setCurrentText("")  # 默认为空，让用户输入
        code_line_edit = self.code_combo.lineEdit()
        if code_line_edit:
            code_line_edit.setPlaceholderText(translate("osc_address_tab.osc_code_placeholder"))
        form_layout.addRow(translate("osc_address_tab.osc_code_label"), self.code_combo)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # 连接语言切换信号
        language_signals.language_changed.connect(self.update_ui_texts)
    
    def update_ui_texts(self) -> None:
        """更新UI文本"""
        self.setWindowTitle(translate("osc_address_tab.add_address"))
        name_line_edit = self.name_combo.lineEdit()
        if name_line_edit:
            name_line_edit.setPlaceholderText(translate("osc_address_tab.address_name_placeholder"))
        code_line_edit = self.code_combo.lineEdit()
        if code_line_edit:
            code_line_edit.setPlaceholderText(translate("osc_address_tab.osc_code_placeholder"))
    
    def get_address_data(self) -> tuple[str, str]:
        """获取输入的地址数据"""
        return self.name_combo.currentText().strip(), self.code_combo.currentText().strip()
    
    def validate_input(self) -> bool:
        """验证输入"""
        name, code = self.get_address_data()
        if not name or not code:
            QMessageBox.warning(self, translate("osc_address_tab.input_error"), 
                              translate("osc_address_tab.name_code_required"))
            return False
        return True


class OSCAddressListTab(QWidget):
    """OSC地址列表标签页"""
    
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.registries: Optional[Registries] = None
        self.options_provider: Optional[OSCOptionsProvider] = None
        
        # UI组件类型注解
        self.address_table: QTableWidget
        self.add_address_btn: QPushButton
        self.delete_address_btn: QPushButton
        self.refresh_btn: QPushButton
        self.save_addresses_btn: QPushButton
        self.status_label: QLabel
        self.address_list_group: QGroupBox
        
        self.init_ui()
        
        # 连接语言切换信号
        language_signals.language_changed.connect(self.update_ui_texts)
    
    def init_ui(self) -> None:
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 地址列表组
        self.create_address_list_group(layout)
        
        # 操作按钮组
        self.create_action_buttons_group(layout)
    
    def create_address_list_group(self, parent_layout: QVBoxLayout) -> None:
        """创建地址列表组"""
        self.address_list_group = QGroupBox(translate("osc_address_tab.address_list"))
        group = self.address_list_group
        layout = QVBoxLayout(group)
        
        # 地址表格
        self.address_table = QTableWidget()
        self.address_table.setColumnCount(3)
        self.address_table.setHorizontalHeaderLabels([
            translate("osc_address_tab.address_name"), 
            translate("osc_address_tab.osc_code"),
            translate("osc_address_tab.status")
        ])
        
        # 设置表格属性
        header = self.address_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)           # 名称列拉伸
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # 代码列拉伸
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)             # 状态列固定宽度
        header.resizeSection(2, 80)  # 状态列宽度80px
        
        self.address_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.address_table.setAlternatingRowColors(True)
        self.address_table.setStyleSheet("""
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
        
        layout.addWidget(self.address_table)
        
        # 状态标签
        self.status_label = QLabel(translate("osc_address_tab.total_addresses").format(0))
        self.status_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 12px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.status_label)
        
        parent_layout.addWidget(group)
    
    def create_action_buttons_group(self, parent_layout: QVBoxLayout) -> None:
        """创建操作按钮组"""
        button_layout = QHBoxLayout()
        
        # 添加地址按钮
        self.add_address_btn = QPushButton(translate("osc_address_tab.add_address"))
        self.add_address_btn.clicked.connect(self.add_address)
        self.add_address_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.add_address_btn.setToolTip(translate("osc_address_tab.add_address_tooltip"))
        button_layout.addWidget(self.add_address_btn)
        
        # 删除地址按钮
        self.delete_address_btn = QPushButton(translate("osc_address_tab.delete_address"))
        self.delete_address_btn.clicked.connect(self.delete_address)
        self.delete_address_btn.setEnabled(False)
        self.delete_address_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover:enabled {
                background-color: #d32f2f;
            }
            QPushButton:pressed:enabled {
                background-color: #b71c1c;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.delete_address_btn.setToolTip(translate("osc_address_tab.delete_address_tooltip"))
        button_layout.addWidget(self.delete_address_btn)
        
        # 刷新按钮
        self.refresh_btn = QPushButton(translate("osc_address_tab.refresh"))
        self.refresh_btn.clicked.connect(self.refresh_address_table)
        self.refresh_btn.setStyleSheet("""
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
        self.refresh_btn.setToolTip(translate("osc_address_tab.refresh_tooltip"))
        button_layout.addWidget(self.refresh_btn)
        
        # 保存地址按钮
        self.save_addresses_btn = QPushButton(translate("osc_address_tab.save_config"))
        self.save_addresses_btn.clicked.connect(self.save_addresses)
        self.save_addresses_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """)
        self.save_addresses_btn.setToolTip(translate("osc_address_tab.save_addresses_tooltip"))
        button_layout.addWidget(self.save_addresses_btn)
        
        button_layout.addStretch()  # 添加弹性空间
        parent_layout.addLayout(button_layout)
        
        # 连接表格选择变化信号
        self.address_table.itemSelectionChanged.connect(self.on_address_selection_changed)
    
    def set_registries(self, registries: Registries) -> None:
        """设置地址注册表引用"""
        self.registries = registries
        self.refresh_address_table()
    
    def set_options_provider(self, options_provider: OSCOptionsProvider) -> None:
        """设置下拉列表数据提供者并启用表格编辑器"""
        self.options_provider = options_provider
        
        # 设置表格代理以启用下拉列表编辑
        if self.options_provider:
            delegate = OSCTableDelegate(self.options_provider)
            self.address_table.setItemDelegate(delegate)
    
    def refresh_address_table(self) -> None:
        """刷新地址表格"""
        if not self.registries:
            return
        
        addresses = self.registries.address_registry.addresses
        self.address_table.setRowCount(len(addresses))
        
        for row, addr in enumerate(addresses):
            # 地址名
            name_item = QTableWidgetItem(addr.name)
            self.address_table.setItem(row, 0, name_item)
            
            # OSC代码
            code_item = QTableWidgetItem(addr.code)
            self.address_table.setItem(row, 1, code_item)
            
            # 状态列 - 所有地址都显示为可用状态
            status_item = QTableWidgetItem(translate("osc_address_tab.available"))
            
            # 设置状态列样式为绿色
            status_item.setBackground(QColor(144, 238, 144))  # 浅绿色背景
            status_item.setForeground(QColor(0, 128, 0))      # 深绿色文字
            
            # 状态列不可编辑
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.address_table.setItem(row, 2, status_item)
        
        # 更新状态标签
        total_count = len(addresses)
        self.status_label.setText(translate("osc_address_tab.total_addresses").format(total_count))
    
    def add_address(self) -> None:
        """添加新地址"""
        if not self.registries:
            QMessageBox.warning(self, translate("osc_address_tab.error"), 
                              translate("osc_address_tab.registry_not_available"))
            return
        
        if not self.options_provider:
            QMessageBox.warning(self, translate("osc_address_tab.error"), 
                              translate("osc_address_tab.provider_not_initialized"))
            return
        
        dialog = AddAddressDialog(self.options_provider, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.validate_input():
                name, code = dialog.get_address_data()
                
                # 检查是否已存在
                if self.registries.address_registry.has_address_name(name):
                    QMessageBox.warning(self, translate("osc_address_tab.error"),
                                      translate("osc_address_tab.address_exists"))
                    return
                
                if self.registries.address_registry.has_address_code(code):
                    QMessageBox.warning(self, translate("osc_address_tab.error"),
                                      translate("osc_address_tab.code_exists"))
                    return
                
                # 添加地址
                try:
                    self.registries.address_registry.register_address(name, code)
                    self.refresh_address_table()
                    self.save_addresses_silent()  # 静默自动保存到配置文件
                    logger.info(f"Added OSC address: {name} -> {code}")
                    
                    # 显示成功消息
                    QMessageBox.information(self, translate("osc_address_tab.success"),
                                          translate("osc_address_tab.address_added").format(name))
                except Exception as e:
                    QMessageBox.critical(self, translate("osc_address_tab.error"),
                                       f"Failed to add address: {str(e)}")
    
    def delete_address(self) -> None:
        """删除选中的地址"""
        current_row = self.address_table.currentRow()
        if current_row < 0:
            return
        
        if not self.registries:
            return
        
        # 获取选中的地址
        address_name_item = self.address_table.item(current_row, 0)
        if not address_name_item:
            return
        
        address_name = address_name_item.text()
        addr = self.registries.address_registry.get_address_by_name(address_name)
        if not addr:
            return
        
        # 由于core模块简化，现在所有地址都可以删除
        
        # 确认删除
        reply = QMessageBox.question(self, translate("osc_address_tab.confirm_delete"),
                                   translate("osc_address_tab.delete_address_confirm").format(address_name),
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 使用注册表的remove_address方法
                self.registries.address_registry.unregister_address(addr)
                self.refresh_address_table()
                self.save_addresses_silent()  # 静默自动保存到配置文件
                logger.info(f"Deleted OSC address: {address_name}")
                
                # 显示成功消息
                QMessageBox.information(self, translate("osc_address_tab.success"),
                                      translate("osc_address_tab.address_deleted").format(address_name))
                
            except Exception as e:
                QMessageBox.critical(self, translate("osc_address_tab.error"),
                                   f"Failed to delete address: {str(e)}")
    
    def save_addresses(self) -> None:
        """保存地址到配置文件"""
        if self.registries:
            try:
                # 导出所有地址
                all_addresses = self.registries.address_registry.export_to_config()
                
                # 更新settings
                self.ui_interface.settings['addresses'] = all_addresses
                
                # 保存到文件
                self.ui_interface.save_settings()
                logger.info(f"Saved {len(all_addresses)} addresses to config")
                
                # 显示成功消息
                QMessageBox.information(self, translate("osc_address_tab.success"),
                                      translate("osc_address_tab.addresses_saved").format(len(all_addresses)))
            except Exception as e:
                logger.error(f"Failed to save addresses: {e}")
                QMessageBox.critical(self, translate("osc_address_tab.error"),
                                   translate("osc_address_tab.save_addresses_failed").format(str(e)))
        else:
            QMessageBox.warning(self, translate("osc_address_tab.error"),
                              translate("osc_address_tab.registry_not_available"))
    
    def save_addresses_silent(self) -> None:
        """静默保存地址到配置文件（用于自动保存，不显示消息框）"""
        if self.registries:
            try:
                # 导出所有地址
                all_addresses = self.registries.address_registry.export_to_config()
                
                # 更新settings
                self.ui_interface.settings['addresses'] = all_addresses
                
                # 保存到文件
                self.ui_interface.save_settings()
                logger.info(f"Auto-saved {len(all_addresses)} addresses to config")
            except Exception as e:
                logger.error(f"Failed to auto-save addresses: {e}")
    
    def on_address_selection_changed(self) -> None:
        """地址选择变化时的处理"""
        has_selection = len(self.address_table.selectedItems()) > 0
        self.delete_address_btn.setEnabled(has_selection)
    
    def update_ui_texts(self) -> None:
        """更新UI文本"""
        # 更新分组框标题
        self.address_list_group.setTitle(translate("osc_address_tab.address_list"))
        
        # 更新表格标题
        self.address_table.setHorizontalHeaderLabels([
            translate("osc_address_tab.address_name"), 
            translate("osc_address_tab.osc_code"),
            translate("osc_address_tab.status")
        ])
        
        # 更新按钮文本
        self.add_address_btn.setText(translate("osc_address_tab.add_address"))
        self.delete_address_btn.setText(translate("osc_address_tab.delete_address"))
        self.refresh_btn.setText(translate("osc_address_tab.refresh"))
        self.save_addresses_btn.setText(translate("osc_address_tab.save_config"))
        
        # 更新工具提示
        self.add_address_btn.setToolTip(translate("osc_address_tab.add_address_tooltip"))
        self.delete_address_btn.setToolTip(translate("osc_address_tab.delete_address_tooltip"))
        self.refresh_btn.setToolTip(translate("osc_address_tab.refresh_tooltip"))
        self.save_addresses_btn.setToolTip(translate("osc_address_tab.save_addresses_tooltip"))
        
        # 刷新表格内容以更新状态列
        self.refresh_address_table()
        
        # 如果没有注册表，至少更新状态标签的文本格式
        if not self.registries:
            self.status_label.setText(translate("osc_address_tab.total_addresses").format(0))


class OSCAddressBindingTab(QWidget):
    """OSC地址绑定标签页"""
    
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.registries: Optional[Registries] = None
        self.options_provider: Optional[OSCOptionsProvider] = None
        
        # UI组件类型注解
        self.binding_table: QTableWidget
        self.add_binding_btn: QPushButton
        self.delete_binding_btn: QPushButton
        self.refresh_btn: QPushButton
        self.save_config_btn: QPushButton
        self.binding_status_label: QLabel
        self.address_binding_group: QGroupBox
        
        self.init_ui()
        
        # 连接语言切换信号
        language_signals.language_changed.connect(self.update_ui_texts)
    
    def init_ui(self) -> None:
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 地址绑定组
        self.create_address_binding_group(layout)
        
        # 操作按钮组
        self.create_action_buttons_group(layout)
    
    def create_address_binding_group(self, parent_layout: QVBoxLayout) -> None:
        """创建地址绑定组"""
        self.address_binding_group = QGroupBox(translate("osc_address_tab.address_binding"))
        group = self.address_binding_group
        layout = QVBoxLayout(group)
        
        # 绑定表格
        self.binding_table = QTableWidget()
        self.binding_table.setColumnCount(3)
        self.binding_table.setHorizontalHeaderLabels([
            translate("osc_address_tab.address_name"),
            translate("osc_address_tab.action_name"),
            translate("osc_address_tab.status")
        ])
        
        # 设置表格属性
        header = self.binding_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)           # 地址名列拉伸
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # 动作名列拉伸
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)             # 状态列固定宽度
        header.resizeSection(2, 100)  # 状态列宽度100px
        
        self.binding_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.binding_table.setAlternatingRowColors(True)
        self.binding_table.setStyleSheet("""
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
        
        layout.addWidget(self.binding_table)
        
        # 绑定状态标签
        self.binding_status_label = QLabel(translate("osc_address_tab.binding_status_all_valid").format(0))
        self.binding_status_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 12px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.binding_status_label)
        
        parent_layout.addWidget(group)
    
    def create_action_buttons_group(self, parent_layout: QVBoxLayout) -> None:
        """创建操作按钮组"""
        button_layout = QHBoxLayout()
        
        # 添加绑定按钮
        self.add_binding_btn = QPushButton(translate("osc_address_tab.add_binding"))
        self.add_binding_btn.clicked.connect(self.add_binding)
        self.add_binding_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.add_binding_btn.setToolTip(translate("osc_address_tab.add_binding_tooltip"))
        button_layout.addWidget(self.add_binding_btn)
        
        # 删除绑定按钮
        self.delete_binding_btn = QPushButton(translate("osc_address_tab.delete_binding"))
        self.delete_binding_btn.clicked.connect(self.delete_binding)
        self.delete_binding_btn.setEnabled(False)
        self.delete_binding_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover:enabled {
                background-color: #d32f2f;
            }
            QPushButton:pressed:enabled {
                background-color: #b71c1c;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.delete_binding_btn.setToolTip(translate("osc_address_tab.delete_binding_tooltip"))
        button_layout.addWidget(self.delete_binding_btn)
        
        # 刷新按钮
        self.refresh_btn = QPushButton(translate("osc_address_tab.refresh"))
        self.refresh_btn.clicked.connect(self.refresh_binding_table)
        self.refresh_btn.setStyleSheet("""
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
        self.refresh_btn.setToolTip(translate("osc_address_tab.refresh_binding_tooltip"))
        button_layout.addWidget(self.refresh_btn)
        
        # 保存配置按钮
        self.save_config_btn = QPushButton(translate("osc_address_tab.save_config"))
        self.save_config_btn.clicked.connect(self.save_config)
        self.save_config_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """)
        self.save_config_btn.setToolTip(translate("osc_address_tab.save_config_tooltip"))
        button_layout.addWidget(self.save_config_btn)
        
        button_layout.addStretch()  # 添加弹性空间
        parent_layout.addLayout(button_layout)
        
        # 连接表格选择变化信号
        self.binding_table.itemSelectionChanged.connect(self.on_binding_selection_changed)
    
    def set_registries(self, registries: Registries) -> None:
        """设置注册表引用"""
        self.registries = registries
        self.refresh_binding_table()
    
    def set_options_provider(self, options_provider: OSCOptionsProvider) -> None:
        """设置下拉列表数据提供者并启用表格编辑器"""
        self.options_provider = options_provider
        
        # 设置表格代理以启用下拉列表编辑
        if self.options_provider:
            delegate = OSCBindingTableDelegate(self.options_provider)
            self.binding_table.setItemDelegate(delegate)
    
    def refresh_binding_table(self) -> None:
        """刷新绑定表格"""
        if not self.registries:
            return
        
        bindings = list(self.registries.binding_registry.bindings.items())
        self.binding_table.setRowCount(len(bindings))
        
        # 统计有效和无效绑定数量
        valid_count = 0
        invalid_count = 0
        
        for row, (addr, action) in enumerate(bindings):
            # 地址名
            addr_item = QTableWidgetItem(addr.name)
            self.binding_table.setItem(row, 0, addr_item)
            
            # 动作名
            action_item = QTableWidgetItem(action.name)
            self.binding_table.setItem(row, 1, action_item)
            
            # 验证绑定有效性
            is_valid, error_msg = self.validate_binding(addr, action)
            
            # 状态列
            if is_valid:
                status_text = translate("osc_address_tab.available")
                status_item = QTableWidgetItem(status_text)
                # 有效绑定：明显的绿色背景
                status_item.setBackground(QColor(144, 238, 144))  # 浅绿色
                status_item.setForeground(QColor(0, 128, 0))      # 深绿色文字
                status_item.setToolTip(translate("osc_address_tab.binding_valid_tooltip"))
                valid_count += 1
                
                # 为有效绑定的行设置正常样式
                addr_item.setBackground(Qt.GlobalColor.white)
                action_item.setBackground(Qt.GlobalColor.white)
            else:
                status_text = translate("osc_address_tab.invalid")
                status_item = QTableWidgetItem(status_text)
                # 无效绑定：浅红色背景
                status_item.setBackground(QColor(255, 200, 200))  # 浅红色
                status_item.setForeground(QColor(150, 0, 0))      # 深红色文字
                status_item.setToolTip(translate("osc_address_tab.binding_invalid").format(error_msg))
                invalid_count += 1
                
                # 为无效绑定的行设置警告样式
                addr_item.setBackground(QColor(240, 240, 240))    # 浅灰色
                action_item.setBackground(QColor(240, 240, 240))  # 浅灰色
                addr_item.setForeground(QColor(150, 0, 0))        # 深红色文字
                action_item.setForeground(QColor(150, 0, 0))      # 深红色文字
            
            # 状态列不可编辑
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.binding_table.setItem(row, 2, status_item)
        
        # 更新状态标签，显示详细统计
        total_count = len(bindings)
        if invalid_count > 0:
            self.binding_status_label.setText(translate("osc_address_tab.binding_status_with_invalid").format(total_count, valid_count, invalid_count))
            self.binding_status_label.setStyleSheet("""
                QLabel {
                    color: #d32f2f;
                    font-size: 12px;
                    padding: 5px;
                    font-weight: bold;
                }
            """)
        else:
            self.binding_status_label.setText(translate("osc_address_tab.binding_status_all_valid").format(total_count))
            self.binding_status_label.setStyleSheet("""
                QLabel {
                    color: #2e7d32;
                    font-size: 12px;
                    padding: 5px;
                    font-weight: bold;
                }
            """)

    
    def validate_binding(self, address: OSCAddress, action: OSCAction) -> tuple[bool, str]:
        """验证绑定的有效性
        
        Args:
            address: OSC地址对象
            action: OSC动作对象
            
        Returns:
            tuple[bool, str]: (是否有效, 错误信息)
        """
        # 基本对象验证
        if not address or not action:
            return False, "地址或动作对象为空"
        
        # 验证地址对象的有效性
        try:
            if not address.name or not address.name.strip():
                return False, "地址名称为空"
            if not address.code or not address.code.strip():
                return False, "OSC代码为空"
        except AttributeError:
            return False, "地址对象缺少必要属性"
        
        # 验证动作对象的有效性
        try:
            if not action.name or not action.name.strip():
                return False, "动作名称为空"
        except AttributeError:
            return False, "动作对象缺少必要属性"
        
        # 如果提供了注册表，检查对象是否仍然在注册表中
        if self.registries:
            if not self.registries.address_registry.has_address_name(address.name):
                return False, f"地址'{address.name}'不存在于注册表中"
            # 检查地址对象是否一致
            registered_address = self.registries.address_registry.get_address_by_name(address.name)
            if registered_address and registered_address.code != address.code:
                return False, f"地址'{address.name}'的OSC代码已变更"

            if not self.registries.action_registry.has_action_name(action.name):
                return False, f"动作'{action.name}'不存在于注册表中"
        
        return True, ""
    
    def save_config(self) -> None:
        """保存配置到文件"""
        try:
            # 保存所有绑定
            if self.registries:
                # 获取所有绑定
                all_bindings = self.registries.binding_registry.export_to_config()
                self.ui_interface.settings['bindings'] = all_bindings
                    
            # 调用UIInterface的保存方法
            self.ui_interface.save_settings()
            QMessageBox.information(self, translate("osc_address_tab.success"),
                                  translate("osc_address_tab.config_saved"))
        except Exception as e:
            QMessageBox.critical(self, translate("osc_address_tab.error"),
                               translate("osc_address_tab.save_config_failed").format(str(e)))
    
    def add_binding(self) -> None:
        """添加新的地址绑定"""
        if not self.registries:
            QMessageBox.warning(self, translate("osc_address_tab.error"), 
                              translate("osc_address_tab.registry_not_ready"))
            return
        
        dialog = AddBindingDialog(self, self.registries)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.validate_input():
                address_name, action_name = dialog.get_binding_data()
                
                # 获取地址和动作对象
                address = self.registries.address_registry.get_address_by_name(address_name)
                action = self.registries.action_registry.get_action_by_name(action_name)
                
                if not address or not action:
                    QMessageBox.critical(self, translate("osc_address_tab.error"),
                                       translate("osc_address_tab.address_action_not_found").format(address_name, action_name))
                    return
                
                # 检查是否已存在的绑定
                if self.registries.binding_registry.has_binding(address):
                    reply = QMessageBox.question(self, translate("osc_address_tab.confirm_replace"),
                                                translate("osc_address_tab.replace_binding_msg").format(address_name),
                                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                
                # 添加绑定
                try:
                    self.registries.binding_registry.register_binding(address, action)
                    self.refresh_binding_table()
                    logger.info(f"Added address binding: {address_name} -> {action_name}")
                    
                    # 显示成功消息
                    QMessageBox.information(self, translate("osc_address_tab.success"),
                                          translate("osc_address_tab.binding_added").format(address_name, action_name))
                except Exception as e:
                    QMessageBox.critical(self, translate("osc_address_tab.error"),
                                       translate("osc_address_tab.add_binding_failed").format(str(e)))
    
    def delete_binding(self) -> None:
        """删除选中的地址绑定"""
        current_row = self.binding_table.currentRow()
        if current_row < 0:
            return
        
        if not self.registries:
            return
        
        # 获取选中的绑定
        bindings = list(self.registries.binding_registry.bindings.items())
        if current_row >= len(bindings):
            return
        
        address, action = bindings[current_row]
        
        # 由于core模块简化，现在所有绑定都可以删除
        
        # 确认删除
        reply = QMessageBox.question(self, translate("osc_address_tab.confirm_delete"),
                                   translate("osc_address_tab.delete_binding_msg").format(address.name, action.name),
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.registries.binding_registry.unregister_binding(address)
                self.refresh_binding_table()
                logger.info(f"Deleted address binding: {address.name} -> {action.name}")
                
                # 显示成功消息
                QMessageBox.information(self, translate("osc_address_tab.success"),
                                      translate("osc_address_tab.binding_deleted").format(address.name, action.name))
                
            except Exception as e:
                QMessageBox.critical(self, translate("osc_address_tab.error"),
                                   translate("osc_address_tab.delete_binding_failed").format(str(e)))
    
    def on_binding_selection_changed(self) -> None:
        """绑定选择变化时的处理"""
        has_selection = len(self.binding_table.selectedItems()) > 0
        self.delete_binding_btn.setEnabled(has_selection)
    
    def update_ui_texts(self) -> None:
        """更新UI文本"""
        # 更新分组框标题
        self.address_binding_group.setTitle(translate("osc_address_tab.address_binding"))
        
        # 更新表格标题
        self.binding_table.setHorizontalHeaderLabels([
            translate("osc_address_tab.address_name"),
            translate("osc_address_tab.action_name"),
            translate("osc_address_tab.status")
        ])
        
        # 更新按钮文本
        self.add_binding_btn.setText(translate("osc_address_tab.add_binding"))
        self.delete_binding_btn.setText(translate("osc_address_tab.delete_binding"))
        self.refresh_btn.setText(translate("osc_address_tab.refresh"))
        self.save_config_btn.setText(translate("osc_address_tab.save_config"))
        
        # 更新工具提示
        self.add_binding_btn.setToolTip(translate("osc_address_tab.add_binding_tooltip"))
        self.delete_binding_btn.setToolTip(translate("osc_address_tab.delete_binding_tooltip"))
        self.refresh_btn.setToolTip(translate("osc_address_tab.refresh_binding_tooltip"))
        self.save_config_btn.setToolTip(translate("osc_address_tab.save_config_tooltip"))
        
        # 刷新表格内容以更新状态列
        self.refresh_binding_table()
        
        # 如果没有绑定注册表，至少更新状态标签的文本格式
        if not self.registries:
            self.binding_status_label.setText(translate("osc_address_tab.binding_status_all_valid").format(0))


class OSCAddressTab(QWidget):
    """OSC地址管理面板 - 包含地址列表和绑定管理的标签页"""
    
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        
        # UI组件类型注解
        self.tab_widget: QTabWidget
        self.address_list_tab: OSCAddressListTab
        self.address_binding_tab: OSCAddressBindingTab
        
        self.init_ui()
        
        # 连接语言切换信号
        language_signals.language_changed.connect(self.update_ui_texts)
    
    def init_ui(self) -> None:
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 创建内部标签页
        self.tab_widget = QTabWidget()
        
        # 地址列表标签页
        self.address_list_tab = OSCAddressListTab(self.ui_interface)
        self.tab_widget.addTab(self.address_list_tab, translate("osc_address_tab.address_list"))
        
        # 地址绑定标签页
        self.address_binding_tab = OSCAddressBindingTab(self.ui_interface)
        self.tab_widget.addTab(self.address_binding_tab, translate("osc_address_tab.address_binding"))
        
        layout.addWidget(self.tab_widget)
    
    def set_registries(self, registries: Registries) -> None:
        """设置注册表引用"""
        self.address_list_tab.set_registries(registries)
        self.address_binding_tab.set_registries(registries)
    
    def set_options_provider(self, options_provider: OSCOptionsProvider) -> None:
        """设置下拉列表数据提供者"""
        self.address_list_tab.set_options_provider(options_provider)
        self.address_binding_tab.set_options_provider(options_provider)
    
    def update_ui_texts(self) -> None:
        """更新UI文本"""
        # 更新内部标签页标题
        self.tab_widget.setTabText(0, translate("osc_address_tab.address_list"))
        self.tab_widget.setTabText(1, translate("osc_address_tab.address_binding"))
        
        # 更新子标签页的文本
        self.address_list_tab.update_ui_texts()
        self.address_binding_tab.update_ui_texts()