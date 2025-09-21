"""
波形编辑器对话框组件

包含新建、导入、导出等对话框
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional, List, Tuple, TypedDict

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QFileDialog, QMessageBox, QFormLayout,
    QDialogButtonBox, QComboBox, QSpinBox, QListWidget, QListWidgetItem,
    QWidget, QApplication, QTabWidget, QPlainTextEdit
)

from core.dglab_pulse import Pulse
from core.waveform_share_codec import WaveformShareCodec
from core.official.pulse_file_parser import PulseFileParser
from core.official.pulse_file_models import PulseFileData
from i18n import translate
from models import PulseOperation, PulseDict, IntegrityReport
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class OfficialPulseFileStats(TypedDict):
    """官方波形文件统计信息"""
    steps: int
    duration_ms: int
    max_frequency: int
    max_intensity: int
    sections: int
    enabled_sections: int
    rest_duration: float
    speed_multiplier: int


class OfficialPulseFileInfo(TypedDict):
    """官方波形文件信息结构"""
    file_path: str
    file_name: str
    pulse_name: str
    pulse_data: PulseFileData
    pulse_operations: List[PulseOperation]
    warnings: List[str]
    stats: OfficialPulseFileStats


class PulseFileExportData(TypedDict):
    """完整的波形文件导出数据"""
    pulses: Dict[str, List[PulseOperation]]


class NewPulseDialog(QDialog):
    """新建波形对话框"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pulse_name = ""
        self.template_data: List[PulseOperation] = []
        
        # UI组件类型注解
        self.name_edit: QLineEdit
        self.template_combo: QComboBox
        self.steps_spinbox: QSpinBox
        self.description_edit: QTextEdit

        self.setWindowTitle(translate("dialogs.pulse.new_pulse.title"))
        self.setModal(True)
        self.resize(400, 300)
        self.setup_ui()
        self.apply_style()

    def setup_ui(self) -> None:
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel(translate("dialogs.pulse.new_pulse.create_new"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # 表单布局
        form_layout = QFormLayout()

        # 波形名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(translate("dialogs.pulse.new_pulse.name_placeholder"))
        form_layout.addRow(translate("dialogs.pulse.new_pulse.pulse_name_label"), self.name_edit)

        # 模板选择
        self.template_combo = QComboBox()
        self.template_combo.addItem(translate("dialogs.pulse.new_pulse.blank_waveform"), [])
        self.template_combo.addItem(translate("dialogs.pulse.new_pulse.simple_pulse"), [
            ((10, 10, 10, 10), (100, 100, 100, 100)),
            ((10, 10, 10, 10), (0, 0, 0, 0))
        ])
        self.template_combo.addItem(translate("dialogs.pulse.new_pulse.progressive_waveform"), [
            ((10, 10, 10, 10), (20, 20, 20, 20)),
            ((10, 10, 10, 10), (40, 40, 40, 40)),
            ((10, 10, 10, 10), (60, 60, 60, 60)),
            ((10, 10, 10, 10), (80, 80, 80, 80)),
            ((10, 10, 10, 10), (100, 100, 100, 100))
        ])
        self.template_combo.addItem(translate("dialogs.pulse.new_pulse.pulse_sequence"), [
            ((10, 10, 10, 10), (100, 100, 100, 100)),
            ((10, 10, 10, 10), (0, 0, 0, 0)),
            ((10, 10, 10, 10), (100, 100, 100, 100)),
            ((10, 10, 10, 10), (0, 0, 0, 0)),
            ((10, 10, 10, 10), (100, 100, 100, 100)),
            ((10, 10, 10, 10), (0, 0, 0, 0))
        ])
        form_layout.addRow(translate("dialogs.pulse.new_pulse.base_template_label"), self.template_combo)

        # 初始步数
        self.steps_spinbox = QSpinBox()
        self.steps_spinbox.setRange(1, 50)
        self.steps_spinbox.setValue(8)
        form_layout.addRow(translate("dialogs.pulse.new_pulse.initial_steps_label"), self.steps_spinbox)

        layout.addLayout(form_layout)

        # 描述
        desc_label = QLabel(translate("dialogs.pulse.new_pulse.description_label"))
        layout.addWidget(desc_label)

        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText(translate("dialogs.pulse.new_pulse.description_placeholder"))
        layout.addWidget(self.description_edit)

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def apply_style(self) -> None:
        """应用样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
                font-weight: 500;
            }
            QLineEdit, QTextEdit {
                background-color: #2a2a2a;
                border: 2px solid #444444;
                padding: 10px 12px;
                border-radius: 6px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #d4af37;
                background-color: #2f2f2f;
            }
            QComboBox {
                background-color: #2a2a2a;
                border: 2px solid #444444;
                padding: 8px 12px;
                border-radius: 6px;
                color: #ffffff;
                font-size: 13px;
                min-width: 120px;
            }
            QComboBox:focus {
                border-color: #d4af37;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                border: none;
                background: #d4af37;
            }
            QSpinBox {
                background-color: #2a2a2a;
                border: 2px solid #444444;
                padding: 8px 12px;
                border-radius: 6px;
                color: #ffffff;
                font-size: 13px;
            }
            QSpinBox:focus {
                border-color: #d4af37;
            }
            QPushButton {
                background-color: #d4af37;
                color: #000000;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #e6c547;
            }
            QPushButton:pressed {
                background-color: #c4a030;
            }
        """)

    def get_pulse_data(self) -> tuple[str, List[PulseOperation], str]:
        """获取波形数据"""
        name = self.name_edit.text().strip()
        description = self.description_edit.toPlainText().strip()

        # 获取模板数据
        template_data = self.template_combo.currentData()
        if not template_data:
            # 创建空白波形
            steps = self.steps_spinbox.value()
            template_data = [((10, 10, 10, 10), (0, 0, 0, 0)) for _ in range(steps)]

        return name, template_data, description

    def validate_input(self) -> bool:
        """验证输入"""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, translate("dialogs.pulse.new_pulse.input_error"),
                                translate("dialogs.pulse.new_pulse.name_required"))
            return False
        return True


