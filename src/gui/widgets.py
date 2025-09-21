from typing import List, Optional
from enum import Enum

from PySide6.QtCore import Signal, Property
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QWidget, QHBoxLayout, QPushButton, QButtonGroup


class EditState(Enum):
    """编辑状态枚举"""
    NONE = "none"          # 无变化
    NEW = "new"            # 新增
    MODIFIED = "modified"  # 修改
    DELETED = "deleted"    # 删除（隐藏不显示）


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


class SegmentedControl(QWidget):
    """分段控制器组件
    
    支持两个或多个选项的切换控件
    左右两端为圆角矩形，中间用颜色分隔，点击可切换状态
    
    完全独立的通用组件，支持通过Qt属性系统进行外部配置
    
    可配置属性：
    - selectedColor: 选中状态的背景颜色
    - normalColor: 正常状态的背景颜色  
    - hoverColor: 悬停状态的背景颜色
    - textColor: 文字颜色
    - selectedTextColor: 选中状态的文字颜色
    - borderColor: 边框颜色
    - borderRadius: 圆角半径
    - disabledColor: 禁用状态的背景颜色
    - disabledTextColor: 禁用状态的文字颜色
    - disabledBorderColor: 禁用状态的边框颜色
    """
    
    # ==================== 信号定义 ====================
    
    # 信号：当选择改变时发出，参数为选中的索引
    selectionChanged = Signal(int)
    
    # ==================== 初始化 ====================
    
    def __init__(self, segments: List[str], parent: Optional[QWidget] = None) -> None:
        """初始化分段控制器
        
        Args:
            segments: 分段标签列表，如 ["选项1", "选项2"]
            parent: 父组件
        """
        super().__init__(parent)
        
        if len(segments) < 2:
            raise ValueError("分段控制器至少需要2个选项")
        
        # 组件属性
        self.segments = segments
        self.buttons: List[QPushButton] = []
        self.button_group = QButtonGroup(self)
        
        # 默认颜色配置 - 基于最佳实践优化
        self._selected_color = QColor("#2196F3")      # 蓝色 - 与项目主色调一致
        self._normal_color = QColor("#f8f9fa")        # 浅灰色背景
        self._hover_color = QColor("#e9ecef")         # 悬停灰色
        self._text_color = QColor("#495057")          # 深灰色文字
        self._selected_text_color = QColor("#ffffff") # 白色文字
        self._border_color = QColor("#2196F3")        # 边框颜色 - 与选中色一致
        self._disabled_color = QColor("#f5f5f5")      # 禁用背景颜色
        self._disabled_text_color = QColor("#9ca3af") # 禁用文字颜色
        self._disabled_border_color = QColor("#e5e7eb") # 禁用边框颜色
        self._border_radius = 6                       # 圆角半径 - 精致现代
        
        # 初始化组件
        self._init_ui()
        self._apply_styles()
        self._connect_signals()
        
        # 默认选中第一个
        self.set_selected_index(0)
    
    # ==================== 公共接口方法 ====================
    
    def get_selected_index(self) -> int:
        """获取当前选中的索引"""
        for i, button in enumerate(self.buttons):
            if button.isChecked():
                return i
        return -1
    
    def set_selected_index(self, index: int) -> None:
        """设置选中的索引"""
        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)
    
    def get_selected_text(self) -> str:
        """获取当前选中的文本"""
        index = self.get_selected_index()
        if index >= 0:
            return self.segments[index]
        return ""
    
    def update_segments(self, segments: List[str]) -> None:
        """更新分段标签文本"""
        if len(segments) != len(self.segments):
            raise ValueError("新分段数量必须与原分段数量一致")
        
        # 保存当前选中状态
        current_index = self.get_selected_index()
        
        # 更新分段文本
        self.segments = segments
        for i, button in enumerate(self.buttons):
            button.setText(segments[i])
        
        # 恢复选中状态
        if current_index >= 0:
            self.set_selected_index(current_index)
    
    # ==================== 颜色配置方法 ====================
    
    def get_selected_color(self) -> QColor:
        """获取选中状态的背景颜色"""
        return self._selected_color
    
    def set_selected_color(self, color: QColor) -> None:
        """设置选中状态的背景颜色"""
        if self._selected_color != color:
            self._selected_color = color
            self._apply_styles()
    
    def get_normal_color(self) -> QColor:
        """获取正常状态的背景颜色"""
        return self._normal_color
    
    def set_normal_color(self, color: QColor) -> None:
        """设置正常状态的背景颜色"""
        if self._normal_color != color:
            self._normal_color = color
            self._apply_styles()
    
    def get_hover_color(self) -> QColor:
        """获取悬停状态的背景颜色"""
        return self._hover_color
    
    def set_hover_color(self, color: QColor) -> None:
        """设置悬停状态的背景颜色"""
        if self._hover_color != color:
            self._hover_color = color
            self._apply_styles()
    
    def get_text_color(self) -> QColor:
        """获取文字颜色"""
        return self._text_color
    
    def set_text_color(self, color: QColor) -> None:
        """设置文字颜色"""
        if self._text_color != color:
            self._text_color = color
            self._apply_styles()
    
    def get_selected_text_color(self) -> QColor:
        """获取选中状态的文字颜色"""
        return self._selected_text_color
    
    def set_selected_text_color(self, color: QColor) -> None:
        """设置选中状态的文字颜色"""
        if self._selected_text_color != color:
            self._selected_text_color = color
            self._apply_styles()
    
    def get_border_color(self) -> QColor:
        """获取边框颜色"""
        return self._border_color
    
    def set_border_color(self, color: QColor) -> None:
        """设置边框颜色"""
        if self._border_color != color:
            self._border_color = color
            self._apply_styles()
    
    def get_border_radius(self) -> int:
        """获取圆角半径"""
        return self._border_radius
    
    def set_border_radius(self, radius: int) -> None:
        """设置圆角半径"""
        if self._border_radius != radius:
            self._border_radius = max(0, radius)  # 确保非负
            self._apply_styles()
    
    def get_disabled_color(self) -> QColor:
        """获取禁用状态的背景颜色"""
        return self._disabled_color
    
    def set_disabled_color(self, color: QColor) -> None:
        """设置禁用状态的背景颜色"""
        if self._disabled_color != color:
            self._disabled_color = color
            self._apply_styles()
    
    def get_disabled_text_color(self) -> QColor:
        """获取禁用状态的文字颜色"""
        return self._disabled_text_color
    
    def set_disabled_text_color(self, color: QColor) -> None:
        """设置禁用状态的文字颜色"""
        if self._disabled_text_color != color:
            self._disabled_text_color = color
            self._apply_styles()
    
    def get_disabled_border_color(self) -> QColor:
        """获取禁用状态的边框颜色"""
        return self._disabled_border_color
    
    def set_disabled_border_color(self, color: QColor) -> None:
        """设置禁用状态的边框颜色"""
        if self._disabled_border_color != color:
            self._disabled_border_color = color
            self._apply_styles()
    
    def set_color_scheme(self, selected: str, normal: Optional[str] = None, hover: Optional[str] = None, 
                        text: Optional[str] = None, selected_text: Optional[str] = None, border: Optional[str] = None,
                        disabled: Optional[str] = None, disabled_text: Optional[str] = None, 
                        disabled_border: Optional[str] = None) -> None:
        """批量设置颜色方案
        
        Args:
            selected: 选中状态颜色 (必需)
            normal: 正常状态颜色 (可选)
            hover: 悬停状态颜色 (可选)
            text: 文字颜色 (可选)
            selected_text: 选中文字颜色 (可选)
            border: 边框颜色 (可选)
            disabled: 禁用背景颜色 (可选)
            disabled_text: 禁用文字颜色 (可选)
            disabled_border: 禁用边框颜色 (可选)
        """
        self._selected_color = QColor(selected)
        if normal:
            self._normal_color = QColor(normal)
        if hover:
            self._hover_color = QColor(hover)
        if text:
            self._text_color = QColor(text)
        if selected_text:
            self._selected_text_color = QColor(selected_text)
        if border:
            self._border_color = QColor(border)
        if disabled:
            self._disabled_color = QColor(disabled)
        if disabled_text:
            self._disabled_text_color = QColor(disabled_text)
        if disabled_border:
            self._disabled_border_color = QColor(disabled_border)
        
        self._apply_styles()
    
    # ==================== Qt属性系统 ====================
    
    # 基础颜色属性
    selectedColor = Property(QColor, get_selected_color, set_selected_color)
    normalColor = Property(QColor, get_normal_color, set_normal_color)
    hoverColor = Property(QColor, get_hover_color, set_hover_color)
    textColor = Property(QColor, get_text_color, set_text_color)
    selectedTextColor = Property(QColor, get_selected_text_color, set_selected_text_color)
    borderColor = Property(QColor, get_border_color, set_border_color)
    borderRadius = Property(int, get_border_radius, set_border_radius)
    
    # 禁用状态颜色属性
    disabledColor = Property(QColor, get_disabled_color, set_disabled_color)
    disabledTextColor = Property(QColor, get_disabled_text_color, set_disabled_text_color)
    disabledBorderColor = Property(QColor, get_disabled_border_color, set_disabled_border_color)
    
    # ==================== 私有方法 ====================
    
    def _init_ui(self) -> None:
        """初始化UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)  # 无间距，按钮紧贴
        
        # 创建按钮
        for i, segment in enumerate(self.segments):
            button = QPushButton(segment)
            button.setCheckable(True)
            
            self.buttons.append(button)
            self.button_group.addButton(button, i)
            layout.addWidget(button)
    
    def _connect_signals(self) -> None:
        """连接信号"""
        self.button_group.buttonClicked.connect(self._on_button_clicked)
    
    def _on_button_clicked(self, button: QPushButton) -> None:
        """按钮点击处理"""
        index = self.buttons.index(button)
        self.selectionChanged.emit(index)
    
    def _apply_styles(self) -> None:
        """应用样式"""
        for i, button in enumerate(self.buttons):
            if i == 0:
                # 第一个按钮 - 左侧圆角
                self._apply_button_style(button, "left")
            elif i == len(self.buttons) - 1:
                # 最后一个按钮 - 右侧圆角
                self._apply_button_style(button, "right")
            else:
                # 中间按钮 - 无圆角
                self._apply_button_style(button, "middle")
    
    def _apply_button_style(self, button: QPushButton, position: str) -> None:
        """应用按钮样式
        
        Args:
            button: 按钮对象
            position: 位置类型 ("left", "right", "middle")
        """
        # 根据位置设置圆角
        if position == "left":
            border_radius_style = f"""
                border-top-left-radius: {self._border_radius}px;
                border-bottom-left-radius: {self._border_radius}px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-right: 1px solid {self._border_color.name()};
            """
        elif position == "right":
            border_radius_style = f"""
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: {self._border_radius}px;
                border-bottom-right-radius: {self._border_radius}px;
                border-left: 1px solid {self._border_color.name()};
            """
        else:  # middle
            border_radius_style = f"""
                border-radius: 0px;
                border-left: 1px solid {self._border_color.name()};
                border-right: 1px solid {self._border_color.name()};
            """
        
        # 计算悬停时的选中颜色（稍微变暗）
        hover_selected_color = self._darken_color(self._selected_color)
        
        style = f"""
            QPushButton {{
                border: 2px solid {self._border_color.name()};
                {border_radius_style}
                padding: 4px 8px;
                background-color: {self._normal_color.name()};
                color: {self._text_color.name()};
                font-weight: 500;
                font-size: 12px;
            }}
            QPushButton:hover:!checked {{
                background-color: {self._hover_color.name()};
            }}
            QPushButton:checked {{
                background-color: {self._selected_color.name()};
                color: {self._selected_text_color.name()};
                border-color: {self._selected_color.name()};
            }}
            QPushButton:checked:hover {{
                background-color: {hover_selected_color.name()};
                border-color: {hover_selected_color.name()};
            }}
            QPushButton:disabled {{
                background-color: {self._disabled_color.name()};
                color: {self._disabled_text_color.name()};
                border-color: {self._disabled_border_color.name()};
            }}
        """
        button.setStyleSheet(style)
    
    def _darken_color(self, color: QColor) -> QColor:
        """将颜色变暗"""
        return color.darker(120)  # 使用Qt内置的darker方法
