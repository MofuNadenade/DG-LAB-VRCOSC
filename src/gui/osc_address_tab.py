from typing import Optional, TYPE_CHECKING
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QGroupBox, QFormLayout, QLabel,
    QHeaderView, QMessageBox, QDialog, QDialogButtonBox, QTabWidget, QComboBox
)
from PySide6.QtCore import Qt
import logging

from i18n import translate as _, language_signals
from core import OSCAddressRegistry, OSCActionRegistry, OSCBindingRegistry, OSCOptionsProvider
from .ui_interface import UIInterface
from .widgets import OSCTableDelegate, OSCBindingTableDelegate, EditableComboBox

if TYPE_CHECKING:
    from core import OSCAddress, OSCAction

logger = logging.getLogger(__name__)


class AddBindingDialog(QDialog):
    """添加OSC地址绑定的对话框"""
    
    def __init__(self, address_registry: OSCAddressRegistry, action_registry: OSCActionRegistry, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.address_registry = address_registry
        self.action_registry = action_registry
        
        # UI组件类型注解
        self.address_combo: QComboBox
        self.action_combo: QComboBox
        
        self.setWindowTitle(_("osc_address_tab.add_binding"))
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
        address_options = [addr.name for addr in self.address_registry.addresses]
        self.address_combo = EditableComboBox(address_options)
        form_layout.addRow(_("osc_address_tab.address_name") + ":", self.address_combo)
        
        # 动作选择
        action_options = [action.name for action in self.action_registry.actions]
        self.action_combo = EditableComboBox(action_options)
        form_layout.addRow(_("osc_address_tab.action_name") + ":", self.action_combo)
        
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
        self.setWindowTitle(_("osc_address_tab.add_binding"))
    
    def get_binding_data(self) -> tuple[str, str]:
        """获取选中的绑定数据"""
        return self.address_combo.currentText(), self.action_combo.currentText()
    
    def validate_input(self) -> bool:
        """验证输入"""
        address_name, action_name = self.get_binding_data()
        if not address_name or not action_name:
            QMessageBox.warning(self, _("osc_address_tab.input_error"), 
                              "请选择地址和动作")
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
        
        self.setWindowTitle(_("osc_address_tab.add_address"))
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
            name_line_edit.setPlaceholderText(_("osc_address_tab.address_name_placeholder"))
        form_layout.addRow(_("osc_address_tab.address_name") + ":", self.name_combo)
        
        # OSC地址/代码 - 可编辑下拉列表
        osc_code_options = self.options_provider.get_osc_code_options()
        self.code_combo = EditableComboBox(osc_code_options)
        self.code_combo.setCurrentText("")  # 默认为空，让用户输入
        code_line_edit = self.code_combo.lineEdit()
        if code_line_edit:
            code_line_edit.setPlaceholderText(_("osc_address_tab.osc_code_placeholder"))
        form_layout.addRow(_("osc_address_tab.osc_code") + ":", self.code_combo)
        
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
        self.setWindowTitle(_("osc_address_tab.add_address"))
        name_line_edit = self.name_combo.lineEdit()
        if name_line_edit:
            name_line_edit.setPlaceholderText(_("osc_address_tab.address_name_placeholder"))
        code_line_edit = self.code_combo.lineEdit()
        if code_line_edit:
            code_line_edit.setPlaceholderText(_("osc_address_tab.osc_code_placeholder"))
    
    def get_address_data(self) -> tuple[str, str]:
        """获取输入的地址数据"""
        return self.name_combo.currentText().strip(), self.code_combo.currentText().strip()
    
    def validate_input(self) -> bool:
        """验证输入"""
        name, code = self.get_address_data()
        if not name or not code:
            QMessageBox.warning(self, _("osc_address_tab.input_error"), 
                              _("osc_address_tab.name_code_required"))
            return False
        return True


class OSCAddressListTab(QWidget):
    """OSC地址列表标签页"""
    
    def __init__(self, ui_callback: UIInterface) -> None:
        super().__init__()
        self.ui_callback: UIInterface = ui_callback
        self.address_registry: Optional[OSCAddressRegistry] = None
        self.options_provider: Optional[OSCOptionsProvider] = None
        
        # UI组件类型注解
        self.address_table: QTableWidget
        self.add_address_btn: QPushButton
        self.delete_address_btn: QPushButton
        self.refresh_btn: QPushButton
        self.save_addresses_btn: QPushButton
        self.status_label: QLabel
        
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
        group = QGroupBox(_("osc_address_tab.address_list"))
        layout = QVBoxLayout(group)
        
        # 地址表格
        self.address_table = QTableWidget()
        self.address_table.setColumnCount(3)
        self.address_table.setHorizontalHeaderLabels([
            _("osc_address_tab.address_name"), 
            _("osc_address_tab.osc_code"),
            _("osc_address_tab.status")
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
        self.status_label = QLabel("地址总数: 0 (默认: 0, 自定义: 0)")
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
        self.add_address_btn = QPushButton(_("osc_address_tab.add_address"))
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
        self.add_address_btn.setToolTip("添加新的自定义OSC地址")
        button_layout.addWidget(self.add_address_btn)
        
        # 删除地址按钮
        self.delete_address_btn = QPushButton(_("osc_address_tab.delete_address"))
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
        self.delete_address_btn.setToolTip("删除选中的自定义地址（不能删除默认地址）")
        button_layout.addWidget(self.delete_address_btn)
        
        # 刷新按钮
        self.refresh_btn = QPushButton(_("osc_address_tab.refresh"))
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
        self.refresh_btn.setToolTip("刷新地址列表")
        button_layout.addWidget(self.refresh_btn)
        
        # 保存地址按钮
        self.save_addresses_btn = QPushButton(_("osc_address_tab.save_config"))
        self.save_addresses_btn.clicked.connect(self.save_custom_addresses)
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
        self.save_addresses_btn.setToolTip("保存自定义地址到配置文件")
        button_layout.addWidget(self.save_addresses_btn)
        
        button_layout.addStretch()  # 添加弹性空间
        parent_layout.addLayout(button_layout)
        
        # 连接表格选择变化信号
        self.address_table.itemSelectionChanged.connect(self.on_address_selection_changed)
    
    def set_address_registry(self, address_registry: OSCAddressRegistry) -> None:
        """设置地址注册表引用"""
        self.address_registry = address_registry
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
        if not self.address_registry:
            return
        
        addresses = self.address_registry.addresses
        self.address_table.setRowCount(len(addresses))
        
        for row, addr in enumerate(addresses):
            # 地址名
            name_item = QTableWidgetItem(addr.name)
            self.address_table.setItem(row, 0, name_item)
            
            # OSC代码
            code_item = QTableWidgetItem(addr.code)
            self.address_table.setItem(row, 1, code_item)
            
            # 状态列
            is_custom = addr in self.address_registry.get_custom_addresses()
            status_item = QTableWidgetItem("自定义" if is_custom else "默认")
            
            # 设置状态列样式
            if is_custom:
                status_item.setBackground(Qt.GlobalColor.green)
                status_item.setForeground(Qt.GlobalColor.darkGreen)
            else:
                status_item.setBackground(Qt.GlobalColor.cyan)
                status_item.setForeground(Qt.GlobalColor.darkBlue)
            
            # 状态列不可编辑
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.address_table.setItem(row, 2, status_item)
        
        # 更新状态标签
        total_count = len(addresses)
        custom_count = len(self.address_registry.get_custom_addresses())
        default_count = total_count - custom_count
        self.status_label.setText(f"地址总数: {total_count} (默认: {default_count}, 自定义: {custom_count})")
    
    def add_address(self) -> None:
        """添加新地址"""
        if not self.address_registry:
            QMessageBox.warning(self, _("osc_address_tab.error"), 
                              _("osc_address_tab.registry_not_available"))
            return
        
        if not self.options_provider:
            QMessageBox.warning(self, _("osc_address_tab.error"), 
                              "下拉列表数据提供者未初始化")
            return
        
        dialog = AddAddressDialog(self.options_provider, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.validate_input():
                name, code = dialog.get_address_data()
                
                # 检查是否已存在
                if name in self.address_registry.addresses_by_name:
                    QMessageBox.warning(self, _("osc_address_tab.error"),
                                      _("osc_address_tab.address_exists"))
                    return
                
                if code in self.address_registry.addresses_by_code:
                    QMessageBox.warning(self, _("osc_address_tab.error"),
                                      _("osc_address_tab.code_exists"))
                    return
                
                # 添加地址
                try:
                    self.address_registry.register_custom_address(name, code)
                    self.refresh_address_table()
                    self.save_custom_addresses_silent()  # 静默自动保存到配置文件
                    logger.info(f"Added OSC address: {name} -> {code}")
                    
                    # 显示成功消息
                    QMessageBox.information(self, _("osc_address_tab.success"),
                                          f"成功添加地址: {name}，已自动保存到配置文件")
                except Exception as e:
                    QMessageBox.critical(self, _("osc_address_tab.error"),
                                       f"Failed to add address: {str(e)}")
    
    def delete_address(self) -> None:
        """删除选中的地址"""
        current_row = self.address_table.currentRow()
        if current_row < 0:
            return
        
        if not self.address_registry:
            return
        
        # 获取选中的地址
        address_name_item = self.address_table.item(current_row, 0)
        if not address_name_item:
            return
        
        address_name = address_name_item.text()
        addr = self.address_registry.addresses_by_name.get(address_name)
        if not addr:
            return
        
        # 检查是否为自定义地址
        is_custom = addr in self.address_registry.get_custom_addresses()
        if not is_custom:
            QMessageBox.warning(self, _("osc_address_tab.error"),
                              "不能删除默认地址，只能删除自定义地址")
            return
        
        # 确认删除
        reply = QMessageBox.question(self, _("osc_address_tab.confirm_delete"),
                                   _("osc_address_tab.delete_address_confirm").format(address_name),
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 使用注册表的remove_address方法
                self.address_registry.remove_address(addr)
                self.refresh_address_table()
                self.save_custom_addresses_silent()  # 静默自动保存到配置文件
                logger.info(f"Deleted OSC address: {address_name}")
                
                # 显示成功消息
                QMessageBox.information(self, _("osc_address_tab.success"),
                                      f"成功删除地址: {address_name}，已自动保存到配置文件")
                
            except Exception as e:
                QMessageBox.critical(self, _("osc_address_tab.error"),
                                   f"Failed to delete address: {str(e)}")
    
    def save_custom_addresses(self) -> None:
        """保存自定义地址到配置文件"""
        if self.address_registry:
            try:
                # 导出自定义地址
                custom_addresses = self.address_registry.export_custom_addresses()
                
                # 更新settings
                self.ui_callback.settings['custom_addresses'] = custom_addresses
                
                # 保存到文件
                self.ui_callback.save_settings()
                logger.info(f"Saved {len(custom_addresses)} custom addresses to config")
                
                # 显示成功消息
                QMessageBox.information(self, _("osc_address_tab.success"),
                                      f"成功保存 {len(custom_addresses)} 个自定义地址到配置文件")
            except Exception as e:
                logger.error(f"Failed to save custom addresses: {e}")
                QMessageBox.critical(self, _("osc_address_tab.error"),
                                   f"保存自定义地址失败: {str(e)}")
        else:
            QMessageBox.warning(self, _("osc_address_tab.error"),
                              _("osc_address_tab.registry_not_available"))
    
    def save_custom_addresses_silent(self) -> None:
        """静默保存自定义地址到配置文件（用于自动保存，不显示消息框）"""
        if self.address_registry:
            try:
                # 导出自定义地址
                custom_addresses = self.address_registry.export_custom_addresses()
                
                # 更新settings
                self.ui_callback.settings['custom_addresses'] = custom_addresses
                
                # 保存到文件
                self.ui_callback.save_settings()
                logger.info(f"Auto-saved {len(custom_addresses)} custom addresses to config")
            except Exception as e:
                logger.error(f"Failed to auto-save custom addresses: {e}")
    
    def on_address_selection_changed(self) -> None:
        """地址选择变化时的处理"""
        has_selection = len(self.address_table.selectedItems()) > 0
        self.delete_address_btn.setEnabled(has_selection)
    
    def update_ui_texts(self) -> None:
        """更新UI文本"""
        # 更新表格标题
        self.address_table.setHorizontalHeaderLabels([
            _("osc_address_tab.address_name"), 
            _("osc_address_tab.osc_code"),
            _("osc_address_tab.status")
        ])
        
        # 更新按钮文本
        self.add_address_btn.setText(_("osc_address_tab.add_address"))
        self.delete_address_btn.setText(_("osc_address_tab.delete_address"))
        self.refresh_btn.setText(_("osc_address_tab.refresh"))
        self.save_addresses_btn.setText(_("osc_address_tab.save_config"))
        
        # 刷新表格内容以更新状态列
        self.refresh_address_table()


class OSCAddressBindingTab(QWidget):
    """OSC地址绑定标签页"""
    
    def __init__(self, ui_callback: UIInterface) -> None:
        super().__init__()
        self.ui_callback: UIInterface = ui_callback
        self.address_registry: Optional[OSCAddressRegistry] = None
        self.action_registry: Optional[OSCActionRegistry] = None
        self.address_bindings: Optional[OSCBindingRegistry] = None
        self.options_provider: Optional[OSCOptionsProvider] = None
        
        # UI组件类型注解
        self.binding_table: QTableWidget
        self.add_binding_btn: QPushButton
        self.delete_binding_btn: QPushButton
        self.refresh_btn: QPushButton
        self.save_config_btn: QPushButton
        self.binding_status_label: QLabel
        
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
        group = QGroupBox(_("osc_address_tab.address_binding"))
        layout = QVBoxLayout(group)
        
        # 绑定表格
        self.binding_table = QTableWidget()
        self.binding_table.setColumnCount(3)
        self.binding_table.setHorizontalHeaderLabels([
            _("osc_address_tab.address_name"),
            _("osc_address_tab.action_name"),
            _("osc_address_tab.status")
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
        self.binding_status_label = QLabel("绑定总数: 0 (有效: 0, 无效: 0)")
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
        self.add_binding_btn = QPushButton("添加绑定")
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
        self.add_binding_btn.setToolTip("添加新的地址绑定")
        button_layout.addWidget(self.add_binding_btn)
        
        # 删除绑定按钮
        self.delete_binding_btn = QPushButton("删除绑定")
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
        self.delete_binding_btn.setToolTip("删除选中的自定义地址绑定（不能删除默认绑定）")
        button_layout.addWidget(self.delete_binding_btn)
        
        # 刷新按钮
        self.refresh_btn = QPushButton(_("osc_address_tab.refresh"))
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
        self.refresh_btn.setToolTip("刷新地址绑定列表")
        button_layout.addWidget(self.refresh_btn)
        
        # 保存配置按钮
        self.save_config_btn = QPushButton(_("osc_address_tab.save_config"))
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
        self.save_config_btn.setToolTip("保存当前的地址绑定配置到文件")
        button_layout.addWidget(self.save_config_btn)
        
        button_layout.addStretch()  # 添加弹性空间
        parent_layout.addLayout(button_layout)
        
        # 连接表格选择变化信号
        self.binding_table.itemSelectionChanged.connect(self.on_binding_selection_changed)
    
    def set_registries(self, address_registry: OSCAddressRegistry, 
                      action_registry: OSCActionRegistry, 
                      address_bindings: OSCBindingRegistry) -> None:
        """设置注册表引用"""
        self.address_registry = address_registry
        self.action_registry = action_registry
        self.address_bindings = address_bindings
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
        if not self.address_bindings:
            return
        
        bindings = list(self.address_bindings.bindings.items())
        self.binding_table.setRowCount(len(bindings))
        
        valid_count = 0
        invalid_count = 0
        default_count = 0
        custom_count = 0
        
        for row, (addr, action) in enumerate(bindings):
            # 地址名
            addr_item = QTableWidgetItem(addr.name)
            self.binding_table.setItem(row, 0, addr_item)
            
            # 动作名
            action_item = QTableWidgetItem(action.name)
            self.binding_table.setItem(row, 1, action_item)
            
            # 检查是否为默认绑定
            binding_dict = {'address_name': addr.name, 'action_name': action.name}
            is_default = self.address_bindings.is_binding_template(binding_dict)
            
            # 状态列 - 显示默认/自定义和有效性
            is_valid = self._is_binding_valid(addr, action)
            
            if is_default:
                status_text = "默认"
                default_count += 1
            else:
                status_text = "自定义"
                custom_count += 1
            
            # 如果绑定无效，在状态文本后添加标识
            if not is_valid:
                status_text += " (无效)"
                invalid_count += 1
            else:
                valid_count += 1
            
            status_item = QTableWidgetItem(status_text)
            
            # 设置状态列样式
            if is_default:
                if is_valid:
                    status_item.setBackground(Qt.GlobalColor.cyan)
                    status_item.setForeground(Qt.GlobalColor.darkBlue)
                else:
                    status_item.setBackground(Qt.GlobalColor.yellow)
                    status_item.setForeground(Qt.GlobalColor.darkRed)
            else:
                if is_valid:
                    status_item.setBackground(Qt.GlobalColor.green)
                    status_item.setForeground(Qt.GlobalColor.darkGreen)
                else:
                    status_item.setBackground(Qt.GlobalColor.red)
                    status_item.setForeground(Qt.GlobalColor.white)
            
            # 状态列不可编辑
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.binding_table.setItem(row, 2, status_item)
        
        # 更新状态标签
        total_count = len(bindings)
        self.binding_status_label.setText(f"绑定总数: {total_count} (默认: {default_count}, 自定义: {custom_count}, 有效: {valid_count}, 无效: {invalid_count})")
    
    def _is_binding_valid(self, addr: 'OSCAddress', action: 'OSCAction') -> bool:
        """检查绑定是否有效"""
        try:
            # 检查注册表是否存在
            if not self.address_registry or not self.action_registry:
                return False
            
            # 检查地址是否仍然存在于注册表中
            addr_exists = addr.name in self.address_registry.addresses_by_name
            
            # 检查动作是否仍然存在于注册表中
            action_exists = action.name in self.action_registry.actions_by_name
            
            # 如果地址或动作不存在，则绑定无效
            if not addr_exists or not action_exists:
                return False
            
            # 检查地址和动作的对象是否与注册表中的一致
            addr_valid = self.address_registry.addresses_by_name[addr.name] == addr
            action_valid = self.action_registry.actions_by_name[action.name] == action
            
            return addr_valid and action_valid
            
        except Exception as e:
            logger.warning(f"Error validating binding: {e}")
            return False
    
    def save_config(self) -> None:
        """保存配置到文件"""
        try:
            # 首先将当前绑定状态同步到settings
            if self.address_bindings:
                # 从内存对象提取当前绑定状态
                address_bindings = []
                for address, action in self.address_bindings.bindings.items():
                    binding_data = {
                        'address_name': address.name,
                        'action_name': action.name
                    }
                    address_bindings.append(binding_data)
                
                # 过滤掉默认绑定，只保存用户自定义的绑定
                custom_bindings = self.address_bindings.filter_non_binding_templates(address_bindings)
                
                # 只有当存在用户自定义绑定时才保存address_bindings字段
                if custom_bindings:
                    self.ui_callback.settings['address_bindings'] = custom_bindings
                else:
                    # 如果只有默认绑定，则从配置中移除address_bindings字段
                    if 'address_bindings' in self.ui_callback.settings:
                        del self.ui_callback.settings['address_bindings']
                    
            # 调用UIInterface的保存方法
            self.ui_callback.save_settings()
            QMessageBox.information(self, _("osc_address_tab.success"),
                                  _("osc_address_tab.config_saved"))
        except Exception as e:
            QMessageBox.critical(self, _("osc_address_tab.error"),
                               f"Failed to save config: {str(e)}")
    
    def add_binding(self) -> None:
        """添加新的地址绑定"""
        if not self.address_registry or not self.action_registry or not self.address_bindings:
            QMessageBox.warning(self, _("osc_address_tab.error"), 
                              "注册表不可用，请等待初始化完成")
            return
        
        dialog = AddBindingDialog(self.address_registry, self.action_registry, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.validate_input():
                address_name, action_name = dialog.get_binding_data()
                
                # 获取地址和动作对象
                address = self.address_registry.addresses_by_name.get(address_name)
                action = self.action_registry.actions_by_name.get(action_name)
                
                if not address or not action:
                    QMessageBox.critical(self, _("osc_address_tab.error"),
                                       f"未找到地址或动作: {address_name}, {action_name}")
                    return
                
                # 检查是否已存在的绑定
                if address in self.address_bindings.bindings:
                    reply = QMessageBox.question(self, "确认替换",
                                                f"地址 '{address_name}' 已有绑定，是否替换？",
                                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                
                # 添加绑定
                try:
                    self.address_bindings.register_binding(address, action)
                    self.refresh_binding_table()
                    logger.info(f"Added address binding: {address_name} -> {action_name}")
                    
                    # 显示成功消息
                    QMessageBox.information(self, _("osc_address_tab.success"),
                                          f"成功添加绑定: {address_name} -> {action_name}")
                except Exception as e:
                    QMessageBox.critical(self, _("osc_address_tab.error"),
                                       f"添加绑定失败: {str(e)}")
    
    def delete_binding(self) -> None:
        """删除选中的地址绑定"""
        current_row = self.binding_table.currentRow()
        if current_row < 0:
            return
        
        if not self.address_bindings:
            return
        
        # 获取选中的绑定
        bindings = list(self.address_bindings.bindings.items())
        if current_row >= len(bindings):
            return
        
        address, action = bindings[current_row]
        
        # 检查是否为默认绑定
        binding_dict = {'address_name': address.name, 'action_name': action.name}
        is_default = self.address_bindings.is_binding_template(binding_dict)
        
        if is_default:
            QMessageBox.warning(self, _("osc_address_tab.error"),
                              "不能删除默认绑定，只能删除自定义绑定")
            return
        
        # 确认删除
        reply = QMessageBox.question(self, "确认删除",
                                   f"是否删除绑定: {address.name} -> {action.name}？",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.address_bindings.unregister_binding(address)
                self.refresh_binding_table()
                logger.info(f"Deleted address binding: {address.name} -> {action.name}")
                
                # 显示成功消息
                QMessageBox.information(self, _("osc_address_tab.success"),
                                      f"成功删除绑定: {address.name} -> {action.name}")
                
            except Exception as e:
                QMessageBox.critical(self, _("osc_address_tab.error"),
                                   f"删除绑定失败: {str(e)}")
    
    def on_binding_selection_changed(self) -> None:
        """绑定选择变化时的处理"""
        has_selection = len(self.binding_table.selectedItems()) > 0
        self.delete_binding_btn.setEnabled(has_selection)
    
    def update_ui_texts(self) -> None:
        """更新UI文本"""
        # 更新表格标题
        self.binding_table.setHorizontalHeaderLabels([
            _("osc_address_tab.address_name"),
            _("osc_address_tab.action_name"),
            _("osc_address_tab.status")
        ])
        
        # 更新按钮文本
        self.add_binding_btn.setText("添加绑定")
        self.delete_binding_btn.setText("删除绑定")
        self.refresh_btn.setText(_("osc_address_tab.refresh"))
        self.save_config_btn.setText(_("osc_address_tab.save_config"))
        
        # 刷新表格内容以更新状态列
        self.refresh_binding_table()


class OSCAddressTab(QWidget):
    """OSC地址管理面板 - 包含地址列表和绑定管理的标签页"""
    
    def __init__(self, ui_callback: UIInterface) -> None:
        super().__init__()
        self.ui_callback: UIInterface = ui_callback
        
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
        self.address_list_tab = OSCAddressListTab(self.ui_callback)
        self.tab_widget.addTab(self.address_list_tab, _("osc_address_tab.address_list"))
        
        # 地址绑定标签页
        self.address_binding_tab = OSCAddressBindingTab(self.ui_callback)
        self.tab_widget.addTab(self.address_binding_tab, _("osc_address_tab.address_binding"))
        
        layout.addWidget(self.tab_widget)
    
    def set_registries(self, address_registry: OSCAddressRegistry, 
                      action_registry: OSCActionRegistry, 
                      address_bindings: OSCBindingRegistry) -> None:
        """设置注册表引用"""
        self.address_list_tab.set_address_registry(address_registry)
        self.address_binding_tab.set_registries(address_registry, action_registry, address_bindings)
    
    def set_options_provider(self, options_provider: OSCOptionsProvider) -> None:
        """设置下拉列表数据提供者"""
        self.address_list_tab.set_options_provider(options_provider)
        self.address_binding_tab.set_options_provider(options_provider)
    
    def update_ui_texts(self) -> None:
        """更新UI文本"""
        # 更新内部标签页标题
        self.tab_widget.setTabText(0, _("osc_address_tab.address_list"))
        self.tab_widget.setTabText(1, _("osc_address_tab.address_binding"))
        
        # 更新子标签页的文本
        self.address_list_tab.update_ui_texts()
        self.address_binding_tab.update_ui_texts()