class ImportPulseDialog(QDialog):
    """导入波形对话框"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.imported_pulses: List[PulseDict] = []
        self.official_pulse_files: List[OfficialPulseFileInfo] = []  # 存储官方波形文件信息
        
        # UI组件类型注解
        self.file_path_edit: QLineEdit
        self.pulse_list: QListWidget
        self.preview_text: QTextEdit
        self.tab_widget: QTabWidget
        self.share_code_edit: QPlainTextEdit
        self.share_code_info: QLabel
        self.share_code_preview: QTextEdit
        
        # 官方波形导入相关组件
        self.official_files_list: QListWidget
        self.official_files_info_preview: QTextEdit

        self.setWindowTitle(translate("dialogs.pulse.import_pulse.title"))
        self.setModal(True)
        self.resize(800, 650)
        self.setup_ui()
        self.apply_style()

    def setup_ui(self) -> None:
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel(translate("dialogs.pulse.import_pulse.import_file"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # 使用标签页来分离文件导入和分享码导入
        self.tab_widget = QTabWidget()
        
        # 文件导入标签页
        file_tab = self.create_file_import_tab()
        self.tab_widget.addTab(file_tab, translate("dialogs.pulse.import_pulse.file_import_tab"))
        
        # 分享码导入标签页
        share_code_tab = self.create_share_code_import_tab()
        self.tab_widget.addTab(share_code_tab, translate("dialogs.pulse.import_pulse.share_code_tab"))
        
        # 官方波形导入标签页
        official_tab = self.create_official_pulse_import_tab()
        self.tab_widget.addTab(official_tab, translate("dialogs.pulse.import_pulse.official_tab"))
        
        layout.addWidget(self.tab_widget)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_layout.addWidget(button_box)
        
        layout.addLayout(button_layout)
    
    def create_file_import_tab(self) -> QWidget:
        """创建文件导入标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 文件选择
        file_layout = QHBoxLayout()

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText(translate("dialogs.pulse.import_pulse.select_file"))
        self.file_path_edit.setReadOnly(True)
        file_layout.addWidget(self.file_path_edit)

        browse_btn = QPushButton(translate("dialogs.pulse.import_pulse.browse"))
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_btn)

        layout.addLayout(file_layout)

        # 波形列表
        list_label = QLabel(translate("dialogs.pulse.import_pulse.pulses_in_file"))
        layout.addWidget(list_label)

        self.pulse_list = QListWidget()
        self.pulse_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.pulse_list)

        # 预览区域
        preview_label = QLabel(translate("dialogs.pulse.import_pulse.pulse_preview"))
        layout.addWidget(preview_label)

        self.preview_text = QTextEdit()
        self.preview_text.setMaximumHeight(100)
        self.preview_text.setReadOnly(True)
        layout.addWidget(self.preview_text)

        # 文件导入按钮
        file_button_layout = QHBoxLayout()

        select_all_btn = QPushButton(translate("dialogs.pulse.import_pulse.select_all"))
        select_all_btn.clicked.connect(self.select_all)
        file_button_layout.addWidget(select_all_btn)

        clear_btn = QPushButton(translate("dialogs.pulse.import_pulse.clear_selection"))
        clear_btn.clicked.connect(self.clear_selection)
        file_button_layout.addWidget(clear_btn)

        file_button_layout.addStretch()
        layout.addLayout(file_button_layout)
        
        # 连接信号
        self.pulse_list.itemSelectionChanged.connect(self.update_preview)
        
        return tab
    
    def create_share_code_import_tab(self) -> QWidget:
        """创建分享码导入标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 说明文本
        info_label = QLabel("粘贴波形分享码进行导入:")
        layout.addWidget(info_label)
        
        # 分享码输入框
        self.share_code_edit = QPlainTextEdit()
        self.share_code_edit.setPlaceholderText("请粘贴分享码，格式: DGLAB-PULSE-V1|名称|数据|哈希")
        self.share_code_edit.setMaximumHeight(80)
        self.share_code_edit.textChanged.connect(self.on_share_code_changed)
        layout.addWidget(self.share_code_edit)
        
        # 解析结果显示
        self.share_code_info = QLabel("等待输入分享码...")
        self.share_code_info.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.share_code_info)
        
        # 预览区域
        preview_label = QLabel("波形预览:")
        layout.addWidget(preview_label)
        
        self.share_code_preview = QTextEdit()
        self.share_code_preview.setMaximumHeight(200)
        self.share_code_preview.setReadOnly(True)
        layout.addWidget(self.share_code_preview)
        
        return tab
    
    def create_official_pulse_import_tab(self) -> QWidget:
        """创建官方波形导入标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 文件选择区域
        file_selection_layout = QHBoxLayout()
        
        # 选择多个文件按钮
        browse_official_btn = QPushButton(translate("dialogs.pulse.import_pulse.select_official_files"))
        browse_official_btn.clicked.connect(self.browse_official_pulse_files)
        file_selection_layout.addWidget(browse_official_btn)
        
        # 清空选择按钮
        clear_official_btn = QPushButton(translate("dialogs.pulse.import_pulse.clear_official_files"))
        clear_official_btn.clicked.connect(self.clear_official_pulse_files)
        file_selection_layout.addWidget(clear_official_btn)
        
        file_selection_layout.addStretch()
        layout.addLayout(file_selection_layout)
        
        # 已选择文件列表
        files_label = QLabel(translate("dialogs.pulse.import_pulse.selected_files"))
        layout.addWidget(files_label)
        
        self.official_files_list = QListWidget()
        self.official_files_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.official_files_list.itemSelectionChanged.connect(self.update_official_pulse_preview)
        layout.addWidget(self.official_files_list)
        
        # 文件信息和波形预览（合并）
        info_preview_label = QLabel(translate("dialogs.pulse.import_pulse.file_info_preview"))
        layout.addWidget(info_preview_label)
        
        self.official_files_info_preview = QTextEdit()
        self.official_files_info_preview.setMaximumHeight(200)
        self.official_files_info_preview.setReadOnly(True)
        layout.addWidget(self.official_files_info_preview)
        
        # 选择操作按钮
        selection_layout = QHBoxLayout()
        
        select_all_official_btn = QPushButton(translate("dialogs.pulse.import_pulse.select_all_files"))
        select_all_official_btn.clicked.connect(self.select_all_official_files)
        selection_layout.addWidget(select_all_official_btn)
        
        clear_selection_official_btn = QPushButton(translate("dialogs.pulse.import_pulse.clear_file_selection"))
        clear_selection_official_btn.clicked.connect(self.clear_official_selection)
        selection_layout.addWidget(clear_selection_official_btn)
        
        selection_layout.addStretch()
        layout.addLayout(selection_layout)
        
        return tab

    def on_share_code_changed(self) -> None:
        """分享码输入变化处理 (Pydantic版本)"""
        share_code = self.share_code_edit.toPlainText().strip()
        
        if not share_code:
            self.share_code_info.setText("等待输入分享码...")
            self.share_code_info.setStyleSheet("color: #888; font-style: italic;")
            self.share_code_preview.clear()
            return
        
        try:
            parsed = WaveformShareCodec.decode_share_code(share_code)
            validation = parsed.validation
            
            if validation.is_valid:
                pulse_data = parsed.pulse_data
                self.share_code_info.setText(f"✓ 解析成功: {pulse_data.name}")
                self.share_code_info.setStyleSheet("color: green; font-weight: bold;")
                
                # 更新预览 - 使用Pydantic模型的丰富信息
                preview_text = f"波形名称: {pulse_data.name}\n"
                preview_text += f"版本: {pulse_data.version}\n"
                preview_text += f"步数: {pulse_data.metadata.steps}\n"
                preview_text += f"创建时间: {pulse_data.metadata.created.strftime('%Y-%m-%d %H:%M:%S')}\n"
                # 基于数据长度计算持续时间而非依赖metadata
                calculated_duration_ms = len(pulse_data.data) * 100
                preview_text += f"持续时间: {calculated_duration_ms}ms\n"
                preview_text += f"最大强度: {pulse_data.metadata.max_intensity}\n"
                preview_text += f"最大频率: {pulse_data.metadata.max_frequency}\n"
                
                if validation.warnings:
                    preview_text += f"\n⚠️ 警告:\n" + "\n".join(f"• {w}" for w in validation.warnings)
                
                # 显示前3步数据示例
                if pulse_data.data:
                    preview_text += f"\n\n前3步数据示例:\n"
                    for i, step in enumerate(pulse_data.data[:3]):
                        freq, intensity = step
                        preview_text += f"步骤{i+1}: 频率{freq[0]}Hz, 强度{intensity[0]}%\n"
                
                self.share_code_preview.setText(preview_text)
                
            else:
                error_text = "; ".join(validation.errors[:3])  # 只显示前3个错误
                if len(validation.errors) > 3:
                    error_text += f" (还有{len(validation.errors)-3}个错误)"
                    
                self.share_code_info.setText(f"✗ 解析失败: {error_text}")
                self.share_code_info.setStyleSheet("color: red; font-weight: bold;")
                
                # 显示详细错误
                error_message = "解析错误详情:\n" + "\n".join(f"• {e}" for e in validation.errors)
                self.share_code_preview.setText(error_message)
                
        except ValidationError as e:
            # Pydantic验证错误的详细显示
            error_details: List[str] = []
            for error in e.errors():
                field = " -> ".join(str(x) for x in error['loc'])
                error_details.append(f"{field}: {error['msg']}")
            
            self.share_code_info.setText("✗ 数据验证失败")
            self.share_code_info.setStyleSheet("color: red; font-weight: bold;")
            self.share_code_preview.setText("验证错误:\n" + "\n".join(error_details))
            
        except Exception as e:
            self.share_code_info.setText(f"✗ 解析错误: {e}")
            self.share_code_info.setStyleSheet("color: red; font-weight: bold;")
            self.share_code_preview.clear()

    def validate_pulse_operation(self, data: List[PulseOperation]) -> Tuple[bool, List[str]]:
        """验证PulseOperation格式"""
        errors: List[str] = []

        if len(data) == 0:
            errors.append("数据不能为空")
            return False, errors

        for i, item in enumerate(data):
            freq, intensity = item

            # 验证频率数据 - 应该是4个10-240范围内的整数
            if len(freq) != 4:
                errors.append(f"步骤 {i + 1} 频率必须是4个值")
            elif not all(10 <= f <= 240 for f in freq):
                errors.append(f"步骤 {i + 1} 频率值必须在10-240范围内")

            # 验证强度数据 - 应该是4个0-200范围内的整数
            if len(intensity) != 4:
                errors.append(f"步骤 {i + 1} 强度必须是4个值")
            elif not all(0 <= s <= 200 for s in intensity):
                errors.append(f"步骤 {i + 1} 强度值必须在0-200范围内")

        return len(errors) == 0, errors

    def check_pulse_data_integrity(self, pulse_data: List[PulseOperation]) -> IntegrityReport:
        """检查波形数据完整性"""
        issues: List[str] = []
        warnings: List[str] = []

        # 检查数据长度
        if len(pulse_data) > 100:
            warnings.append(translate("dialogs.pulse.import_pulse.validation.too_many_steps").format(len(pulse_data)))
        elif len(pulse_data) > 50:
            warnings.append(translate("dialogs.pulse.import_pulse.validation.many_steps").format(len(pulse_data)))

        # 统计频率和强度使用情况
        frequencies: List[int] = []
        intensities: List[int] = []

        for freq, intensity in pulse_data:
            frequencies.extend(freq)
            intensities.extend(intensity)

        # 检查是否有极端值
        max_freq = max(frequencies) if frequencies else 0
        max_intensity = max(intensities) if intensities else 0

        if max_freq > 150:
            warnings.append(translate("dialogs.pulse.import_pulse.validation.high_frequency").format(max_freq))
        if max_intensity > 150:
            warnings.append(translate("dialogs.pulse.import_pulse.validation.high_intensity").format(max_intensity))

        # 检查数据变化
        if len(set(intensities)) == 1:
            warnings.append(translate("dialogs.pulse.import_pulse.validation.monotonic"))

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'stats': {
                'steps': len(pulse_data),
                'max_frequency': max_freq,
                'max_intensity': max_intensity,
                'duration_ms': len(pulse_data) * 100  # 每步100ms
            }
        }

    def apply_style(self) -> None:
        """应用样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
                font-weight: 500;
            }
            QLineEdit {
                background-color: #2a2a2a;
                border: 2px solid #444444;
                padding: 10px 12px;
                border-radius: 6px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #d4af37;
                background-color: #2f2f2f;
            }
            QTextEdit, QPlainTextEdit {
                background-color: #2a2a2a;
                border: 2px solid #444444;
                padding: 10px 12px;
                border-radius: 6px;
                color: #ffffff;
                font-size: 12px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                line-height: 1.4;
            }
            QTextEdit:focus, QPlainTextEdit:focus {
                border-color: #d4af37;
                background-color: #2f2f2f;
            }
            QListWidget {
                background-color: #2a2a2a;
                border: 2px solid #444444;
                border-radius: 6px;
                color: #ffffff;
                outline: none;
            }
            QListWidget::item {
                padding: 12px 15px;
                border-bottom: 1px solid #333333;
                border-radius: 4px;
                margin: 1px;
            }
            QListWidget::item:selected {
                background-color: #d4af37;
                color: #000000;
                font-weight: 600;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
            }
            QListWidget::item:selected:hover {
                background-color: #e6c547;
            }
            QPushButton {
                background-color: #d4af37;
                color: #000000;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #e6c547;
            }
            QPushButton:pressed {
                background-color: #c4a030;
            }
            QTabWidget::pane {
                border: 2px solid #444444;
                background-color: #2a2a2a;
                border-radius: 8px;
                margin-top: 8px;
            }
            QTabBar::tab {
                background-color: #333333;
                color: #cccccc;
                border: 1px solid #555555;
                padding: 14px 28px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
                min-width: 120px;
            }
            QTabBar::tab:selected {
                background-color: #d4af37;
                color: #000000;
                border-bottom: 2px solid #d4af37;
                font-weight: 600;
            }
            QTabBar::tab:hover {
                background-color: #444444;
                color: #ffffff;
            }
            QTabBar::tab:selected:hover {
                background-color: #e6c547;
            }
        """)

    def browse_file(self) -> None:
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, translate("dialogs.pulse.import_pulse.select_file"), "", "JSON文件 (*.json);;所有文件 (*)"
        )

        if file_path:
            self.file_path_edit.setText(file_path)
            self.load_pulses(file_path)

    def load_pulses(self, file_path: str) -> None:
        """加载波形文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

        except FileNotFoundError:
            QMessageBox.critical(self, translate("dialogs.pulse.import_pulse.file_error"),
                                 translate("dialogs.pulse.import_pulse.file_not_found"))
            return
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, translate("dialogs.pulse.import_pulse.format_error"),
                                 translate("dialogs.pulse.import_pulse.json_invalid").format(str(e)))
            return
        except UnicodeDecodeError:
            QMessageBox.critical(self, translate("dialogs.pulse.import_pulse.encoding_error"),
                                 translate("dialogs.pulse.import_pulse.encoding_unsupported"))
            return
        except Exception as e:
            QMessageBox.critical(self, translate("dialogs.pulse.import_pulse.read_error"),
                                 translate("dialogs.pulse.import_pulse.read_failed").format(str(e)))
            return

        try:
            self.imported_pulses.clear()
            self.pulse_list.clear()

            pulses: Dict[str, List[PulseOperation]] = data['pulses']

            valid_count = 0
            error_count = 0
            warnings: List[str] = []

            for name, pulse_data in pulses.items():
                # 类型转换：确保pulse_data是List[PulseOperation]格式
                name_str: str = str(name)
                pulse_data_typed: List[PulseOperation] = pulse_data

                # 验证波形数据格式
                is_valid, errors = self.validate_pulse_operation(pulse_data_typed)

                if is_valid:
                    # 检查数据完整性
                    integrity = self.check_pulse_data_integrity(pulse_data_typed)

                    self.imported_pulses.append({
                        'name': name_str,
                        'data': pulse_data_typed,
                        'integrity': integrity
                    })

                    item = QListWidgetItem(name_str)
                    item.setData(Qt.ItemDataRole.UserRole, len(self.imported_pulses) - 1)

                    # 根据完整性检查设置图标或提示
                    integrity_warnings = integrity.get('warnings', [])
                    if integrity_warnings:
                        item.setToolTip(
                            f"{translate('dialogs.pulse.import_pulse.preview.warnings')}: {'; '.join(integrity_warnings)}")
                        warnings.extend(integrity_warnings)

                    self.pulse_list.addItem(item)
                    valid_count += 1
                else:
                    error_count += 1
                    logger.warning(f"跳过无效波形 '{name_str}': {'; '.join(errors)}")

            # 显示导入结果
            if valid_count > 0:
                message = translate("dialogs.pulse.import_pulse.import_success_msg").format(valid_count)
                if error_count > 0:
                    message += translate("dialogs.pulse.import_pulse.skipped_invalid").format(error_count)
                if warnings:
                    message += f"\n\n{translate('dialogs.pulse.import_pulse.preview.warnings')}:\n" + '\n'.join(
                        set(warnings))
                    QMessageBox.warning(self, translate("dialogs.pulse.import_pulse.import_complete"), message)
                else:
                    QMessageBox.information(self, translate("dialogs.pulse.import_pulse.import_success"), message)
            else:
                if error_count > 0:
                    QMessageBox.critical(self, translate("dialogs.pulse.import_pulse.import_failed"),
                                         translate("dialogs.pulse.import_pulse.all_invalid"))
                else:
                    QMessageBox.warning(self, translate("dialogs.pulse.import_pulse.import_failed"),
                                        translate("dialogs.pulse.import_pulse.no_valid_data"))

        except KeyError as e:
            QMessageBox.critical(self, translate("dialogs.pulse.import_pulse.data_error"),
                                 translate("dialogs.pulse.import_pulse.missing_field").format(str(e)))
        except Exception as e:
            QMessageBox.critical(self, translate("dialogs.pulse.import_pulse.process_error"),
                                 translate("dialogs.pulse.import_pulse.process_failed").format(str(e)))

    def update_preview(self) -> None:
        """更新预览"""
        selected_items = self.pulse_list.selectedItems()
        if selected_items:
            item = selected_items[0]
            index: int = item.data(Qt.ItemDataRole.UserRole)
            pulse: PulseDict = self.imported_pulses[index]

            preview_text = f"{translate('dialogs.pulse.import_pulse.preview.name')}: {pulse['name']}\n"
            preview_text += f"{translate('dialogs.pulse.import_pulse.preview.steps')}: {len(pulse['data'])}\n"

            # 显示统计信息
            if 'integrity' in pulse:
                stats = pulse['integrity']['stats']
                preview_text += f"{translate('dialogs.pulse.import_pulse.preview.duration')}: {stats['duration_ms']}ms\n"
                preview_text += f"{translate('dialogs.pulse.import_pulse.preview.max_frequency')}: {stats['max_frequency']}\n"
                preview_text += f"{translate('dialogs.pulse.import_pulse.preview.max_intensity')}: {stats['max_intensity']}\n"

                # 显示警告
                if pulse['integrity']['warnings']:
                    preview_text += f"\n{translate('dialogs.pulse.import_pulse.preview.warnings')}:\n"
                    for warning in pulse['integrity']['warnings']:
                        preview_text += f"• {warning}\n"

            preview_text += f"\n{translate('dialogs.pulse.import_pulse.preview.first_3_steps')}:\n{str(pulse['data'][:3])}"

            self.preview_text.setText(preview_text)
        else:
            self.preview_text.clear()

    def select_all(self) -> None:
        """全选"""
        for i in range(self.pulse_list.count()):
            self.pulse_list.item(i).setSelected(True)

    def clear_selection(self) -> None:
        """清除选择"""
        self.pulse_list.clearSelection()

    def get_selected_pulses(self) -> List[PulseDict]:
        """获取选中的波形"""
        # 检查当前是哪个标签页
        current_index = self.tab_widget.currentIndex()
        
        if current_index == 0:  # 文件导入
            # 现有文件导入逻辑
            selected_pulses: List[PulseDict] = []
            for item in self.pulse_list.selectedItems():
                index: int = item.data(Qt.ItemDataRole.UserRole)
                selected_pulses.append(self.imported_pulses[index])
            return selected_pulses
        elif current_index == 1:  # 分享码导入
            return self.get_share_code_pulses()
        elif current_index == 2:  # 官方波形导入
            return self.get_official_pulse_data()
        
        return []
    
    def get_share_code_pulses(self) -> List[PulseDict]:
        """获取分享码解析的波形 (Pydantic版本)"""
        share_code = self.share_code_edit.toPlainText().strip()
        
        if not share_code:
            return []
        
        try:
            parsed = WaveformShareCodec.decode_share_code(share_code)
            
            if parsed.validation.is_valid:
                pulse_data = parsed.pulse_data
                
                return [{
                    'name': pulse_data.name,
                    'data': pulse_data.data,
                    'integrity': {
                        'valid': True,
                        'issues': [],
                        'warnings': parsed.validation.warnings,
                        'stats': {
                            'steps': pulse_data.metadata.steps,
                            'max_frequency': pulse_data.metadata.max_frequency,
                            'max_intensity': pulse_data.metadata.max_intensity,
                            'duration_ms': len(pulse_data.data) * 100  # 基于数据长度计算
                        }
                    }
                }]
            
        except Exception as e:
            logger.error(f"Failed to get share code pulses: {e}")
        
        return []
    
    def browse_official_pulse_files(self) -> None:
        """浏览并选择多个.pulse文件"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, translate("dialogs.pulse.import_pulse.select_official_files"), "", "Pulse文件 (*.pulse);;所有文件 (*)"
        )
        
        if file_paths:
            self.load_official_pulse_files(file_paths)
    
    def load_official_pulse_files(self, file_paths: List[str]) -> None:
        """加载多个官方.pulse文件"""
        parser = PulseFileParser()
        loaded_files: List[OfficialPulseFileInfo] = []
        success_count = 0
        error_count = 0
        error_messages: List[str] = []
        
        for file_path in file_paths:
            try:
                # 解析文件
                result = parser.parse_file(file_path)
                
                if result.success and result.data:
                    # 转换为PulseOperation
                    pulse_operations = parser.convert_to_pulse_operations(result.data.header, result.data.sections)
                    
                    # 生成波形名称（使用文件名）
                    import os
                    file_name = os.path.splitext(os.path.basename(file_path))[0]
                    pulse_name = f"官方-{file_name}"
                    
                    # 计算统计信息
                    if pulse_operations:
                        frequencies = [freq[0] for freq, _ in pulse_operations]
                        intensities = [intensity[0] for _, intensity in pulse_operations]
                        max_frequency = max(frequencies) if frequencies else 0
                        max_intensity = max(intensities) if intensities else 0
                    else:
                        max_frequency = 0
                        max_intensity = 0
                    
                    file_info: OfficialPulseFileInfo = {
                        'file_path': file_path,
                        'file_name': file_name,
                        'pulse_name': pulse_name,
                        'pulse_data': result.data,
                        'pulse_operations': pulse_operations,
                        'warnings': [w.message for w in result.warnings],
                        'stats': {
                            'steps': len(pulse_operations),
                            'duration_ms': len(pulse_operations) * 100,
                            'max_frequency': max_frequency,
                            'max_intensity': max_intensity,
                            'sections': len(result.data.sections),
                            'enabled_sections': sum(1 for s in result.data.sections if s.enabled),
                            'rest_duration': result.data.header.rest_duration,
                            'speed_multiplier': result.data.header.speed_multiplier
                        }
                    }
                    
                    loaded_files.append(file_info)
                    success_count += 1
                else:
                    error_count += 1
                    errors = [e.message for e in result.errors]
                    error_messages.extend(errors)
                    logger.warning(f"解析文件失败 '{file_path}': {'; '.join(errors)}")
                    
            except Exception as e:
                error_count += 1
                error_msg = f"加载文件 '{file_path}' 时发生异常: {e}"
                error_messages.append(error_msg)
                logger.error(error_msg)
        
        # 更新UI
        if loaded_files:
            self.official_pulse_files.extend(loaded_files)
            self.update_official_files_list()
            
            # 显示加载结果
            if error_count > 0:
                message = translate("dialogs.pulse.import_pulse.partial_load_msg").format(success_count, error_count) + "\n\n"
                if error_messages:
                    message += translate("dialogs.pulse.import_pulse.error_details") + "\n" + "\n".join(error_messages[:5])  # 只显示前5个错误
                    if len(error_messages) > 5:
                        message += "\n" + translate("dialogs.pulse.import_pulse.more_errors").format(len(error_messages) - 5)
                QMessageBox.warning(self, translate("dialogs.pulse.import_pulse.partial_load_success"), message)
            else:
                QMessageBox.information(self, translate("dialogs.pulse.import_pulse.load_success"), 
                                      translate("dialogs.pulse.import_pulse.load_success_msg").format(success_count))
        else:
            if error_messages:
                message = translate("dialogs.pulse.import_pulse.all_files_failed") + ":\n" + "\n".join(error_messages[:3])
                if len(error_messages) > 3:
                    message += "\n" + translate("dialogs.pulse.import_pulse.more_errors").format(len(error_messages) - 3)
            else:
                message = translate("dialogs.pulse.import_pulse.no_files_loaded")
            QMessageBox.critical(self, translate("dialogs.pulse.import_pulse.load_failed"), message)
    
    def update_official_files_list(self) -> None:
        """更新官方文件列表显示"""
        self.official_files_list.clear()
        
        for i, file_info in enumerate(self.official_pulse_files):
            item_text = f"{file_info['file_name']} ({file_info['stats']['steps']}步, {file_info['stats']['duration_ms']}ms)"
            if file_info['warnings']:
                item_text += " ⚠️"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, i)
            item.setSelected(True)  # 默认选中
            self.official_files_list.addItem(item)
    
    def update_official_pulse_preview(self) -> None:
        """更新官方波形预览"""
        selected_items = self.official_files_list.selectedItems()
        
        if not selected_items:
            self.official_files_info_preview.clear()
            return
        
        # 显示选中文件的信息
        if len(selected_items) == 1:
            # 单个文件详细信息
            item = selected_items[0]
            index: int = item.data(Qt.ItemDataRole.UserRole)
            file_info: OfficialPulseFileInfo = self.official_pulse_files[index]
            
            # 合并文件信息和波形预览
            combined_text = f"📁 {translate('dialogs.pulse.import_pulse.file_stats.file')}: {file_info['file_name']}\n"
            combined_text += f"⏱️ {translate('dialogs.pulse.import_pulse.file_stats.rest_duration')}: {file_info['stats']['rest_duration']:.1f}s\n"
            combined_text += f"⚡ {translate('dialogs.pulse.import_pulse.file_stats.speed_multiplier')}: {file_info['stats']['speed_multiplier']}x\n"
            combined_text += f"📊 {translate('dialogs.pulse.import_pulse.file_stats.sections')}: {file_info['stats']['sections']}\n"
            combined_text += f"✅ {translate('dialogs.pulse.import_pulse.file_stats.enabled_sections')}: {file_info['stats']['enabled_sections']}\n"
            
            if file_info['warnings']:
                combined_text += f"⚠️ {translate('dialogs.pulse.import_pulse.file_stats.warnings')}: {len(file_info['warnings'])}个\n"
            
            # 分隔线
            combined_text += "\n" + "─" * 40 + "\n\n"
            
            # 波形预览信息
            stats = file_info['stats']
            combined_text += f"🎵 {translate('dialogs.pulse.import_pulse.file_stats.waveform_name')}: {file_info['pulse_name']}\n"
            combined_text += f"📈 {translate('dialogs.pulse.import_pulse.file_stats.total_steps')}: {stats['steps']}\n"
            combined_text += f"⏰ {translate('dialogs.pulse.import_pulse.file_stats.duration')}: {stats['duration_ms']}ms ({stats['duration_ms']/1000:.1f}s)\n"
            combined_text += f"🔊 {translate('dialogs.pulse.import_pulse.file_stats.max_frequency')}: {stats['max_frequency']}\n"
            combined_text += f"💪 {translate('dialogs.pulse.import_pulse.file_stats.max_intensity')}: {stats['max_intensity']}%"
            
            if file_info['warnings']:
                combined_text += f"\n\n⚠️ {translate('dialogs.pulse.import_pulse.file_stats.warnings')}:\n" + "\n".join(f"• {w}" for w in file_info['warnings'][:3])
                if len(file_info['warnings']) > 3:
                    combined_text += f"\n" + translate("dialogs.pulse.import_pulse.more_errors").format(len(file_info['warnings']) - 3)
            
            self.official_files_info_preview.setText(combined_text)
        else:
            # 多个文件统计信息
            total_steps = 0
            total_duration = 0
            total_warnings = 0
            
            for item in selected_items:
                item_index: int = item.data(Qt.ItemDataRole.UserRole)
                item_file_info: OfficialPulseFileInfo = self.official_pulse_files[item_index]
                total_steps += item_file_info['stats']['steps']
                total_duration += item_file_info['stats']['duration_ms']
                total_warnings += len(item_file_info['warnings'])
            
            # 合并多文件统计信息
            combined_text = f"📁 {translate('dialogs.pulse.import_pulse.file_stats.selected_files_count').format(len(selected_items))}\n\n"
            combined_text += f"📊 {translate('dialogs.pulse.import_pulse.file_stats.selected_stats')}:\n"
            combined_text += f"📈 {translate('dialogs.pulse.import_pulse.file_stats.total_steps')}: {total_steps}\n"
            combined_text += f"⏰ {translate('dialogs.pulse.import_pulse.file_stats.total_duration')}: {total_duration}ms ({total_duration/1000:.1f}s)\n"
            combined_text += f"🗂️ {translate('dialogs.pulse.import_pulse.file_stats.file_count')}: {len(selected_items)}"
            
            if total_warnings > 0:
                combined_text += f"\n⚠️ {translate('dialogs.pulse.import_pulse.file_stats.total_warnings')}: {total_warnings}"
            
            self.official_files_info_preview.setText(combined_text)
    
    def clear_official_pulse_files(self) -> None:
        """清空官方波形文件"""
        self.official_pulse_files.clear()
        self.official_files_list.clear()
        self.official_files_info_preview.clear()
    
    def select_all_official_files(self) -> None:
        """选择所有官方文件"""
        for i in range(self.official_files_list.count()):
            self.official_files_list.item(i).setSelected(True)
    
    def clear_official_selection(self) -> None:
        """清除官方文件选择"""
        self.official_files_list.clearSelection()
    
    def get_official_pulse_data(self) -> List[PulseDict]:
        """获取选中的官方波形数据"""
        selected_items = self.official_files_list.selectedItems()
        selected_pulses: List[PulseDict] = []
        
        for item in selected_items:
            index: int = item.data(Qt.ItemDataRole.UserRole)
            file_info: OfficialPulseFileInfo = self.official_pulse_files[index]
            
            # 创建完整性报告
            integrity_report: IntegrityReport = {
                'valid': True,
                'issues': [],
                'warnings': file_info['warnings'],
                'stats': file_info['stats']
            }
            
            pulse_dict: PulseDict = {
                'name': file_info['pulse_name'],
                'data': file_info['pulse_operations'],
                'integrity': integrity_report
            }
            
            selected_pulses.append(pulse_dict)
        
        return selected_pulses


