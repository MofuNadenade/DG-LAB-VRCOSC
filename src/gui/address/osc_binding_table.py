import logging
from typing import Optional, Any, Union

from PySide6.QtCore import Qt, QModelIndex, QPersistentModelIndex
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QGroupBox, QFormLayout, QLabel,
    QHeaderView, QMessageBox, QDialog, QDialogButtonBox, QComboBox, QStyledItemDelegate
)

from core import OSCOptionsProvider
from core.osc_common import OSCAction, OSCAddress, OSCBinding
from core.registries import Registries
from i18n import translate, language_signals
from ..ui_interface import UIInterface
from ..widgets import EditableComboBox, EditState
from ..styles import CommonColors

logger = logging.getLogger(__name__)


class AddBindingDialog(QDialog):
    """添加OSC地址绑定的对话框"""

    def __init__(self, parent: Optional[QWidget], registries: Registries) -> None:
        super().__init__(parent)
        self.registries = registries

        # UI组件类型注解
        self.address_combo: QComboBox
        self.action_combo: QComboBox

        self.setWindowTitle(translate("tabs.osc.add_binding"))
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
        self.address_combo = EditableComboBox(address_options, allow_manual_input=False)
        form_layout.addRow(translate("tabs.osc.address_name_label"), self.address_combo)

        # 动作选择
        action_options = [action.name for action in self.registries.action_registry.actions]
        self.action_combo = EditableComboBox(action_options, allow_manual_input=False)
        form_layout.addRow(translate("tabs.osc.action_name_label"), self.action_combo)

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
        self.setWindowTitle(translate("tabs.osc.add_binding"))

    def get_binding_data(self) -> tuple[str, str]:
        """获取选中的绑定数据"""
        return self.address_combo.currentText(), self.action_combo.currentText()

    def validate_input(self) -> bool:
        """验证输入"""
        address_name, action_name = self.get_binding_data()
        if not address_name or not action_name:
            QMessageBox.warning(self, translate("tabs.osc.input_error"),
                                translate("tabs.osc.select_address_action"))
            return False
        return True


