from typing import Any, List, Optional, Union

from PySide6.QtCore import Qt, QModelIndex, QPersistentModelIndex
from PySide6.QtWidgets import QComboBox, QWidget, QStyledItemDelegate

from core import OSCOptionsProvider


class StyledComboBox(QComboBox):
    """统一样式的下拉框基类"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._apply_style()

    def _apply_style(self) -> None:
        """应用统一样式"""
        self.setStyleSheet("""
            QComboBox {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 14px;
                min-height: 20px;
                background-color: white;
                color: #333;
            }
            QComboBox:hover {
                border-color: #999;
            }
            QComboBox:focus {
                border-color: #0078d4;
                outline: none;
            }
            QComboBox:disabled {
                background-color: #f5f5f5;
                color: #999;
                border-color: #ddd;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #ccc;
                background-color: white;
                selection-background-color: #e3f2fd;
                selection-color: #333;
                outline: none;
                font-size: 14px;
            }
            QComboBox QAbstractItemView::item {
                padding: 6px 8px;
                border: none;
                color: #333;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #e3f2fd;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #f0f8ff;
            }
        """)


class EditableComboBox(StyledComboBox):
    """可编辑的下拉框，支持快速选择和手动输入"""

    MANUAL_INPUT_TEXT = "[手动输入...]"

    def __init__(self, options: List[str], parent: Optional[QWidget] = None,
                 allow_manual_input: bool = True) -> None:
        super().__init__(parent)
        self.allow_manual_input = allow_manual_input

        # 设置可编辑性
        self.setEditable(allow_manual_input)
        if allow_manual_input:
            self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            # 连接信号处理手动输入
            self.currentTextChanged.connect(self._on_text_changed)

        # 添加选项
        self.set_options(options)

    def set_options(self, options: List[str]) -> None:
        """设置下拉选项"""
        self.clear()
        self.addItems(options)

        # 如果允许手动输入且选项中没有手动输入提示，则添加
        if (self.allow_manual_input and
                EditableComboBox.MANUAL_INPUT_TEXT not in options and
                options):  # 只有当有其他选项时才添加
            self.addItem(EditableComboBox.MANUAL_INPUT_TEXT)

    def _on_text_changed(self, text: str) -> None:
        """处理文本改变事件"""
        if text == EditableComboBox.MANUAL_INPUT_TEXT:
            # 清空文本，让用户输入
            self.clearEditText()
            line_edit = self.lineEdit()
            if line_edit:
                line_edit.setFocus()


class OSCAddressTableDelegate(QStyledItemDelegate):
    """OSC地址表格的自定义代理"""

    def __init__(self, options_provider: OSCOptionsProvider, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.options_provider = options_provider

    def createEditor(self, parent: QWidget, option: Any, index: Union[QModelIndex, QPersistentModelIndex]) -> QWidget:
        """创建编辑器"""
        column = index.column()

        if column == 0:  # 地址名称列
            options = self.options_provider.get_address_name_options()
            return EditableComboBox(options, parent, allow_manual_input=True)
        elif column == 1:  # OSC代码列  
            options = self.options_provider.get_osc_code_options()
            return EditableComboBox(options, parent, allow_manual_input=True)
        else:
            return super().createEditor(parent, option, index)

    def setEditorData(self, editor: QWidget, index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        """设置编辑器数据"""
        if isinstance(editor, EditableComboBox):
            text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
            if text:
                # 尝试在下拉列表中找到匹配项
                idx = editor.findText(text)
                if idx >= 0:
                    editor.setCurrentIndex(idx)
                else:
                    # 如果没找到，直接设置文本
                    editor.setCurrentText(text)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor: QWidget, model: Any, index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        """将编辑器数据设置到模型"""
        if isinstance(editor, EditableComboBox):
            text = editor.currentText()
            model.setData(index, text, Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)


class OSCBindingTableDelegate(QStyledItemDelegate):
    """OSC地址绑定表格的自定义代理 - 只允许选择预定义选项"""

    def __init__(self, options_provider: OSCOptionsProvider, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.options_provider = options_provider

    def createEditor(self, parent: QWidget, option: Any, index: Union[QModelIndex, QPersistentModelIndex]) -> QWidget:
        """创建编辑器"""
        column = index.column()

        if column == 0:  # 地址名称列 - 只能选择预定义地址
            options = self.options_provider.get_address_name_options()
            return EditableComboBox(options, parent, allow_manual_input=False)
        elif column == 1:  # 动作名称列 - 只能选择预定义动作
            options = self.options_provider.get_action_name_options()
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
        """将编辑器数据设置到模型"""
        if isinstance(editor, EditableComboBox):
            text = editor.currentText()
            model.setData(index, text, Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)