class ExportPulseDialog(QDialog):
    """导出波形对话框"""

    def __init__(self, pulses: List[Pulse], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pulses = pulses
        
        # UI组件类型注解
        self.pulse_list: QListWidget
        self.file_path_edit: QLineEdit
        self.copy_share_code_btn: QPushButton
        self.tab_widget: QTabWidget
        self.share_pulse_list: QListWidget
        self.share_code_text: QTextEdit

        self.setWindowTitle(translate("dialogs.pulse.export_pulse.title"))
        self.setModal(True)
        self.resize(800, 650)
        self.setup_ui()
        self.apply_style()

    def setup_ui(self) -> None:
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel(translate("dialogs.pulse.export_pulse.export_file"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # 使用标签页来分离文件导出和分享码导出
        self.tab_widget = QTabWidget()
        
        # 文件导出标签页
        file_tab = self.create_file_export_tab()
        self.tab_widget.addTab(file_tab, "导出到文件")
        
        # 分享码导出标签页
        share_code_tab = self.create_share_code_export_tab()
        self.tab_widget.addTab(share_code_tab, "生成分享码")
        
        layout.addWidget(self.tab_widget)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.handle_export)
        button_box.rejected.connect(self.reject)
        button_layout.addWidget(button_box)

        layout.addLayout(button_layout)
    
    def create_file_export_tab(self) -> QWidget:
        """创建文件导出标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 波形选择
        list_label = QLabel(translate("dialogs.pulse.export_pulse.select_pulses"))
        layout.addWidget(list_label)

        self.pulse_list = QListWidget()
        self.pulse_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

        for pulse in self.pulses:
            item = QListWidgetItem(pulse.name)
            item.setData(Qt.ItemDataRole.UserRole, pulse)
            item.setSelected(True)  # 默认全选
            self.pulse_list.addItem(item)

        layout.addWidget(self.pulse_list)

        # 文件路径选择
        file_layout = QHBoxLayout()

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText(translate("dialogs.pulse.export_pulse.save_path"))
        file_layout.addWidget(self.file_path_edit)

        browse_btn = QPushButton(translate("dialogs.pulse.import_pulse.browse"))
        browse_btn.clicked.connect(self.browse_save_path)
        file_layout.addWidget(browse_btn)

        layout.addLayout(file_layout)

        # 选择按钮
        button_layout = QHBoxLayout()

        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)

        clear_btn = QPushButton(translate("dialogs.pulse.import_pulse.clear_selection"))
        clear_btn.clicked.connect(self.clear_selection)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 连接选择变化事件
        self.pulse_list.itemSelectionChanged.connect(self.on_selection_changed)
        
        return tab
    
    def create_share_code_export_tab(self) -> QWidget:
        """创建分享码导出标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 波形选择
        list_label = QLabel("选择要生成分享码的波形：")
        layout.addWidget(list_label)
        
        self.share_pulse_list = QListWidget()
        self.share_pulse_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        
        for pulse in self.pulses:
            item = QListWidgetItem(pulse.name)
            item.setData(Qt.ItemDataRole.UserRole, pulse)
            self.share_pulse_list.addItem(item)
        
        # 默认选中第一个
        if self.pulses:
            self.share_pulse_list.setCurrentRow(0)
        
        layout.addWidget(self.share_pulse_list)
        
        # 分享码显示区域
        share_code_label = QLabel("分享码：")
        layout.addWidget(share_code_label)
        
        self.share_code_text = QTextEdit()
        self.share_code_text.setMaximumHeight(120)
        self.share_code_text.setReadOnly(True)
        layout.addWidget(self.share_code_text)
        
        # 复制按钮
        copy_layout = QHBoxLayout()
        copy_layout.addStretch()
        
        self.copy_share_code_btn = QPushButton("复制分享码")
        self.copy_share_code_btn.clicked.connect(self.copy_share_code)
        self.copy_share_code_btn.setEnabled(False)
        copy_layout.addWidget(self.copy_share_code_btn)
        
        layout.addLayout(copy_layout)
        
        # 连接信号
        self.share_pulse_list.itemSelectionChanged.connect(self.on_share_selection_changed)
        
        return tab

    def apply_style(self) -> None:
        """应用样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
                font-weight: 500;
            }
            QLineEdit {
                background-color: #2a2a2a;
                border: 2px solid #444444;
                padding: 10px 12px;
                border-radius: 6px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #d4af37;
                background-color: #2f2f2f;
            }
            QComboBox {
                background-color: #2a2a2a;
                border: 2px solid #444444;
                padding: 8px 12px;
                border-radius: 6px;
                color: #ffffff;
                font-size: 13px;
                min-width: 120px;
            }
            QComboBox:focus {
                border-color: #d4af37;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border: 2px solid #d4af37;
                width: 8px;
                height: 8px;
                border-top: none;
                border-right: none;
                transform: rotate(-45deg);
            }
            QListWidget {
                background-color: #2a2a2a;
                border: 2px solid #444444;
                border-radius: 6px;
                color: #ffffff;
                outline: none;
            }
            QListWidget::item {
                padding: 12px 15px;
                border-bottom: 1px solid #333333;
                border-radius: 4px;
                margin: 1px;
            }
            QListWidget::item:selected {
                background-color: #d4af37;
                color: #000000;
                font-weight: 600;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
            }
            QListWidget::item:selected:hover {
                background-color: #e6c547;
            }
            QPushButton {
                background-color: #d4af37;
                color: #000000;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #e6c547;
            }
            QPushButton:pressed {
                background-color: #c4a030;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
            QTabWidget::pane {
                border: 2px solid #444444;
                background-color: #2a2a2a;
                border-radius: 8px;
                margin-top: 8px;
            }
            QTabBar::tab {
                background-color: #333333;
                color: #cccccc;
                border: 1px solid #555555;
                padding: 14px 28px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
                min-width: 120px;
            }
            QTabBar::tab:selected {
                background-color: #d4af37;
                color: #000000;
                border-bottom: 2px solid #d4af37;
                font-weight: 600;
            }
            QTabBar::tab:hover {
                background-color: #444444;
                color: #ffffff;
            }
            QTabBar::tab:selected:hover {
                background-color: #e6c547;
            }
        """)

    def get_default_filename(self) -> str:
        """生成默认文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"dg_lab_pulses_{timestamp}.json"

    def browse_save_path(self) -> None:
        """浏览保存路径"""
        default_filename = self.get_default_filename()
        file_path, _ = QFileDialog.getSaveFileName(
            self, translate("dialogs.pulse.export_pulse.save_path"), default_filename, "JSON文件 (*.json);;所有文件 (*)"
        )

        if file_path:
            self.file_path_edit.setText(file_path)

    def select_all(self) -> None:
        """全选"""
        for i in range(self.pulse_list.count()):
            self.pulse_list.item(i).setSelected(True)

    def clear_selection(self) -> None:
        """清除选择"""
        self.pulse_list.clearSelection()
    
    def on_selection_changed(self) -> None:
        """选择变化处理"""
        selected_items = self.pulse_list.selectedItems()
        # 分享码功能只支持单选
        self.copy_share_code_btn.setEnabled(len(selected_items) == 1)
    
    def copy_share_code(self) -> None:
        """复制选中波形的分享码到剪贴板"""
        current_tab = self.tab_widget.currentIndex()
        
        if current_tab == 0:  # 文件导出标签页
            selected_items = self.pulse_list.selectedItems()
            if len(selected_items) != 1:
                QMessageBox.warning(self, "选择错误", "请选择一个波形生成分享码")
                return
            pulse = selected_items[0].data(Qt.ItemDataRole.UserRole)
        elif current_tab == 1:  # 分享码导出标签页
            selected_items = self.share_pulse_list.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "选择错误", "请选择一个波形生成分享码")
                return
            pulse = selected_items[0].data(Qt.ItemDataRole.UserRole)
        else:
            return
        
        try:
            share_code = WaveformShareCodec.encode_pulse(pulse)
            
            # 复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setText(share_code)
            
            # 显示详细信息
            info_text = (
                f"波形 '{pulse.name}' 的分享码已复制到剪贴板\n\n"
                f"分享码长度: {len(share_code)} 字符\n"
                f"数据完整性: SHA256 校验\n"
                f"波形步数: {len(pulse.data)} 步\n"
                f"预估持续时间: {len(pulse.data) * 100}ms"
            )
            
            QMessageBox.information(self, "分享成功", info_text)
            logger.info(f"Share code copied for pulse: {pulse.name}")
            
        except ValidationError as e:
            error_details: List[str] = []
            for error in e.errors():
                field = " -> ".join(str(x) for x in error['loc'])
                error_details.append(f"{field}: {error['msg']}")
            
            QMessageBox.critical(self, "数据验证失败", 
                               f"波形数据不符合要求:\n" + "\n".join(error_details))
            
        except Exception as e:
            QMessageBox.critical(self, "生成失败", f"生成分享码失败: {e}")

    def export_pulses(self) -> None:
        """导出波形"""
        file_path = self.file_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(self, translate("dialogs.pulse.export_pulse.path_error"),
                                translate("dialogs.pulse.export_pulse.select_save_path"))
            return

        selected_items = self.pulse_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, translate("dialogs.pulse.export_pulse.selection_error"),
                                translate("dialogs.pulse.export_pulse.select_at_least_one"))
            return

        try:
            # 收集选中的波形并验证数据
            export_data: Dict[str, List[PulseOperation]] = {}
            total_steps = 0

            for item in selected_items:
                pulse = item.data(Qt.ItemDataRole.UserRole)

                # 确保数据格式正确
                pulse_data = list(pulse.data)
                export_data[pulse.name] = pulse_data
                total_steps += len(pulse_data)

            # 创建导出数据
            final_data: PulseFileExportData = {
                "pulses": export_data
            }

            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, ensure_ascii=False, indent=2)

            # 显示导出成功信息
            duration_ms = total_steps * 100

            message = translate("dialogs.pulse.export_pulse.export_success_msg").format(
                os.path.basename(file_path),
                len(selected_items),
                total_steps,
                duration_ms,
                duration_ms / 1000
            )

            QMessageBox.information(self, translate("dialogs.pulse.export_pulse.export_success"), message)
            self.accept()

        except PermissionError:
            QMessageBox.critical(self, translate("dialogs.pulse.export_pulse.permission_error"),
                                 translate("dialogs.pulse.export_pulse.no_write_permission"))
        except OSError as e:
            QMessageBox.critical(self, translate("dialogs.pulse.export_pulse.file_error"),
                                 translate("dialogs.pulse.export_pulse.cannot_create").format(str(e)))
        except Exception as e:
            QMessageBox.critical(self, translate("dialogs.pulse.export_pulse.export_error"),
                                 translate("dialogs.pulse.export_pulse.save_failed").format(str(e)))
    
    def handle_export(self) -> None:
        """处理导出操作"""
        current_tab = self.tab_widget.currentIndex()
        
        if current_tab == 0:  # 文件导出
            self.export_pulses()
        elif current_tab == 1:  # 分享码导出
            self.copy_share_code()
            self.accept()  # 关闭对话框
    
    def on_share_selection_changed(self) -> None:
        """分享码选择变化处理"""
        selected_items = self.share_pulse_list.selectedItems()
        
        if selected_items:
            pulse = selected_items[0].data(Qt.ItemDataRole.UserRole)
            try:
                share_code = WaveformShareCodec.encode_pulse(pulse)
                self.share_code_text.setText(share_code)
                self.copy_share_code_btn.setEnabled(True)
            except Exception as e:
                self.share_code_text.setText(f"生成分享码失败: {e}")
                self.copy_share_code_btn.setEnabled(False)
        else:
            self.share_code_text.clear()
            self.copy_share_code_btn.setEnabled(False)


class PulseInfoDialog(QDialog):
    """波形信息对话框"""

    def __init__(self, pulse: Pulse, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pulse = pulse
        
        # UI组件类型注解
        self.data_text: QTextEdit

        self.setWindowTitle(f"{translate('dialogs.pulse.pulse_info.title')} - {pulse.name}")
        self.setModal(True)
        self.resize(800, 650)
        self.setMinimumSize(700, 500)
        self.setup_ui()
        self.apply_style()

    def setup_ui(self) -> None:
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel(f"{translate('dialogs.pulse.pulse_info.pulse_name')}: {self.pulse.name}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # 信息表单
        form_layout = QFormLayout()

        # 基本信息
        form_layout.addRow(translate("dialogs.pulse.pulse_info.index_label"), QLabel(str(self.pulse.id)))
        form_layout.addRow(translate("dialogs.pulse.pulse_info.steps_label"), QLabel(str(len(self.pulse.data))))

        # 强度统计
        intensities = [step[1][0] for step in self.pulse.data]  # 使用第一个强度值
        if intensities:
            form_layout.addRow(translate("dialogs.pulse.pulse_info.min_intensity_label"),
                               QLabel(f"{min(intensities)}%"))
            form_layout.addRow(translate("dialogs.pulse.pulse_info.max_intensity_label"),
                               QLabel(f"{max(intensities)}%"))
            form_layout.addRow(translate("dialogs.pulse.pulse_info.avg_intensity_label"),
                               QLabel(f"{sum(intensities) / len(intensities):.1f}%"))

        layout.addLayout(form_layout)

        # 详细数据
        data_label = QLabel(translate("dialogs.pulse.pulse_info.detailed_data_label"))
        layout.addWidget(data_label)

        self.data_text = QTextEdit()
        self.data_text.setReadOnly(True)

        # 格式化显示数据
        data_str = translate("dialogs.pulse.pulse_info.step_header") + "\n"
        data_str += "-" * 40 + "\n"

        for i, (duration, intensity) in enumerate(self.pulse.data):
            data_str += f"{i + 1}\t{duration[0]}ms\t{intensity[0]}%\n"

        self.data_text.setText(data_str)
        layout.addWidget(self.data_text)

        # 关闭按钮
        close_btn = QPushButton(translate("dialogs.pulse.pulse_info.close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def apply_style(self) -> None:
        """应用样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
                font-weight: 500;
            }
            QTextEdit {
                background-color: #2a2a2a;
                border: 2px solid #444444;
                padding: 10px 12px;
                border-radius: 6px;
                color: #ffffff;
                font-size: 12px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border-color: #d4af37;
                background-color: #2f2f2f;
            }
            QPushButton {
                background-color: #d4af37;
                color: #000000;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #e6c547;
            }
            QPushButton:pressed {
                background-color: #c4a030;
            }
        """)