class OSCBindingTableTab(QWidget):
    """OSC地址绑定标签页"""

    def __init__(self, ui_interface: UIInterface, registries: Registries, options_provider: OSCOptionsProvider) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.registries: Registries = registries
        self.options_provider: OSCOptionsProvider = options_provider

        # UI组件类型注解
        self.binding_table: QTableWidget
        self.add_binding_btn: QPushButton
        self.delete_binding_btn: QPushButton
        self.refresh_btn: QPushButton
        self.save_config_btn: QPushButton
        self.binding_status_label: QLabel
        self.binding_list_group: QGroupBox
        self.description_label: QLabel

        self.init_ui()

        # 设置表格代理以启用下拉列表编辑
        delegate = OSCBindingTableDelegate(self)
        self.binding_table.setItemDelegate(delegate)

        # 连接数据变化信号
        self.binding_table.itemChanged.connect(self.on_item_changed)

        # 初始化表格数据 - 从registries加载
        self.refresh_binding_table()

        # 连接语言切换信号
        language_signals.language_changed.connect(self.update_ui_texts)

    def init_ui(self) -> None:
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 绑定列表组
        self.create_binding_list_group(layout)

        # 描述标签
        self.create_description_label(layout)

        # 操作按钮组
        self.create_action_buttons_group(layout)

    def create_description_label(self, parent_layout: QVBoxLayout) -> None:
        """创建描述标签"""
        self.description_label = QLabel(translate("tabs.osc.binding_description"))
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

    def create_binding_list_group(self, parent_layout: QVBoxLayout) -> None:
        """创建绑定列表组"""
        self.binding_list_group = QGroupBox(translate("tabs.osc.binding_list"))
        group = self.binding_list_group
        layout = QVBoxLayout(group)

        # 绑定表格 - 6列：ID(隐藏)、地址名、动作名、动作类型、状态、编辑状态(隐藏)
        self.binding_table = QTableWidget()
        self.binding_table.setColumnCount(6)
        self.binding_table.setHorizontalHeaderLabels([
            translate("tabs.osc.id"),
            translate("tabs.osc.address_name"),
            translate("tabs.osc.action_name"),
            translate("tabs.osc.action_types"),
            translate("tabs.osc.status"),
            translate("tabs.osc.edit_state")
        ])

        # 隐藏ID列和编辑状态列
        self.binding_table.setColumnHidden(0, True)
        self.binding_table.setColumnHidden(5, True)

        # 设置表格属性
        header = self.binding_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # 地址名列拉伸
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # 动作名列拉伸
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)   # 动作类型列固定宽度
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)   # 状态列固定宽度
        header.resizeSection(3, 120)  # 动作类型列宽度120px
        header.resizeSection(4, 70)  # 状态列宽度70px

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
        self.binding_status_label = QLabel(translate("tabs.osc.binding_status_all_valid").format(0))
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
        self.add_binding_btn = QPushButton(translate("tabs.osc.add_binding"))
        self.add_binding_btn.clicked.connect(self.add_binding)
        self.add_binding_btn.setStyleSheet(CommonColors.get_primary_button_style())
        self.add_binding_btn.setToolTip(translate("tabs.osc.add_binding_tooltip"))
        button_layout.addWidget(self.add_binding_btn)

        # 删除绑定按钮
        self.delete_binding_btn = QPushButton(translate("tabs.osc.delete_binding"))
        self.delete_binding_btn.clicked.connect(self.delete_binding)
        self.delete_binding_btn.setEnabled(False)
        self.delete_binding_btn.setStyleSheet(CommonColors.get_warning_button_style())
        self.delete_binding_btn.setToolTip(translate("tabs.osc.delete_binding_tooltip"))
        button_layout.addWidget(self.delete_binding_btn)

        # 刷新按钮
        self.refresh_btn = QPushButton(translate("tabs.osc.refresh"))
        self.refresh_btn.clicked.connect(self.refresh_binding_table)
        self.refresh_btn.setStyleSheet(CommonColors.get_secondary_button_style())
        self.refresh_btn.setToolTip(translate("tabs.osc.refresh_binding_tooltip"))
        button_layout.addWidget(self.refresh_btn)

        # 保存配置按钮
        self.save_config_btn = QPushButton(translate("tabs.osc.save_config"))
        self.save_config_btn.clicked.connect(self.save_bindings)
        self.save_config_btn.setStyleSheet(CommonColors.get_special_button_style())
        self.save_config_btn.setToolTip(translate("tabs.osc.save_config_tooltip"))
        button_layout.addWidget(self.save_config_btn)

        button_layout.addStretch()  # 添加弹性空间
        parent_layout.addLayout(button_layout)

        # 连接表格选择变化信号
        self.binding_table.itemSelectionChanged.connect(self.on_binding_selection_changed)

    def refresh_binding_table(self) -> None:
        """刷新绑定表格 - 从registries重新加载数据"""
        # 阻塞信号避免在刷新时触发itemChanged
        self.binding_table.blockSignals(True)

        # 清空表格
        self.binding_table.setRowCount(0)
        
        bindings: list[OSCBinding] = self.registries.binding_registry.bindings
        self.binding_table.setRowCount(len(bindings))

        for row, binding in enumerate(bindings):
            self.update_binding(row, binding)

        # 恢复信号连接
        self.binding_table.blockSignals(False)

        # 更新状态标签
        self.update_binding_status_label()

    def save_bindings(self) -> None:
        """增量保存到registry"""
        try:
            for row in range(self.binding_table.rowCount()):
                edit_state_item = self.binding_table.item(row, 5)
                if not edit_state_item:
                    continue
                    
                edit_state = edit_state_item.text()
                
                if edit_state == EditState.NEW.value:
                    # 处理新增
                    self._handle_new_binding(row)
                elif edit_state == EditState.MODIFIED.value:
                    # 处理修改
                    self._handle_update_binding(row)
                elif edit_state == EditState.DELETED.value:
                    # 处理删除
                    self._handle_delete_binding(row)
            
            # 保存配置
            self._save_config()

            # 刷新表格
            self.refresh_binding_table()
            
            # 显示成功消息
            QMessageBox.information(self, translate("common.success"),
                                    translate("tabs.osc.config_saved"))
                                    
        except Exception as e:
            logger.error(f"Failed to save bindings: {e}")
            QMessageBox.critical(self, translate("common.error"),
                                 translate("tabs.osc.save_config_failed").format(str(e)))

    def _handle_new_binding(self, row: int) -> None:
        """处理新增绑定"""
        address_name_item = self.binding_table.item(row, 1)
        action_name_item = self.binding_table.item(row, 2)
        
        if not address_name_item or not action_name_item:
            return
            
        address_name = address_name_item.text().strip()
        action_name = action_name_item.text().strip()
        
        address = self.registries.address_registry.get_address_by_name(address_name)
        action = self.registries.action_registry.get_action_by_name(action_name)
        
        if address and action:
            new_binding = self.registries.binding_registry.register_binding(address, action)
            # 更新ID列为新分配的ID
            id_item = self.binding_table.item(row, 0)
            if id_item:
                id_item.setText(str(new_binding.id))
            logger.info(f"Added new binding: {address_name} -> {action_name} with ID {new_binding.id}")

    def _handle_update_binding(self, row: int) -> None:
        """处理更新绑定"""
        id_item = self.binding_table.item(row, 0)
        address_name_item = self.binding_table.item(row, 1)
        action_name_item = self.binding_table.item(row, 2)
        
        if not id_item or not address_name_item or not action_name_item:
            return
            
        binding_id = int(id_item.text())
        address_name = address_name_item.text().strip()
        action_name = action_name_item.text().strip()

        new_address = self.registries.address_registry.get_address_by_name(address_name)
        if new_address:
            self.registries.binding_registry.update_binding_address(binding_id, new_address)

        new_action = self.registries.action_registry.get_action_by_name(action_name)
        if new_action:
            self.registries.binding_registry.update_binding_action(binding_id, new_action)

    def _handle_delete_binding(self, row: int) -> None:
        """处理删除绑定"""
        id_item = self.binding_table.item(row, 0)
        if not id_item:
            return
            
        binding_id = int(id_item.text())
        if binding_id > 0:
            # 从registry删除
            binding = self.registries.binding_registry.get_binding_by_id(binding_id)
            if binding:
                self.registries.binding_registry.unregister_binding(binding.address)
                logger.info(f"Deleted binding from registry: ID {binding_id}")

    def _save_config(self) -> None:
        """保存配置到文件"""
        # 导出所有绑定
        all_bindings = self.registries.binding_registry.export_to_config()

        # 更新settings
        self.ui_interface.settings['bindings'] = all_bindings

        # 保存到文件
        self.ui_interface.save_settings()
        logger.info(f"Saved {len(all_bindings)} bindings to config")

    def update_binding(self, row: int, binding: OSCBinding) -> None:
        """更新表格中的绑定行"""
        # 验证绑定有效性
        is_valid, error_msg = self.validate_binding(binding.address, binding.action)
        
        # ID列（隐藏）
        id_item = QTableWidgetItem(str(binding.id))
        id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.binding_table.setItem(row, 0, id_item)
        
        # 地址名 - 存储原始值用于比较
        addr_item = QTableWidgetItem(binding.address.name)
        self.binding_table.setItem(row, 1, addr_item)
        
        # 动作名 - 存储原始值用于比较
        action_item = QTableWidgetItem(binding.action.name)
        self.binding_table.setItem(row, 2, action_item)
        
        # 动作类型列 - 显示OSC值类型，用逗号分隔
        action_types_text = ", ".join([t.value_type().value for t in binding.action.types])
        action_types_item = QTableWidgetItem(action_types_text)
        action_types_item.setFlags(action_types_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.binding_table.setItem(row, 3, action_types_item)
        
        # 状态列
        if is_valid:
            status_text = translate("tabs.osc.available")
            status_item = QTableWidgetItem(status_text)
            # 有效绑定：明显的绿色背景
            status_item.setBackground(QColor(144, 238, 144))  # 浅绿色
            status_item.setForeground(QColor(0, 128, 0))  # 深绿色文字
            status_item.setToolTip(translate("tabs.osc.binding_valid_tooltip"))

            # 为有效绑定的行设置正常样式
            addr_item.setBackground(Qt.GlobalColor.white)
            action_item.setBackground(Qt.GlobalColor.white)
        else:
            status_text = translate("tabs.osc.invalid")
            status_item = QTableWidgetItem(status_text)
            # 无效绑定：浅红色背景
            status_item.setBackground(QColor(255, 200, 200))  # 浅红色
            status_item.setForeground(QColor(150, 0, 0))  # 深红色文字
            status_item.setToolTip(translate("tabs.osc.binding_invalid").format(error_msg))

            # 为无效绑定的行设置警告样式
            addr_item.setBackground(QColor(240, 240, 240))  # 浅灰色
            action_item.setBackground(QColor(240, 240, 240))  # 浅灰色
            addr_item.setForeground(QColor(150, 0, 0))  # 深红色文字
            action_item.setForeground(QColor(150, 0, 0))  # 深红色文字

        # 状态列不可编辑
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.binding_table.setItem(row, 4, status_item)
        
        # 编辑状态列（隐藏）
        edit_state_item = QTableWidgetItem(EditState.NONE.value)
        edit_state_item.setFlags(edit_state_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.binding_table.setItem(row, 5, edit_state_item)

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
        if not address.name or not address.name.strip():
            return False, "地址名称为空"
        if not address.code or not address.code.strip():
            return False, "OSC代码为空"

        # 验证动作对象的有效性
        if not action.name or not action.name.strip():
            return False, "动作名称为空"

        # 检查对象是否仍然在注册表中
        if not self.registries.address_registry.has_address_name(address.name):
            return False, f"地址'{address.name}'不存在于注册表中"
        if not self.registries.action_registry.has_action_name(action.name):
            return False, f"动作'{action.name}'不存在于注册表中"

        return True, ""

    def add_binding(self) -> None:
        """添加新的地址绑定 - 直接添加到binding_table"""
        dialog = AddBindingDialog(self, self.registries)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.validate_input():
                address_name, action_name = dialog.get_binding_data()

                # 获取地址和动作对象
                address = self.registries.address_registry.get_address_by_name(address_name)
                action = self.registries.action_registry.get_action_by_name(action_name)

                if not address or not action:
                    QMessageBox.critical(self, translate("common.error"),
                                         translate("tabs.osc.address_action_not_found").format(address_name,
                                                                                                      action_name))
                    return
                
                # 阻塞信号避免在刷新时触发itemChanged
                self.binding_table.blockSignals(True)

                # 直接添加到表格
                row = self.binding_table.rowCount()
                self.binding_table.setRowCount(row + 1)
                
                # 创建新的绑定项
                id_item = QTableWidgetItem(str(-1))  # 临时ID，保存时会重新生成
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                addr_item = QTableWidgetItem(address_name)
                action_item = QTableWidgetItem(action_name)
                
                # 验证绑定有效性并设置状态
                is_valid, error_msg = self.validate_binding(address, action)
                if is_valid:
                    status_text = translate("tabs.osc.available")
                    status_item = QTableWidgetItem(status_text)
                    status_item.setBackground(QColor(144, 238, 144))
                    status_item.setForeground(QColor(0, 128, 0))
                    status_item.setToolTip(translate("tabs.osc.binding_valid_tooltip"))
                else:
                    status_text = translate("tabs.osc.invalid")
                    status_item = QTableWidgetItem(status_text)
                    status_item.setBackground(QColor(255, 200, 200))
                    status_item.setForeground(QColor(150, 0, 0))
                    status_item.setToolTip(translate("tabs.osc.binding_invalid").format(error_msg))
                    
                    # 为无效绑定的行设置警告样式
                    addr_item.setBackground(QColor(240, 240, 240))
                    action_item.setBackground(QColor(240, 240, 240))
                    addr_item.setForeground(QColor(150, 0, 0))
                    action_item.setForeground(QColor(150, 0, 0))
                
                # 状态列不可编辑
                status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                # 动作类型列 - 显示OSC值类型，用逗号分隔
                action_types_text = ", ".join([t.value_type().value for t in action.types])
                action_types_item = QTableWidgetItem(action_types_text)
                action_types_item.setFlags(action_types_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                # 编辑状态列设置为新增状态
                edit_state_item = QTableWidgetItem(EditState.NEW.value)
                edit_state_item.setFlags(edit_state_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                # 添加到表格
                self.binding_table.setItem(row, 0, id_item)
                self.binding_table.setItem(row, 1, addr_item)
                self.binding_table.setItem(row, 2, action_item)
                self.binding_table.setItem(row, 3, action_types_item)
                self.binding_table.setItem(row, 4, status_item)
                self.binding_table.setItem(row, 5, edit_state_item)

                # 高亮显示修改的行
                self.update_highlight_row(row)

                # 恢复信号连接
                self.binding_table.blockSignals(False)

                # 更新状态标签
                self.update_binding_status_label()

                logger.info(f"Added binding to table: {address_name} -> {action_name}")

                # 显示成功消息
                QMessageBox.information(self, translate("common.success"),
                                        translate("tabs.osc.binding_added").format(address_name,
                                                                                          action_name))

    def delete_binding(self) -> None:
        """删除选中的地址绑定"""
        current_row = self.binding_table.currentRow()
        if current_row < 0:
            return

        # 获取选中的绑定信息
        address_name_item = self.binding_table.item(current_row, 1)
        action_name_item = self.binding_table.item(current_row, 2)
        
        if not address_name_item or not action_name_item:
            return

        address_name = address_name_item.text()
        action_name = action_name_item.text()

        # 确认删除
        reply = QMessageBox.question(self, translate("tabs.osc.confirm_delete"),
                                     translate("tabs.osc.delete_binding_msg").format(address_name, action_name),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # 检查是否为新增状态的绑定
            edit_state_item = self.binding_table.item(current_row, 5)
            if edit_state_item:
                if edit_state_item.text() == EditState.NEW.value:
                    # 如果是新增的绑定，直接删除
                    self.binding_table.removeRow(current_row)
                    logger.info(f"Deleted new binding: {address_name} -> {action_name}")
                else:
                    # 如果是已存在的绑定，标记为删除状态并隐藏
                    edit_state_item.setText(EditState.DELETED.value)
                    
                    # 隐藏行而不是删除
                    self.binding_table.setRowHidden(current_row, True)
                    logger.info(f"Marked binding for deletion: {address_name} -> {action_name}")
            
            # 更新状态标签
            self.update_binding_status_label()

            # 显示成功消息
            QMessageBox.information(self, translate("common.success"),
                                    translate("tabs.osc.binding_deleted").format(address_name, action_name))

    def has_binding_in_table(self, address_name: str, exclude_row: int = -1) -> bool:
        """检查表格中是否已存在相同地址的绑定
        
        Args:
            address_name: 要检查的地址名
            exclude_row: 要排除的行号，-1表示不排除任何行（默认值）
        """
        for row in range(self.binding_table.rowCount()):
            if exclude_row >= 0 and row == exclude_row:
                continue
                
            # 检查编辑状态，忽略已删除的行
            edit_state_item = self.binding_table.item(row, 5)
            if edit_state_item and edit_state_item.text() == EditState.DELETED.value:
                continue
                
            addr_item = self.binding_table.item(row, 1)
            if addr_item and addr_item.text().strip() == address_name:
                return True
        return False

    def update_binding_status_label(self) -> None:
        """更新绑定状态标签"""
        total_count = 0
        valid_count = 0
        invalid_count = 0

        for row in range(self.binding_table.rowCount()):
            # 检查编辑状态，忽略已删除的行
            edit_state_item = self.binding_table.item(row, 5)
            if not edit_state_item or edit_state_item.text() == EditState.DELETED.value:
                continue
                
            address_name_item = self.binding_table.item(row, 1)
            action_name_item = self.binding_table.item(row, 2)
            
            if address_name_item and action_name_item:
                address_name = address_name_item.text().strip()
                action_name = action_name_item.text().strip()
                
                if address_name and action_name:
                    total_count += 1
                    # 获取地址和动作对象进行验证
                    address = self.registries.address_registry.get_address_by_name(address_name)
                    action = self.registries.action_registry.get_action_by_name(action_name)
                    
                    if address and action:
                        is_valid, _ = self.validate_binding(address, action)
                        if is_valid:
                            valid_count += 1
                        else:
                            invalid_count += 1

        # 更新状态标签
        if invalid_count > 0:
            self.binding_status_label.setText(
                translate("tabs.osc.binding_status_with_invalid").format(total_count, valid_count, invalid_count))
            self.binding_status_label.setStyleSheet("""
                QLabel {
                    color: #d32f2f;
                    font-size: 12px;
                    padding: 5px;
                    font-weight: bold;
                }
            """)
        else:
            self.binding_status_label.setText(translate("tabs.osc.binding_status_all_valid").format(total_count))
            self.binding_status_label.setStyleSheet("""
                QLabel {
                    color: #2e7d32;
                    font-size: 12px;
                    padding: 5px;
                    font-weight: bold;
                }
            """)

    def on_binding_selection_changed(self) -> None:
        """绑定选择变化时的处理"""
        has_selection = len(self.binding_table.selectedItems()) > 0
        self.delete_binding_btn.setEnabled(has_selection)

    def on_item_changed(self, item: QTableWidgetItem) -> None:
        """当表格项数据变化时自动标记"""
        # 设置编辑状态为修改
        edit_state_item = self.binding_table.item(item.row(), 5)
        if edit_state_item:
            # 获取当前行的编辑状态
            current_state = edit_state_item.text()
            # 如果当前状态为NONE，则设置为MODIFIED
            if current_state == EditState.NONE.value:
                edit_state_item.setText(EditState.MODIFIED.value)        
                # 高亮显示修改的行
                self.update_highlight_row(item.row())

    def update_highlight_row(self, row: int) -> None:
        """高亮显示修改的行"""
        edit_state_item = self.binding_table.item(row, 5)
        if not edit_state_item:
            return
        
        edit_state = edit_state_item.text()
        for col in [1, 2]:
            item = self.binding_table.item(row, col)
            if item:
                if edit_state in [EditState.NEW.value, EditState.MODIFIED.value]:
                    # 设置背景色为浅黄色表示已修改
                    item.setBackground(QColor(255, 255, 200))
                else:
                    item.setBackground(Qt.GlobalColor.white)

    def update_ui_texts(self) -> None:
        """更新UI文本"""
        # 更新分组框标题
        self.binding_list_group.setTitle(translate("tabs.osc.binding_list"))
        
        # 更新描述标签
        self.description_label.setText(translate("tabs.osc.binding_description"))

        # 更新表格标题
        self.binding_table.setHorizontalHeaderLabels([
            translate("tabs.osc.id"),
            translate("tabs.osc.address_name"),
            translate("tabs.osc.action_name"),
            translate("tabs.osc.action_types"),
            translate("tabs.osc.status"),
            translate("tabs.osc.edit_state")
            
        ])

        # 更新按钮文本
        self.add_binding_btn.setText(translate("tabs.osc.add_binding"))
        self.delete_binding_btn.setText(translate("tabs.osc.delete_binding"))
        self.refresh_btn.setText(translate("tabs.osc.refresh"))
        self.save_config_btn.setText(translate("tabs.osc.save_config"))

        # 更新工具提示
        self.add_binding_btn.setToolTip(translate("tabs.osc.add_binding_tooltip"))
        self.delete_binding_btn.setToolTip(translate("tabs.osc.delete_binding_tooltip"))
        self.refresh_btn.setToolTip(translate("tabs.osc.refresh_binding_tooltip"))
        self.save_config_btn.setToolTip(translate("tabs.osc.save_config_tooltip"))

        # 刷新表格内容以更新状态列
        self.refresh_binding_table()


class OSCBindingTableDelegate(QStyledItemDelegate):
    """OSC地址绑定表格的自定义代理 - 只允许选择预定义选项"""

    def __init__(self, binding_tab: OSCBindingTableTab, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.binding_tab = binding_tab

    def createEditor(self, parent: QWidget, option: Any, index: Union[QModelIndex, QPersistentModelIndex]) -> QWidget:
        """创建编辑器"""
        column = index.column()

        if column == 1:  # 地址名称列 - 只能选择预定义地址
            options = self.binding_tab.options_provider.get_address_name_options()
            return EditableComboBox(options, parent, allow_manual_input=False)
        elif column == 2:  # 动作名称列 - 只能选择预定义动作
            options = self.binding_tab.options_provider.get_action_name_options()
            return EditableComboBox(options, parent, allow_manual_input=False)
        else:
            return super().createEditor(parent, option, index)

    def setEditorData(self, editor: QWidget, index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        """设置编辑器数据"""
        if isinstance(editor, EditableComboBox):
            text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
            if text:
                # 在下拉列表中找到匹配项
                idx = editor.findText(text)
                if idx >= 0:
                    editor.setCurrentIndex(idx)
                else:
                    # 如果没找到，设置为第一项
                    editor.setCurrentIndex(0)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor: QWidget, model: Any, index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        """将编辑器数据设置到模型 - 在此处进行冲突验证"""
        if isinstance(editor, EditableComboBox):
            new_text = editor.currentText().strip()
            
            # 没有冲突，正常设置数据
            model.setData(index, new_text, Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)

