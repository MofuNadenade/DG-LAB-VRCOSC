from typing import List, Optional

from PySide6.QtWidgets import QComboBox, QWidget


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
