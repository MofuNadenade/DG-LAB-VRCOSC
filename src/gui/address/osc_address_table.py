import logging
from typing import Optional, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QGroupBox, QFormLayout, QLabel,
    QHeaderView, QMessageBox, QDialog, QDialogButtonBox
)

from core import OSCOptionsProvider
from core.osc_common import OSCAddress
from core.registries import Registries
from i18n import translate, language_signals
from ..ui_interface import UIInterface
from ..widgets import OSCAddressTableDelegate, EditableComboBox

logger = logging.getLogger(__name__)


class AddAddressDialog(QDialog):
    """添加OSC地址的对话框"""

    def __init__(self, parent: Optional[QWidget], options_provider: OSCOptionsProvider) -> None:
        super().__init__(parent)
        self.options_provider = options_provider

        # UI组件类型注解
        self.name_combo: EditableComboBox
        self.code_combo: EditableComboBox

        self.setWindowTitle(translate("osc_address_tab.add_address"))
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


class OSCAddressTableTab(QWidget):
    """OSC地址列表标签页"""

    def __init__(self, ui_interface: UIInterface, registries: Registries, options_provider: OSCOptionsProvider) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.registries: Registries = registries
        self.options_provider: OSCOptionsProvider = options_provider

        # UI组件类型注解
        self.address_table: QTableWidget
        self.add_address_btn: QPushButton
        self.delete_address_btn: QPushButton
        self.refresh_btn: QPushButton
        self.save_addresses_btn: QPushButton
        self.status_label: QLabel
        self.address_list_group: QGroupBox

        self.init_ui()

        # 设置表格代理以启用下拉列表编辑
        delegate = OSCAddressTableDelegate(self.options_provider)
        self.address_table.setItemDelegate(delegate)

        # 连接数据变化信号
        self.address_table.itemChanged.connect(self.on_item_changed)

        # 初始化表格数据 - 从registries加载
        self.refresh_address_table()

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

        # 地址表格 - 4列：ID(隐藏)、名称、OSC代码、状态
        self.address_table = QTableWidget()
        self.address_table.setColumnCount(4)
        self.address_table.setHorizontalHeaderLabels([
            translate("osc_address_tab.id"),
            translate("osc_address_tab.address_name"),
            translate("osc_address_tab.osc_code"),
            translate("osc_address_tab.status")
        ])

        # 隐藏ID列
        self.address_table.setColumnHidden(0, True)

        # 设置表格属性
        header = self.address_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # 名称列拉伸
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # 代码列拉伸
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # 状态列固定宽度
        header.resizeSection(3, 100)  # 状态列宽度100px

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
                color: #2e7d32;
                font-size: 12px;
                padding: 5px;
                font-weight: bold;
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

    def refresh_address_table(self) -> None:
        """刷新地址表格 - 从registries重新加载数据"""
        # 阻塞信号避免在刷新时触发itemChanged
        self.address_table.blockSignals(True)
        
        addresses = self.registries.address_registry.addresses
        self.address_table.setRowCount(len(addresses))

        for row, addr in enumerate(addresses):
            self.update_address(row, addr)

        # 恢复信号连接
        self.address_table.blockSignals(False)

        # 更新状态标签
        total_count = len(addresses)
        self.status_label.setText(translate("osc_address_tab.total_addresses").format(total_count))
        logger.info(f"Refreshed address table with {total_count} addresses from registries")

    def save_addresses(self) -> None:
        """增量保存到registry"""
        try:
            modified_rows = self.get_modified_rows()
            
            if not modified_rows:
                QMessageBox.information(self, translate("osc_address_tab.info"),
                                        translate("osc_address_tab.no_changes_to_save"))
                return
            
            for row in modified_rows:
                id_item = self.address_table.item(row, 0)
                name_item = self.address_table.item(row, 1)
                code_item = self.address_table.item(row, 2)
                
                if not id_item or not name_item or not code_item:
                    continue
                    
                address_id = int(id_item.text())
                name = name_item.text().strip()
                code = code_item.text().strip()
                
                if address_id == -1:  # 新增地址
                    self._handle_new_address(row, name, code)
                else:  # 更新地址
                    self._handle_update_address(row, address_id, name, code)
                
                # 标记为已保存
                self.mark_row_as_saved(row)
            
            # 保存配置
            self._save_config()
            
            # 显示成功消息
            QMessageBox.information(self, translate("osc_address_tab.success"),
                                    translate("osc_address_tab.addresses_saved").format(len(modified_rows)))
                                    
        except Exception as e:
            logger.error(f"Failed to save addresses: {e}")
            QMessageBox.critical(self, translate("osc_address_tab.error"),
                                 translate("osc_address_tab.save_addresses_failed").format(str(e)))

    def _handle_new_address(self, row: int, name: str, code: str) -> None:
        """处理新增地址"""
        new_address = self.registries.address_registry.register_address(name, code)
        # 更新ID列为新分配的ID
        id_item = self.address_table.item(row, 0)
        if id_item:
            id_item.setText(str(new_address.id))
        logger.info(f"Added new address: {name} -> {code} with ID {new_address.id}")

    def _handle_update_address(self, row: int, address_id: int, name: str, code: str) -> None:
        """处理更新地址"""
        name_item = self.address_table.item(row, 1)
        code_item = self.address_table.item(row, 2)
        
        # 检查名称是否变化
        if name_item and name_item.data(Qt.ItemDataRole.UserRole) == True:
            self.registries.address_registry.update_address_name(address_id, name)
            logger.info(f"Updated address {address_id} name to: {name}")
        
        # 检查代码是否变化
        if code_item and code_item.data(Qt.ItemDataRole.UserRole) == True:
            self.registries.address_registry.update_address_code(address_id, code)
            logger.info(f"Updated address {address_id} code to: {code}")

    def _save_config(self) -> None:
        """保存配置到文件"""
        # 导出所有地址
        all_addresses = self.registries.address_registry.export_to_config()

        # 更新settings
        self.ui_interface.settings['addresses'] = all_addresses

        # 保存到文件
        self.ui_interface.save_settings()
        logger.info(f"Saved {len(all_addresses)} addresses to config")

    def update_address(self, row: int, addr: OSCAddress) -> None:
        """更新表格中的地址行"""
        # ID列（隐藏）
        id_item = QTableWidgetItem(str(addr.id))
        id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.address_table.setItem(row, 0, id_item)
        
        # 地址名 - 存储原始值用于比较
        name_item = QTableWidgetItem(addr.name)
        name_item.setData(Qt.ItemDataRole.UserRole, False)  # 初始未修改
        self.address_table.setItem(row, 1, name_item)
        
        # OSC代码 - 存储原始值用于比较
        code_item = QTableWidgetItem(addr.code)
        code_item.setData(Qt.ItemDataRole.UserRole, False)  # 初始未修改
        self.address_table.setItem(row, 2, code_item)
        
        # 状态列 - 所有地址都显示为可用状态
        status_item = QTableWidgetItem(translate("osc_address_tab.available"))
        # 设置状态列样式为绿色
        status_item.setBackground(QColor(144, 238, 144))  # 浅绿色背景
        status_item.setForeground(QColor(0, 128, 0))  # 深绿色文字
        # 状态列不可编辑
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.address_table.setItem(row, 3, status_item)

    def add_address(self) -> None:
        """添加新地址 - 直接添加到address_table"""
        dialog = AddAddressDialog(self, self.options_provider)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.validate_input():
                name, code = dialog.get_address_data()

                # 检查表格中是否已存在相同名称
                if self.has_address_name_in_table(name):
                    QMessageBox.warning(self, translate("osc_address_tab.error"),
                                        translate("osc_address_tab.address_exists"))
                    return

                # 检查表格中是否已存在相同代码
                if self.has_address_code_in_table(code):
                    QMessageBox.warning(self, translate("osc_address_tab.error"),
                                        translate("osc_address_tab.code_exists"))
                    return

                # 直接添加到表格
                row = self.address_table.rowCount()
                self.address_table.insertRow(row)
                
                # 创建新的地址项
                id_item = QTableWidgetItem(str(-1))  # 临时ID，保存时会重新生成
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                name_item = QTableWidgetItem(name)
                code_item = QTableWidgetItem(code)
                status_item = QTableWidgetItem(translate("osc_address_tab.available"))
                
                # 设置修改标记为True（新增项目）
                name_item.setData(Qt.ItemDataRole.UserRole, True)
                code_item.setData(Qt.ItemDataRole.UserRole, True)
                
                # 设置状态列样式
                status_item.setBackground(QColor(144, 238, 144))
                status_item.setForeground(QColor(0, 128, 0))
                status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                # 添加到表格
                self.address_table.setItem(row, 0, id_item)
                self.address_table.setItem(row, 1, name_item)
                self.address_table.setItem(row, 2, code_item)
                self.address_table.setItem(row, 3, status_item)

                # 更新状态标签
                total_count = self.address_table.rowCount()
                self.status_label.setText(translate("osc_address_tab.total_addresses").format(total_count))

                logger.info(f"Added OSC address to table: {name} -> {code}")

                # 显示成功消息
                QMessageBox.information(self, translate("osc_address_tab.success"),
                                        translate("osc_address_tab.address_added").format(name))

    def delete_address(self) -> None:
        """删除选中的地址"""
        current_row = self.address_table.currentRow()
        if current_row < 0:
            return

        # 获取选中的地址名称
        address_name_item = self.address_table.item(current_row, 1)
        if not address_name_item:
            return

        address_name = address_name_item.text()

        # 获取地址ID
        id_item = self.address_table.item(current_row, 0)
        if not id_item:
            return
        address_id = int(id_item.text())

        # 确认删除
        reply = QMessageBox.question(self, translate("osc_address_tab.confirm_delete"),
                                     translate("osc_address_tab.delete_address_confirm").format(address_name),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # 如果ID > 0，从registry删除
            if address_id > 0:
                self.registries.address_registry.unregister_address(address_id)
                logger.info(f"Deleted address from registry: ID {address_id}")

            # 从表格删除行
            self.address_table.removeRow(current_row)

            # 更新状态标签
            total_count = self.address_table.rowCount()
            self.status_label.setText(translate("osc_address_tab.total_addresses").format(total_count))

            logger.info(f"Deleted OSC address from table: {address_name}")

            # 显示成功消息
            QMessageBox.information(self, translate("osc_address_tab.success"),
                                    translate("osc_address_tab.address_deleted").format(address_name))

    def has_address_name_in_table(self, name: str) -> bool:
        """检查表格中是否已存在相同名称的地址"""
        for row in range(self.address_table.rowCount()):
            name_item = self.address_table.item(row, 1)
            if name_item and name_item.text().strip() == name:
                return True
        return False

    def has_address_code_in_table(self, code: str) -> bool:
        """检查表格中是否已存在相同代码的地址"""
        for row in range(self.address_table.rowCount()):
            code_item = self.address_table.item(row, 2)
            if code_item and code_item.text().strip() == code:
                return True
        return False

    def on_address_selection_changed(self) -> None:
        """地址选择变化时的处理"""
        has_selection = len(self.address_table.selectedItems()) > 0
        self.delete_address_btn.setEnabled(has_selection)

    def on_item_changed(self, item: QTableWidgetItem) -> None:
        """当表格项数据变化时自动标记"""
        if item.column() in [1, 2]:  # 名称和代码列
            # 标记为已修改
            item.setData(Qt.ItemDataRole.UserRole, True)
            
            # 高亮显示修改的行
            self.highlight_modified_row(item.row())

    def highlight_modified_row(self, row: int) -> None:
        """高亮显示修改的行"""
        for col in range(self.address_table.columnCount()):
            item = self.address_table.item(row, col)
            if item and item.data(Qt.ItemDataRole.UserRole) == True:
                # 设置背景色为浅黄色表示已修改
                item.setBackground(QColor(255, 255, 200))

    def is_item_modified(self, item: QTableWidgetItem) -> bool:
        """检查表格项是否被修改"""
        return item.data(Qt.ItemDataRole.UserRole) == True

    def is_row_modified(self, row: int) -> bool:
        """检查指定行是否被修改"""
        name_item = self.address_table.item(row, 1)
        code_item = self.address_table.item(row, 2)
        
        name_modified = name_item and self.is_item_modified(name_item)
        code_modified = code_item and self.is_item_modified(code_item)
        
        return bool(name_modified or code_modified)

    def get_modified_rows(self) -> List[int]:
        """获取所有修改过的行"""
        return [row for row in range(self.address_table.rowCount()) 
                if self.is_row_modified(row)]

    def get_modified_count(self) -> int:
        """获取修改过的行数"""
        return len(self.get_modified_rows())

    def mark_row_as_saved(self, row: int) -> None:
        """标记行为已保存"""
        name_item = self.address_table.item(row, 1)
        code_item = self.address_table.item(row, 2)
        
        # 重置修改标记
        if name_item:
            name_item.setData(Qt.ItemDataRole.UserRole, False)
            name_item.setBackground(Qt.GlobalColor.white)
        if code_item:
            code_item.setData(Qt.ItemDataRole.UserRole, False)
            code_item.setBackground(Qt.GlobalColor.white)

    def reset_all_modifications(self) -> None:
        """重置所有修改标记"""
        for row in range(self.address_table.rowCount()):
            self.mark_row_as_saved(row)

    def update_ui_texts(self) -> None:
        """更新UI文本"""
        # 更新分组框标题
        self.address_list_group.setTitle(translate("osc_address_tab.address_list"))

        # 更新表格标题
        self.address_table.setHorizontalHeaderLabels([
            translate("osc_address_tab.id"),
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