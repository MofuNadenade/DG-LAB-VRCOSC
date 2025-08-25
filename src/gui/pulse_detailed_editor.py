"""
精细脉冲编辑器
支持4元组频率和强度的详细编辑，确保不丢失精度
"""

import logging
from functools import partial
from typing import Optional, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QDialog, QDialogButtonBox, QGridLayout,
    QTabWidget, QScrollArea, QSlider
)

from i18n import translate, language_signals
from models import PulseOperation

logger = logging.getLogger(__name__)


class DetailedPulseStepDialog(QDialog):
    """单个脉冲步骤的详细编辑对话框"""

    def __init__(self, pulse_operation: PulseOperation, step_index: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pulse_operation = pulse_operation
        self.step_index = step_index
        self.frequency_sliders: List[QSlider] = []
        self.frequency_labels: List[QLabel] = []
        self.strength_sliders: List[QSlider] = []
        self.strength_labels: List[QLabel] = []
        self.preview_label: QLabel

        self.setup_ui()
        self.load_data()

        # 连接语言变更信号
        language_signals.language_changed.connect(self.update_ui_texts)

    def setup_ui(self) -> None:
        """设置UI"""
        self.setWindowTitle(translate("pulse_editor.detailed_edit_title"))
        self.setModal(True)
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel(translate("pulse_editor.detailed_edit_step").format(self.step_index + 1))
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 创建标签页
        tab_widget = QTabWidget()

        # 频率编辑标签页
        freq_tab = self.create_frequency_tab()
        tab_widget.addTab(freq_tab, translate("pulse_editor.frequency_tab"))

        # 强度编辑标签页
        strength_tab = self.create_strength_tab()
        tab_widget.addTab(strength_tab, translate("pulse_editor.strength_tab"))

        # 预览标签页
        preview_tab = self.create_preview_tab()
        tab_widget.addTab(preview_tab, translate("pulse_editor.preview_tab"))

        layout.addWidget(tab_widget)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.apply_theme()

    def create_frequency_tab(self) -> QWidget:
        """创建频率编辑标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 说明文字
        desc_label = QLabel(translate("pulse_editor.frequency_desc"))
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # 频率编辑组
        freq_group = QGroupBox(translate("pulse_editor.frequency_values"))
        freq_layout = QGridLayout(freq_group)

        self.frequency_sliders = []
        self.frequency_labels = []
        for i in range(4):
            # 通道标签
            channel_label = QLabel(translate("pulse_editor.frequency_channel").format(i + 1))
            freq_layout.addWidget(channel_label, i, 0)

            # 数值显示标签
            value_label = QLabel("10")
            value_label.setMinimumWidth(40)
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet("""
                QLabel {
                    background-color: #333;
                    color: #d4af37;
                    border: 1px solid #555;
                    border-radius: 3px;
                    padding: 2px;
                    font-weight: bold;
                }
            """)
            freq_layout.addWidget(value_label, i, 1)
            self.frequency_labels.append(value_label)

            # 滑动条
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(10, 240)
            slider.setValue(10)
            slider.setStyleSheet("""
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
            slider.valueChanged.connect(partial(self._on_frequency_slider_changed, i))
            freq_layout.addWidget(slider, i, 2)
            self.frequency_sliders.append(slider)

        layout.addWidget(freq_group)

        # 快速设置按钮
        quick_group = QGroupBox(translate("pulse_editor.quick_frequency_settings"))
        quick_layout = QHBoxLayout(quick_group)

        # 统一设置
        uniform_btn = QPushButton(translate("pulse_editor.set_uniform_frequency"))
        uniform_btn.clicked.connect(self.set_uniform_frequency)
        quick_layout.addWidget(uniform_btn)

        # 渐变设置
        gradient_btn = QPushButton(translate("pulse_editor.set_gradient_frequency"))
        gradient_btn.clicked.connect(self.set_gradient_frequency)
        quick_layout.addWidget(gradient_btn)

        # 复制第一个值
        copy_first_btn = QPushButton(translate("pulse_editor.copy_first_frequency"))
        copy_first_btn.clicked.connect(self.copy_first_frequency)
        quick_layout.addWidget(copy_first_btn)

        layout.addWidget(quick_group)
        layout.addStretch()

        return widget

    def create_strength_tab(self) -> QWidget:
        """创建强度编辑标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 说明文字
        desc_label = QLabel(translate("pulse_editor.strength_desc"))
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # 强度编辑组
        strength_group = QGroupBox(translate("pulse_editor.strength_values"))
        strength_layout = QGridLayout(strength_group)

        self.strength_sliders = []
        self.strength_labels = []
        for i in range(4):
            # 通道标签
            channel_label = QLabel(translate("pulse_editor.strength_channel").format(i + 1))
            strength_layout.addWidget(channel_label, i, 0)

            # 数值显示标签
            value_label = QLabel("0%")
            value_label.setMinimumWidth(50)
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet("""
                QLabel {
                    background-color: #333;
                    color: #d4af37;
                    border: 1px solid #555;
                    border-radius: 3px;
                    padding: 2px;
                    font-weight: bold;
                }
            """)
            strength_layout.addWidget(value_label, i, 1)
            self.strength_labels.append(value_label)

            # 滑动条
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(0)
            slider.setStyleSheet("""
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
            slider.valueChanged.connect(partial(self._on_strength_slider_changed, i))
            strength_layout.addWidget(slider, i, 2)
            self.strength_sliders.append(slider)

        layout.addWidget(strength_group)

        # 快速设置按钮
        quick_group = QGroupBox(translate("pulse_editor.quick_strength_settings"))
        quick_layout = QHBoxLayout(quick_group)

        # 统一设置
        uniform_btn = QPushButton(translate("pulse_editor.set_uniform_strength"))
        uniform_btn.clicked.connect(self.set_uniform_strength)
        quick_layout.addWidget(uniform_btn)

        # 渐变设置
        gradient_btn = QPushButton(translate("pulse_editor.set_gradient_strength"))
        gradient_btn.clicked.connect(self.set_gradient_strength)
        quick_layout.addWidget(gradient_btn)

        # 复制第一个值
        copy_first_btn = QPushButton(translate("pulse_editor.copy_first_strength"))
        copy_first_btn.clicked.connect(self.copy_first_strength)
        quick_layout.addWidget(copy_first_btn)

        layout.addWidget(quick_group)
        layout.addStretch()

        return widget

    def create_preview_tab(self) -> QWidget:
        """创建预览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 预览组
        preview_group = QGroupBox(translate("pulse_editor.data_preview"))
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border: 1px solid #d4af37;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Courier New', monospace;
                color: white;
            }
        """)

        scroll_area = QScrollArea()
        scroll_area.setWidget(self.preview_label)
        scroll_area.setWidgetResizable(True)
        preview_layout.addWidget(scroll_area)

        layout.addWidget(preview_group)

        return widget

    def _on_frequency_slider_changed(self, index: int, value: int) -> None:
        """频率滑动条值改变处理"""
        self.frequency_labels[index].setText(str(value))
        self.update_preview()

    def _on_strength_slider_changed(self, index: int, value: int) -> None:
        """强度滑动条值改变处理"""
        self.strength_labels[index].setText(f"{value}%")
        self.update_preview()

    def load_data(self) -> None:
        """加载数据到编辑器"""
        frequency_tuple, strength_tuple = self.pulse_operation

        # 加载频率数据
        for i, freq in enumerate(frequency_tuple):
            self.frequency_sliders[i].setValue(freq)
            self.frequency_labels[i].setText(str(freq))

        # 加载强度数据
        for i, strength in enumerate(strength_tuple):
            self.strength_sliders[i].setValue(strength)
            self.strength_labels[i].setText(f"{strength}%")

        self.update_preview()

    def update_preview(self) -> None:
        """更新预览"""
        frequency_values = [slider.value() for slider in self.frequency_sliders]
        strength_values = [slider.value() for slider in self.strength_sliders]

        preview_text = translate("pulse_editor.preview_format").format(
            self.step_index + 1,
            ', '.join(map(str, frequency_values)),
            ', '.join(map(str, strength_values))
        )

        # 添加数据分析
        preview_text += "\n\n" + translate("pulse_editor.data_analysis") + ":\n"
        preview_text += f"• {translate('pulse_editor.frequency_range')}: {min(frequency_values)} - {max(frequency_values)}\n"
        preview_text += f"• {translate('pulse_editor.strength_range')}: {min(strength_values)} - {max(strength_values)}%\n"
        preview_text += f"• {translate('pulse_editor.frequency_uniform')}: {translate('pulse_editor.yes') if len(set(frequency_values)) == 1 else translate('pulse_editor.no')}\n"
        preview_text += f"• {translate('pulse_editor.strength_uniform')}: {translate('pulse_editor.yes') if len(set(strength_values)) == 1 else translate('pulse_editor.no')}\n"

        self.preview_label.setText(preview_text)

    def get_pulse_operation(self) -> PulseOperation:
        """获取编辑后的脉冲操作数据"""
        frequency_values = (
            self.frequency_sliders[0].value(),
            self.frequency_sliders[1].value(),
            self.frequency_sliders[2].value(),
            self.frequency_sliders[3].value()
        )
        strength_values = (
            self.strength_sliders[0].value(),
            self.strength_sliders[1].value(),
            self.strength_sliders[2].value(),
            self.strength_sliders[3].value()
        )
        return frequency_values, strength_values

    def set_uniform_frequency(self) -> None:
        """设置统一频率"""
        if self.frequency_sliders:
            first_value = self.frequency_sliders[0].value()
            for slider in self.frequency_sliders[1:]:
                slider.setValue(first_value)

    def set_gradient_frequency(self) -> None:
        """设置渐变频率"""
        if len(self.frequency_sliders) >= 2:
            start_value = self.frequency_sliders[0].value()
            end_value = self.frequency_sliders[-1].value()

            for i, slider in enumerate(self.frequency_sliders[1:-1], 1):
                # 线性插值
                progress = i / (len(self.frequency_sliders) - 1)
                value = int(start_value + (end_value - start_value) * progress)
                slider.setValue(value)

    def copy_first_frequency(self) -> None:
        """复制第一个频率值到所有位置"""
        self.set_uniform_frequency()

    def set_uniform_strength(self) -> None:
        """设置统一强度"""
        if self.strength_sliders:
            first_value = self.strength_sliders[0].value()
            for slider in self.strength_sliders[1:]:
                slider.setValue(first_value)

    def set_gradient_strength(self) -> None:
        """设置渐变强度"""
        if len(self.strength_sliders) >= 2:
            start_value = self.strength_sliders[0].value()
            end_value = self.strength_sliders[-1].value()

            for i, slider in enumerate(self.strength_sliders[1:-1], 1):
                # 线性插值
                progress = i / (len(self.strength_sliders) - 1)
                value = int(start_value + (end_value - start_value) * progress)
                slider.setValue(value)

    def copy_first_strength(self) -> None:
        """复制第一个强度值到所有位置"""
        self.set_uniform_strength()

    def apply_theme(self) -> None:
        """应用主题"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: white;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #d4af37;
                border-radius: 8px;
                margin: 5px;
                padding-top: 15px;
                color: #d4af37;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                background-color: #1a1a1a;
            }
            QSpinBox {
                background-color: #2b2b2b;
                border: 1px solid #d4af37;
                border-radius: 3px;
                padding: 3px;
                color: white;
                min-width: 80px;
            }
            QSpinBox:focus {
                border: 2px solid #d4af37;
            }
            QPushButton {
                background-color: #d4af37;
                color: black;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f0c040;
            }
            QPushButton:pressed {
                background-color: #b8860b;
            }
            QTabWidget::pane {
                border: 1px solid #d4af37;
                background-color: #1a1a1a;
            }
            QTabBar::tab {
                background-color: #333;
                color: white;
                padding: 8px 16px;
                border: 1px solid #d4af37;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #d4af37;
                color: black;
            }
            QLabel {
                color: white;
            }
        """)

    def update_ui_texts(self) -> None:
        """更新UI文本"""
        self.setWindowTitle(translate("pulse_editor.detailed_edit_title"))
        # 这里可以添加更多UI文本更新逻辑
