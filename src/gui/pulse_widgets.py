"""
波形编辑器专用UI组件

基于DG-LAB官方APP界面设计的波形编辑组件
"""

from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QScrollArea, QGroupBox, QMenu, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QTimer, QRect, QPoint, QEvent
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPaintEvent, QMouseEvent, QFont, QLinearGradient

from models import PulseOperation
from i18n import translate, language_signals
import logging

logger = logging.getLogger(__name__)


class PulsePreviewWidget(QWidget):
    """波形预览图组件 - 仿照官方APP样式"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pulse_data: List[PulseOperation] = []
        self.current_step: int = -1
        self.channel_value: int = 0
        self.setMinimumHeight(150)
        self.setMaximumHeight(200)
        
        # 设置样式
        self.setStyleSheet("""
            PulsePreviewWidget {
                background-color: #2b2b2b;
                border: 2px solid #d4af37;
                border-radius: 10px;
            }
        """)
        
        # 动画定时器
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_step = 0
        
    def set_pulse_data(self, data: List[PulseOperation]) -> None:
        """设置波形数据"""
        self.pulse_data = data
        # 如果有数据，初始化显示第一步的强度范围
        if data:
            first_pulse = data[0]
            strength_tuple = first_pulse[1]
            self.channel_value = strength_tuple[0]
        else:
            self.channel_value = 0
        self.update()
        
    def set_current_step(self, step: int) -> None:
        """设置当前高亮步骤"""
        self.current_step = step
        self.update()
        
    def set_channel_value(self, value: int) -> None:
        """设置通道当前值"""
        self.channel_value = value
        self.update()
        
    def start_animation(self) -> None:
        """开始播放动画"""
        self.animation_timer.start(100)  # 100ms间隔
        
    def stop_animation(self) -> None:
        """停止播放动画"""
        self.animation_timer.stop()
        self.animation_step = 0
        self.current_step = -1
        self.update()
        
    def update_animation(self) -> None:
        """更新动画步骤"""
        if self.pulse_data:
            self.animation_step = (self.animation_step + 1) % len(self.pulse_data)
            self.current_step = self.animation_step
            # 更新当前值显示 - 显示当前步骤的强度范围
            current_pulse = self.pulse_data[self.animation_step]
            strength_tuple = current_pulse[1]  # (strength1, strength2, strength3, strength4)
            self.channel_value = strength_tuple[0]
            self.update()
        
    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制波形预览"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 获取绘制区域
        rect = self.rect()
        margin = 20
        draw_rect = QRect(margin, margin, rect.width() - 2*margin, rect.height() - 2*margin)
        
        if not self.pulse_data:
            # 绘制空状态
            painter.setPen(QPen(QColor("#666666"), 1))
            painter.drawText(draw_rect, Qt.AlignmentFlag.AlignCenter, translate("pulse_editor.no_waveform_data"))
            return
            
        # 绘制波形曲线
        self._draw_pulse_curve(painter, draw_rect)
        
        # 绘制通道值显示
        self._draw_channel_value(painter, rect)
        
    def _draw_pulse_curve(self, painter: QPainter, draw_rect: QRect) -> None:
        """绘制波形曲线"""
        if not self.pulse_data:
            return
            
        # 计算点位置
        points: List[QPoint] = []
        step_width = draw_rect.width() / max(len(self.pulse_data) - 1, 1)
        
        for i, pulse in enumerate(self.pulse_data):
            # 使用第一个强度值作为高度
            intensity = pulse[1][0]  # 使用第一个强度参数
            x = draw_rect.left() + i * step_width
            y = draw_rect.bottom() - (intensity / 100.0) * draw_rect.height()
            points.append(QPoint(int(x), int(y)))
        
        # 绘制连接线
        if len(points) > 1:
            pen = QPen(QColor("#d4af37"), 3)
            painter.setPen(pen)
            
            for i in range(len(points) - 1):
                painter.drawLine(points[i], points[i + 1])
        
        # 绘制点
        brush = QBrush(QColor("#d4af37"))
        painter.setBrush(brush)
        painter.setPen(QPen(QColor("#d4af37"), 1))
        
        for i, point in enumerate(points):
            # 高亮当前步骤
            if i == self.current_step:
                painter.setBrush(QBrush(QColor("#ff6b6b")))
                painter.drawEllipse(point, 8, 8)
                painter.setBrush(brush)
            else:
                painter.drawEllipse(point, 5, 5)
                
    def _draw_channel_value(self, painter: QPainter, rect: QRect) -> None:
        """绘制强度范围显示"""
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        
        # 绘制强度范围
        painter.setPen(QPen(QColor("#d4af37"), 1))
        strength_text = f"强度:{self.channel_value:02d}"
        painter.drawText(rect.width() - 80, rect.height() - 30, strength_text)


class PulseBar(QWidget):
    """单个脉冲条组件"""
    
    value_changed = Signal(int, int)  # 位置, 新值
    frequency_changed = Signal(int, int)  # 位置, 新频率
    delete_requested = Signal(int)  # 删除请求信号，传递位置
    detailed_edit_requested = Signal(int)  # 精细编辑请求信号，传递位置
    
    def __init__(self, position: int, height_percent: float, parent: Optional[QWidget] = None, 
                 pulse_operation: Optional[PulseOperation] = None):
        super().__init__(parent)
        self.position = position
        self.height_percent = max(0.0, min(100.0, height_percent))

        self.pulse_operation: PulseOperation
        self.frequency: int
        self.intensity: int
        
        # 存储完整的脉冲操作数据，避免精度丢失
        if pulse_operation:
            self.pulse_operation = pulse_operation
            # 显示用的简化值（取第一个值作为显示）
            self.frequency = pulse_operation[0][0]
            self.intensity = pulse_operation[1][0]
        else:
            # 默认数据
            self.frequency = 10
            self.intensity = int(height_percent)
            self.pulse_operation = ((10, 10, 10, 10), (self.intensity, self.intensity, self.intensity, self.intensity))
        
        self.is_dragging = False
        self.delete_button_hovered = False
        self.setFixedWidth(35)  # 增加宽度以容纳频率显示
        self.setMinimumHeight(100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)  # 启用鼠标跟踪以检测hover状态
        
        # 设置工具提示
        self.update_tooltip()
        
    def set_height_percent(self, percent: float) -> None:
        """设置高度百分比"""
        self.height_percent = max(0.0, min(100.0, percent))
        self.update()
        self.update_tooltip()
        
    def update_tooltip(self) -> None:
        """更新工具提示信息"""
        # 分析4元组数据的复杂性
        freq_tuple, strength_tuple = self.pulse_operation
        freq_is_uniform = len(set(freq_tuple)) == 1
        strength_is_uniform = len(set(strength_tuple)) == 1
        
        tooltip_text = f"步骤 {self.position + 1}\n"
        
        if strength_is_uniform:
            tooltip_text += f"强度: {strength_tuple[0]}% (统一)\n"
        else:
            tooltip_text += f"强度: {strength_tuple[0]}% (复杂: {min(strength_tuple)}-{max(strength_tuple)}%)\n"
            
        if freq_is_uniform:
            tooltip_text += f"频率: {freq_tuple[0]} (统一)\n"
        else:
            tooltip_text += f"频率: {freq_tuple[0]} (复杂: {min(freq_tuple)}-{max(freq_tuple)})\n"
            
        tooltip_text += f"持续: {freq_tuple[0]}\n\n"
        tooltip_text += "拖拽调整强度\n"
        tooltip_text += "右键编辑频率\n"
        tooltip_text += "双击精细编辑"
        
        self.setToolTip(tooltip_text)
        
    def _show_frequency_edit_menu(self, position: QPoint) -> None:
        """显示频率编辑菜单"""
        menu = QMenu(self)
        
        # 精细编辑动作
        detailed_edit_action = menu.addAction("🔧 精细编辑 (4元组)")
        menu.addSeparator()
        
        # 编辑频率动作
        edit_freq_action = menu.addAction(f"📊 编辑频率 (当前: {self.frequency})")
        menu.addSeparator()
        
        # 快速设置动作
        quick_10 = menu.addAction("⚡ 高频 10")
        quick_50 = menu.addAction("🔄 中频 50") 
        quick_100 = menu.addAction("🐌 低频 100")
        quick_240 = menu.addAction("🔽 极低频 240")
        
        # 显示菜单
        action = menu.exec(self.mapToGlobal(position))
        
        if action == detailed_edit_action:
            self.detailed_edit_requested.emit(self.position)
        elif action == edit_freq_action:
            self._edit_frequency_dialog()
        elif action == quick_10:
            self._set_frequency(10)
        elif action == quick_50:
            self._set_frequency(50)
        elif action == quick_100:
            self._set_frequency(100)
        elif action == quick_240:
            self._set_frequency(240)
            
    def _edit_frequency_dialog(self) -> None:
        """显示频率编辑对话框"""
        frequency, ok = QInputDialog.getInt(
            self, 
            "编辑步骤频率",
            f"步骤 {self.position + 1} 的频率值:\n范围: 10-240",
            self.frequency, 10, 240, 1
        )
        
        if ok:
            self._set_frequency(frequency)
            
    def _set_frequency(self, frequency: int) -> None:
        """设置频率并发射信号（统一设置所有4个值）"""
        if frequency != self.frequency:
            self.frequency = frequency
            # 更新脉冲操作数据，保持强度不变
            _, strength_tuple = self.pulse_operation
            self.pulse_operation = ((frequency, frequency, frequency, frequency), strength_tuple)
            self.update()  # 重绘条形
            self.update_tooltip()  # 更新工具提示
            self.frequency_changed.emit(self.position, frequency)
            
    def set_pulse_operation(self, pulse_operation: PulseOperation) -> None:
        """设置完整的脉冲操作数据"""
        self.pulse_operation = pulse_operation
        # 更新显示值
        self.frequency = pulse_operation[0][0]
        self.intensity = pulse_operation[1][0]
        self.height_percent = float(self.intensity)
        self.update()
        self.update_tooltip()
        
    def get_pulse_operation(self) -> PulseOperation:
        """获取完整的脉冲操作数据"""
        return self.pulse_operation
        
    def get_delete_button_rect(self) -> QRect:
        """获取删除按钮的矩形区域"""
        button_size = 12
        margin = 2
        return QRect(
            self.width() // 2 - button_size // 2,  # 居中
            margin,  # 顶部边距
            button_size,
            button_size
        )
        
    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制脉冲条"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        margin = 2
        delete_button_height = 16  # 为删除按钮预留空间
        frequency_label_height = 14  # 为频率标签预留空间
        bar_rect = QRect(margin, margin + delete_button_height, 
                        rect.width() - 2*margin, 
                        rect.height() - 2*margin - delete_button_height - frequency_label_height)
        
        # 计算条形高度
        bar_height = int(bar_rect.height() * (self.height_percent / 100.0))
        bar_y = bar_rect.bottom() - bar_height
        
        # 创建渐变效果
        gradient = QLinearGradient(0, bar_y, 0, bar_rect.bottom())
        if self.height_percent > 80:
            gradient.setColorAt(0, QColor("#ff6b6b"))  # 红色 - 高强度
            gradient.setColorAt(1, QColor("#d4af37"))  # 金色
        elif self.height_percent > 50:
            gradient.setColorAt(0, QColor("#ffa500"))  # 橙色 - 中等强度
            gradient.setColorAt(1, QColor("#d4af37"))  # 金色
        else:
            gradient.setColorAt(0, QColor("#d4af37"))  # 金色 - 低强度
            gradient.setColorAt(1, QColor("#b8860b"))  # 深金色
            
        # 绘制条形
        painter.fillRect(bar_rect.left(), bar_y, bar_rect.width(), bar_height, gradient)
        
        # 绘制边框
        painter.setPen(QPen(QColor("#d4af37"), 1))
        painter.drawRect(bar_rect.left(), bar_y, bar_rect.width(), bar_height)
        
        # 绘制强度数值标签
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QPen(QColor("white"), 1))
        
        # 计算强度文字区域
        intensity_rect = QRect(bar_rect.left(), bar_y, bar_rect.width(), bar_height // 2)
        painter.drawText(intensity_rect, Qt.AlignmentFlag.AlignCenter, f"{int(self.height_percent)}")
        
        # 绘制频率标签（在条形底部）
        freq_font = QFont()
        freq_font.setPointSize(6)
        painter.setFont(freq_font)
        
        # 根据频率值设置颜色
        if self.frequency <= 30:
            freq_color = QColor("#4CAF50")  # 绿色 - 快速
        elif self.frequency <= 100:
            freq_color = QColor("#FFC107")  # 黄色 - 中等
        else:
            freq_color = QColor("#FF9800")  # 橙色 - 慢速
            
        painter.setPen(QPen(freq_color, 1))
        
        # 频率显示区域（条形底部下方）
        freq_rect = QRect(bar_rect.left(), bar_rect.bottom() + 2, bar_rect.width(), 12)
        freq_text = f"{self.frequency}"
        painter.drawText(freq_rect, Qt.AlignmentFlag.AlignCenter, freq_text)
        
        # 绘制删除按钮
        self._draw_delete_button(painter)
        
    def _draw_delete_button(self, painter: QPainter) -> None:
        """绘制删除按钮"""
        button_rect = self.get_delete_button_rect()
        
        # 设置按钮背景色
        if self.delete_button_hovered:
            button_color = QColor("#ff4444")  # 悬停时为红色
            text_color = QColor("white")
        else:
            button_color = QColor("#d4af37")  # 默认为金色
            text_color = QColor("black")
            
        # 绘制圆形背景
        painter.setBrush(QBrush(button_color))
        painter.setPen(QPen(button_color, 1))
        painter.drawEllipse(button_rect)
        
        # 绘制 × 符号
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(text_color, 1))
        painter.drawText(button_rect, Qt.AlignmentFlag.AlignCenter, "×")
        
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 检查是否点击了删除按钮
            delete_rect = self.get_delete_button_rect()
            if delete_rect.contains(event.position().toPoint()):
                self.delete_requested.emit(self.position)
                return
                
            # 否则进行正常的拖拽操作
            self.is_dragging = True
            self._update_value_from_mouse(event.position().y())
            
        elif event.button() == Qt.MouseButton.RightButton:
            # 右键编辑频率
            self._show_frequency_edit_menu(event.position().toPoint())
            
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """鼠标双击事件 - 打开精细编辑"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.detailed_edit_requested.emit(self.position)
            
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """鼠标移动事件"""
        if self.is_dragging:
            self._update_value_from_mouse(event.position().y())
        else:
            # 检查是否悬停在删除按钮上
            delete_rect = self.get_delete_button_rect()
            was_hovered = self.delete_button_hovered
            self.delete_button_hovered = delete_rect.contains(event.position().toPoint())
            
            # 如果hover状态改变，重绘按钮区域
            if was_hovered != self.delete_button_hovered:
                self.update(delete_rect)
            
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """鼠标释放事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            
    def leaveEvent(self, event: QEvent) -> None:
        """鼠标离开事件"""
        if self.delete_button_hovered:
            self.delete_button_hovered = False
            self.update(self.get_delete_button_rect())
            
    def _update_value_from_mouse(self, mouse_y: float) -> None:
        """根据鼠标位置更新数值"""
        rect = self.rect()
        margin = 2
        delete_button_height = 16  # 删除按钮占用的高度
        available_height = rect.height() - 2*margin - delete_button_height
        
        # 调整鼠标Y坐标，考虑删除按钮空间
        adjusted_mouse_y = mouse_y - margin - delete_button_height
        
        # 计算百分比（反转Y轴）
        percent = max(0.0, min(100.0, (available_height - adjusted_mouse_y) / available_height * 100))
        
        if abs(percent - self.height_percent) > 1:  # 避免频繁更新
            self.height_percent = percent
            self.update()
            self.value_changed.emit(self.position, int(percent))


class PulseStepEditor(QWidget):
    """脉冲步骤编辑器 - 仿照官方APP的条形图编辑器"""
    
    step_changed = Signal(int, int)  # 步骤位置, 新强度值
    frequency_changed = Signal(int, int)  # 步骤位置, 新频率值
    step_added = Signal()
    step_removed = Signal(int)
    detailed_edit_requested = Signal(int, object)  # 精细编辑请求信号，传递位置和PulseOperation
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pulse_bars: List[PulseBar] = []
        self.current_frequency: int = 10  # 当前频率值，默认10
        self.setMinimumHeight(120)
        self.setMaximumHeight(200)
        
        # 设置主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 容器widget
        self.container_widget = QWidget()
        self.container_layout = QHBoxLayout(self.container_widget)
        self.container_layout.setSpacing(2)
        self.container_layout.setContentsMargins(5, 5, 5, 5)
        
        self.scroll_area.setWidget(self.container_widget)
        main_layout.addWidget(self.scroll_area)
        
        # 设置样式
        self.setStyleSheet("""
            PulseStepEditor {
                background-color: #1e1e1e;
                border: 1px solid #d4af37;
                border-radius: 5px;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        
    def set_pulse_data(self, data: List[PulseOperation]) -> None:
        """设置脉冲数据"""
        logger.debug(f"PulseStepEditor: 设置脉冲数据，数据长度: {len(data)}")
        
        # 清除现有条形
        self.clear_bars()
        
        # 创建新的条形
        for i, pulse_op in enumerate(data):
            # 提取频率和强度信息
            frequency_tuple, intensity_tuple = pulse_op
            frequency = frequency_tuple[0]  # 使用第一个频率值作为显示
            intensity = intensity_tuple[0]  # 使用第一个强度值作为显示
            
            logger.debug(f"PulseStepEditor: 创建第{i}个条形，频率: {frequency}, 强度: {intensity}")
            # 传入完整的脉冲操作数据，避免精度丢失
            bar = PulseBar(i, intensity, pulse_operation=pulse_op)
            bar.value_changed.connect(self._on_bar_value_changed)
            bar.frequency_changed.connect(self._on_bar_frequency_changed)
            bar.delete_requested.connect(self._on_bar_delete_requested)
            bar.detailed_edit_requested.connect(self._on_detailed_edit_requested)
            
            self.pulse_bars.append(bar)
            self.container_layout.addWidget(bar)
            
        # 添加弹性空间
        self.container_layout.addStretch()
        logger.debug(f"PulseStepEditor: 完成创建，总共{len(self.pulse_bars)}个条形")
        
    def clear_bars(self) -> None:
        """清除所有条形"""
        for bar in self.pulse_bars:
            bar.deleteLater()
        self.pulse_bars.clear()
        
        # 清除布局中的所有项目
        while self.container_layout.count():
            child = self.container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
    def add_step(self, intensity: float = 50.0) -> None:
        """添加新步骤"""
        position = len(self.pulse_bars)
        # 创建默认的脉冲操作数据
        intensity_int = int(intensity)
        default_pulse_op = (
            (self.current_frequency, self.current_frequency, self.current_frequency, self.current_frequency),
            (intensity_int, intensity_int, intensity_int, intensity_int)
        )
        
        bar = PulseBar(position, intensity, pulse_operation=default_pulse_op)
        bar.value_changed.connect(self._on_bar_value_changed)
        bar.frequency_changed.connect(self._on_bar_frequency_changed)
        bar.delete_requested.connect(self._on_bar_delete_requested)
        bar.detailed_edit_requested.connect(self._on_detailed_edit_requested)
        
        # 移除弹性空间
        if self.container_layout.count() > 0:
            _ = self.container_layout.takeAt(self.container_layout.count() - 1)
            
        self.pulse_bars.append(bar)
        self.container_layout.addWidget(bar)
        
        # 重新添加弹性空间
        self.container_layout.addStretch()
        
        self.step_added.emit()
        
    def remove_step(self, position: int) -> None:
        """移除指定位置的步骤"""
        if 0 <= position < len(self.pulse_bars):
            bar = self.pulse_bars.pop(position)
            bar.deleteLater()
            
            # 更新剩余条形的位置
            for i, remaining_bar in enumerate(self.pulse_bars):
                remaining_bar.position = i
                
            self.step_removed.emit(position)
    
    def set_frequency(self, frequency: int) -> None:
        """设置当前频率值"""
        self.current_frequency = frequency
        
    def update_all_frequencies(self, frequency: int) -> None:
        """更新所有条形的频率（固定模式用）"""
        for bar in self.pulse_bars:
            bar.frequency = frequency
            bar.update()  # 重绘条形
            bar.update_tooltip()  # 更新工具提示
        self.current_frequency = frequency
        
    def get_pulse_data(self) -> List[PulseOperation]:
        """获取当前的脉冲数据（保持完整精度）"""
        data: List[PulseOperation] = []
        for bar in self.pulse_bars:
            # 直接使用条形存储的完整脉冲操作数据，避免精度丢失
            data.append(bar.get_pulse_operation())
        return data
        
    def _on_bar_value_changed(self, position: int, value: int) -> None:
        """条形值改变处理"""
        self.step_changed.emit(position, value)
        
    def _on_bar_frequency_changed(self, position: int, frequency: int) -> None:
        """条形频率改变处理"""
        self.frequency_changed.emit(position, frequency)
        
    def _on_bar_delete_requested(self, position: int) -> None:
        """处理条形删除请求"""
        # 至少保留一个步骤
        if len(self.pulse_bars) <= 1:
            logger.debug("Cannot delete the last step")
            return
            
        self.remove_step(position)
        
    def _on_detailed_edit_requested(self, position: int) -> None:
        """处理精细编辑请求"""
        if 0 <= position < len(self.pulse_bars):
            pulse_operation = self.pulse_bars[position].get_pulse_operation()
            self.detailed_edit_requested.emit(position, pulse_operation)
            
    def update_step_data(self, position: int, pulse_operation: PulseOperation) -> None:
        """更新指定步骤的数据"""
        if 0 <= position < len(self.pulse_bars):
            self.pulse_bars[position].set_pulse_operation(pulse_operation)
            logger.debug(f"Updated step {position} with detailed data")


class ParameterControlPanel(QWidget):
    """参数控制面板"""
    
    frequency_changed = Signal(int)
    frequency_mode_changed = Signal(str)  # 频率模式改变信号
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.frequency_mode = "fixed"  # 默认固定频率模式
        
        # 预声明实例变量（在setup_ui中初始化）
        self.freq_group: QGroupBox
        self.freq_label: QLabel
        self.mode_btn: QPushButton
        self.freq_slider: QSlider
        
        self.setup_ui()
        
        # 连接语言变更信号
        language_signals.language_changed.connect(self.update_ui_texts)
        
    def setup_ui(self) -> None:
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 脉冲频率区域
        freq_group = self._create_frequency_group()
        layout.addWidget(freq_group)
        

    def _create_frequency_group(self) -> QWidget:
        """创建频率控制组"""
        self.freq_group = QGroupBox(translate("pulse_editor.pulse_frequency"))
        group = self.freq_group
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d4af37;
                border-radius: 5px;
                margin: 5px;
                padding-top: 10px;
                color: #d4af37;
            }
        """)
        
        layout = QVBoxLayout(group)
        
        # 频率标签和控制
        freq_layout = QHBoxLayout()
        
        self.freq_label = QLabel("10 (固定)")
        self.freq_label.setStyleSheet("color: white; font-weight: normal;")
        freq_layout.addWidget(self.freq_label)
        
        # 频率模式切换按钮
        self.mode_btn = QPushButton("固定频率")
        self.mode_btn.setCheckable(True)
        self.mode_btn.setChecked(True)
        self.mode_btn.clicked.connect(self._toggle_frequency_mode)
        self.mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: white;
                border: 1px solid #d4af37;
                padding: 3px 8px;
                border-radius: 3px;
            }
            QPushButton:checked {
                background-color: #d4af37;
                color: black;
            }
        """)
        freq_layout.addWidget(self.mode_btn)
        
        freq_layout.addStretch()
        layout.addLayout(freq_layout)
        
        # 频率滑块
        self.freq_slider = QSlider(Qt.Orientation.Horizontal)
        self.freq_slider.setRange(10, 240)
        self.freq_slider.setValue(10)
        self.freq_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #333;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #d4af37;
                width: 18px;
                height: 18px;
                border-radius: 9px;
                margin: -6px 0;
            }
            QSlider::sub-page:horizontal {
                background: #d4af37;
                border-radius: 3px;
            }
        """)
        self.freq_slider.valueChanged.connect(self._on_frequency_changed)
        layout.addWidget(self.freq_slider)
        
        return group
        
    def _on_frequency_changed(self, value: int) -> None:
        """频率改变处理"""
        mode_text = "固定" if self.frequency_mode == "fixed" else "独立"
        self.freq_label.setText(f"{value} ({mode_text})")
        self.frequency_changed.emit(value)
        
    def _toggle_frequency_mode(self) -> None:
        """切换频率模式"""
        if self.frequency_mode == "fixed":
            self.frequency_mode = "individual"
            self.mode_btn.setText("独立频率")
            self.mode_btn.setChecked(False)
        else:
            self.frequency_mode = "fixed"
            self.mode_btn.setText("固定频率")
            self.mode_btn.setChecked(True)
            
        # 更新频率标签
        current_freq = self.freq_slider.value()
        mode_text = "固定" if self.frequency_mode == "fixed" else "独立"
        self.freq_label.setText(f"{current_freq} ({mode_text})")
        
        # 发射模式改变信号
        self.frequency_mode_changed.emit(self.frequency_mode)
        
    def get_frequency(self) -> int:
        """获取当前频率"""
        return self.freq_slider.value()
        
    def update_ui_texts(self) -> None:
        """更新UI文本"""
        # 更新频率组标题
        self.freq_group.setTitle(translate("pulse_editor.pulse_frequency"))
        
        # 更新模式按钮文本
        if self.frequency_mode == "fixed":
            self.mode_btn.setText("固定频率")
        else:
            self.mode_btn.setText("独立频率")
            
    def get_frequency_mode(self) -> str:
        """获取当前频率模式"""
        return self.frequency_mode
        
    def set_frequency_mode(self, mode: str) -> None:
        """设置频率模式"""
        if mode in ["fixed", "individual"]:
            self.frequency_mode = mode
            if mode == "fixed":
                self.mode_btn.setText("固定频率")
                self.mode_btn.setChecked(True)
            else:
                self.mode_btn.setText("独立频率")
                self.mode_btn.setChecked(False)
            
            # 更新频率标签
            current_freq = self.freq_slider.value()
            mode_text = "固定" if mode == "fixed" else "独立"
            self.freq_label.setText(f"{current_freq} ({mode_text})")
        

