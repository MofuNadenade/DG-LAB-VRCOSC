"""
波形编辑器对话框组件

包含新建、导入、导出等对话框
"""

import json
import os
from typing import Optional, List, Tuple, Union
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QTextEdit, QFileDialog, QMessageBox, QFormLayout,
    QDialogButtonBox, QComboBox, QSpinBox, QListWidget, QListWidgetItem,
    QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from models import PulseOperation, PulseDict, IntegrityReport
from core.dglab_pulse import Pulse
from i18n import translate as _
import logging

logger = logging.getLogger(__name__)


class NewPulseDialog(QDialog):
    """新建波形对话框"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pulse_name = ""
        self.template_data: List[PulseOperation] = []
        
        self.setWindowTitle(_("pulse_dialogs.new_pulse.title"))
        self.setModal(True)
        self.resize(400, 300)
        self.setup_ui()
        self.apply_style()
        
    def setup_ui(self) -> None:
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel(_("pulse_dialogs.new_pulse.create_new"))
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
        self.name_edit.setPlaceholderText(_("pulse_dialogs.new_pulse.name_placeholder"))
        form_layout.addRow(_("pulse_dialogs.new_pulse.pulse_name_label"), self.name_edit)
        
        # 模板选择
        self.template_combo = QComboBox()
        self.template_combo.addItem(_("pulse_dialogs.new_pulse.blank_waveform"), [])
        self.template_combo.addItem(_("pulse_dialogs.new_pulse.simple_pulse"), [
            ((10, 10, 10, 10), (100, 100, 100, 100)),
            ((10, 10, 10, 10), (0, 0, 0, 0))
        ])
        self.template_combo.addItem(_("pulse_dialogs.new_pulse.progressive_waveform"), [
            ((10, 10, 10, 10), (20, 20, 20, 20)),
            ((10, 10, 10, 10), (40, 40, 40, 40)),
            ((10, 10, 10, 10), (60, 60, 60, 60)),
            ((10, 10, 10, 10), (80, 80, 80, 80)),
            ((10, 10, 10, 10), (100, 100, 100, 100))
        ])
        self.template_combo.addItem(_("pulse_dialogs.new_pulse.pulse_sequence"), [
            ((10, 10, 10, 10), (100, 100, 100, 100)),
            ((10, 10, 10, 10), (0, 0, 0, 0)),
            ((10, 10, 10, 10), (100, 100, 100, 100)),
            ((10, 10, 10, 10), (0, 0, 0, 0)),
            ((10, 10, 10, 10), (100, 100, 100, 100)),
            ((10, 10, 10, 10), (0, 0, 0, 0))
        ])
        form_layout.addRow(_("pulse_dialogs.new_pulse.base_template_label"), self.template_combo)
        
        # 初始步数
        self.steps_spinbox = QSpinBox()
        self.steps_spinbox.setRange(1, 50)
        self.steps_spinbox.setValue(8)
        form_layout.addRow(_("pulse_dialogs.new_pulse.initial_steps_label"), self.steps_spinbox)
        
        layout.addLayout(form_layout)
        
        # 描述
        desc_label = QLabel(_("pulse_dialogs.new_pulse.description_label"))
        layout.addWidget(desc_label)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText(_("pulse_dialogs.new_pulse.description_placeholder"))
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
                color: white;
            }
            QLabel {
                color: white;
            }
            QLineEdit, QTextEdit, QComboBox, QSpinBox {
                background-color: #333;
                color: white;
                border: 1px solid #d4af37;
                padding: 5px;
                border-radius: 3px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                border: none;
                background: #d4af37;
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
            QMessageBox.warning(self, _("pulse_dialogs.new_pulse.input_error"), _("pulse_dialogs.new_pulse.name_required"))
            return False
        return True


class ImportPulseDialog(QDialog):
    """导入波形对话框"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.imported_pulses: List[PulseDict] = []
        
        self.setWindowTitle(_("pulse_dialogs.import_pulse.title"))
        self.setModal(True)
        self.resize(500, 400)
        self.setup_ui()
        self.apply_style()
        
    def setup_ui(self) -> None:
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel(_("pulse_dialogs.import_pulse.import_file"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        
        # 文件选择
        file_layout = QHBoxLayout()
        
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText(_("pulse_dialogs.import_pulse.select_file"))
        self.file_path_edit.setReadOnly(True)
        file_layout.addWidget(self.file_path_edit)
        
        browse_btn = QPushButton(_("pulse_dialogs.import_pulse.browse"))
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_btn)
        
        layout.addLayout(file_layout)
        
        # 波形列表
        list_label = QLabel(_("pulse_dialogs.import_pulse.pulses_in_file"))
        layout.addWidget(list_label)
        
        self.pulse_list = QListWidget()
        self.pulse_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.pulse_list)
        
        # 预览区域
        preview_label = QLabel(_("pulse_dialogs.import_pulse.pulse_preview"))
        layout.addWidget(preview_label)
        
        self.preview_text = QTextEdit()
        self.preview_text.setMaximumHeight(100)
        self.preview_text.setReadOnly(True)
        layout.addWidget(self.preview_text)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        select_all_btn = QPushButton(_("pulse_dialogs.import_pulse.select_all"))
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)
        
        clear_btn = QPushButton(_("pulse_dialogs.import_pulse.clear_selection"))
        clear_btn.clicked.connect(self.clear_selection)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_layout.addWidget(button_box)
        
        layout.addLayout(button_layout)
        
        # 连接信号
        self.pulse_list.itemSelectionChanged.connect(self.update_preview)
    
    def validate_pulse_operation(self, data: Union[List[PulseOperation], List[object], object]) -> Tuple[bool, List[str]]:
        """验证PulseOperation格式"""
        errors = []
        
        if not isinstance(data, list):
            errors.append(_("pulse_dialogs.import_pulse.validation.data_must_list"))
            return False, errors
            
        if len(data) == 0:
            errors.append(_("pulse_dialogs.import_pulse.validation.data_not_empty"))
            return False, errors
            
        for i, item in enumerate(data):
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                errors.append(_("pulse_dialogs.import_pulse.validation.step_format").format(i+1))
                continue
                
            freq, intensity = item
            
            # 验证频率数据
            if not isinstance(freq, (list, tuple)) or len(freq) != 4:
                errors.append(_("pulse_dialogs.import_pulse.validation.freq_4_values").format(i+1))
            elif not all(isinstance(x, int) for x in freq):
                errors.append(_("pulse_dialogs.import_pulse.validation.freq_must_int").format(i+1))
            elif any(f < 10 or f > 240 for f in freq):
                errors.append(_("pulse_dialogs.import_pulse.validation.freq_range").format(i+1))
                
            # 验证强度数据
            if not isinstance(intensity, (list, tuple)) or len(intensity) != 4:
                errors.append(_("pulse_dialogs.import_pulse.validation.intensity_4_values").format(i+1))
            elif not all(isinstance(x, int) for x in intensity):
                errors.append(_("pulse_dialogs.import_pulse.validation.intensity_must_int").format(i+1))
            elif any(s < 0 or s > 100 for s in intensity):
                errors.append(_("pulse_dialogs.import_pulse.validation.intensity_range").format(i+1))
        
        return len(errors) == 0, errors
    
    def check_pulse_data_integrity(self, pulse_data: List[PulseOperation]) -> IntegrityReport:
        """检查波形数据完整性"""
        issues: List[str] = []
        warnings: List[str] = []
        
        # 检查数据长度
        if len(pulse_data) > 100:
            warnings.append(_("pulse_dialogs.import_pulse.validation.too_many_steps").format(len(pulse_data)))
        elif len(pulse_data) > 50:
            warnings.append(_("pulse_dialogs.import_pulse.validation.many_steps").format(len(pulse_data)))
        
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
            warnings.append(_("pulse_dialogs.import_pulse.validation.high_frequency").format(max_freq))
        if max_intensity > 150:
            warnings.append(_("pulse_dialogs.import_pulse.validation.high_intensity").format(max_intensity))
        
        # 检查数据变化
        if len(set(intensities)) == 1:
            warnings.append(_("pulse_dialogs.import_pulse.validation.monotonic"))
        
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
                color: white;
            }
            QLabel {
                color: white;
            }
            QLineEdit, QTextEdit, QListWidget {
                background-color: #333;
                color: white;
                border: 1px solid #d4af37;
                padding: 5px;
                border-radius: 3px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #555;
            }
            QListWidget::item:selected {
                background-color: #d4af37;
                color: black;
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
        """)
        
    def browse_file(self) -> None:
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, _("pulse_dialogs.import_pulse.select_file"), "", "JSON文件 (*.json);;所有文件 (*)"
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
            QMessageBox.critical(self, _("pulse_dialogs.import_pulse.file_error"), _("pulse_dialogs.import_pulse.file_not_found"))
            return
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, _("pulse_dialogs.import_pulse.format_error"), _("pulse_dialogs.import_pulse.json_invalid").format(str(e)))
            return
        except UnicodeDecodeError:
            QMessageBox.critical(self, _("pulse_dialogs.import_pulse.encoding_error"), _("pulse_dialogs.import_pulse.encoding_unsupported"))
            return
        except Exception as e:
            QMessageBox.critical(self, _("pulse_dialogs.import_pulse.read_error"), _("pulse_dialogs.import_pulse.read_failed").format(str(e)))
            return
            
        try:
            self.imported_pulses.clear()
            self.pulse_list.clear()
            
            # 处理不同的文件格式
            if isinstance(data, dict):
                if 'pulses' in data:
                    pulses = data['pulses']
                else:
                    pulses = data
            else:
                pulses = data
                
            if not isinstance(pulses, dict):
                QMessageBox.warning(self, _("pulse_dialogs.import_pulse.data_format_error"), _("pulse_dialogs.import_pulse.data_must_dict"))
                return
                
            valid_count = 0
            error_count = 0
            warnings: List[str] = []
            
            for name, pulse_data in pulses.items():
                # 验证波形数据格式
                is_valid, errors = self.validate_pulse_operation(pulse_data)
                
                if is_valid:
                    # 检查数据完整性
                    integrity = self.check_pulse_data_integrity(pulse_data)
                    
                    self.imported_pulses.append({
                        'name': name,
                        'data': pulse_data,
                        'integrity': integrity
                    })
                    
                    item = QListWidgetItem(name)
                    item.setData(Qt.ItemDataRole.UserRole, len(self.imported_pulses) - 1)
                    
                    # 根据完整性检查设置图标或提示
                    integrity_warnings = integrity.get('warnings', [])
                    if integrity_warnings and isinstance(integrity_warnings, list):
                        item.setToolTip(f"{_('pulse_dialogs.import_pulse.preview.warnings')}: {'; '.join(integrity_warnings)}")
                        warnings.extend(integrity_warnings)
                    
                    self.pulse_list.addItem(item)
                    valid_count += 1
                else:
                    error_count += 1
                    logger.warning(f"跳过无效波形 '{name}': {'; '.join(errors)}")
                
            # 显示导入结果
            if valid_count > 0:
                message = _("pulse_dialogs.import_pulse.import_success_msg").format(valid_count)
                if error_count > 0:
                    message += _("pulse_dialogs.import_pulse.skipped_invalid").format(error_count)
                if warnings:
                    message += f"\n\n{_('pulse_dialogs.import_pulse.preview.warnings')}:\n" + '\n'.join(set(warnings))
                    QMessageBox.warning(self, _("pulse_dialogs.import_pulse.import_complete"), message)
                else:
                    QMessageBox.information(self, _("pulse_dialogs.import_pulse.import_success"), message)
            else:
                if error_count > 0:
                    QMessageBox.critical(self, _("pulse_dialogs.import_pulse.import_failed"), _("pulse_dialogs.import_pulse.all_invalid"))
                else:
                    QMessageBox.warning(self, _("pulse_dialogs.import_pulse.import_failed"), _("pulse_dialogs.import_pulse.no_valid_data"))
                    
        except KeyError as e:
            QMessageBox.critical(self, _("pulse_dialogs.import_pulse.data_error"), _("pulse_dialogs.import_pulse.missing_field").format(str(e)))
        except Exception as e:
            QMessageBox.critical(self, _("pulse_dialogs.import_pulse.process_error"), _("pulse_dialogs.import_pulse.process_failed").format(str(e)))
            
    def update_preview(self) -> None:
        """更新预览"""
        selected_items = self.pulse_list.selectedItems()
        if selected_items:
            item = selected_items[0]
            index = item.data(Qt.ItemDataRole.UserRole)
            pulse = self.imported_pulses[index]
            
            preview_text = f"{_('pulse_dialogs.import_pulse.preview.name')}: {pulse['name']}\n"
            preview_text += f"{_('pulse_dialogs.import_pulse.preview.steps')}: {len(pulse['data'])}\n"
            
            # 显示统计信息
            if 'integrity' in pulse:
                stats = pulse['integrity']['stats']
                preview_text += f"{_('pulse_dialogs.import_pulse.preview.duration')}: {stats['duration_ms']}ms\n"
                preview_text += f"{_('pulse_dialogs.import_pulse.preview.max_frequency')}: {stats['max_frequency']}\n"
                preview_text += f"{_('pulse_dialogs.import_pulse.preview.max_intensity')}: {stats['max_intensity']}\n"
                
                # 显示警告
                if pulse['integrity']['warnings']:
                    preview_text += f"\n{_('pulse_dialogs.import_pulse.preview.warnings')}:\n"
                    for warning in pulse['integrity']['warnings']:
                        preview_text += f"• {warning}\n"
            
            preview_text += f"\n{_('pulse_dialogs.import_pulse.preview.first_3_steps')}:\n{str(pulse['data'][:3])}"
            
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
        selected_pulses = []
        for item in self.pulse_list.selectedItems():
            index = item.data(Qt.ItemDataRole.UserRole)
            selected_pulses.append(self.imported_pulses[index])
        return selected_pulses


class ExportPulseDialog(QDialog):
    """导出波形对话框"""
    
    def __init__(self, pulses: List[Pulse], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pulses = pulses
        
        self.setWindowTitle(_("pulse_dialogs.export_pulse.title"))
        self.setModal(True)
        self.resize(450, 350)
        self.setup_ui()
        self.apply_style()
        
    def setup_ui(self) -> None:
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel(_("pulse_dialogs.export_pulse.export_file"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        
        # 波形选择
        list_label = QLabel(_("pulse_dialogs.export_pulse.select_pulses"))
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
        self.file_path_edit.setPlaceholderText(_("pulse_dialogs.export_pulse.save_path"))
        file_layout.addWidget(self.file_path_edit)
        
        browse_btn = QPushButton(_("pulse_dialogs.import_pulse.browse"))
        browse_btn.clicked.connect(self.browse_save_path)
        file_layout.addWidget(browse_btn)
        
        layout.addLayout(file_layout)
        
        # 格式选项
        format_label = QLabel(_("pulse_dialogs.export_pulse.export_format"))
        layout.addWidget(format_label)
        
        self.format_combo = QComboBox()
        self.format_combo.addItem(_("pulse_dialogs.export_pulse.standard_format"), "standard")
        self.format_combo.addItem(_("pulse_dialogs.export_pulse.compatible_format"), "compatible")
        layout.addWidget(self.format_combo)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)
        
        clear_btn = QPushButton(_("pulse_dialogs.import_pulse.clear_selection"))
        clear_btn.clicked.connect(self.clear_selection)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.export_pulses)
        button_box.rejected.connect(self.reject)
        button_layout.addWidget(button_box)
        
        layout.addLayout(button_layout)
        
    def apply_style(self) -> None:
        """应用样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: white;
            }
            QLabel {
                color: white;
            }
            QLineEdit, QListWidget, QComboBox {
                background-color: #333;
                color: white;
                border: 1px solid #d4af37;
                padding: 5px;
                border-radius: 3px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #555;
            }
            QListWidget::item:selected {
                background-color: #d4af37;
                color: black;
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
        """)
        
    def get_default_filename(self) -> str:
        """生成默认文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"dg_lab_pulses_{timestamp}.json"
    
    def browse_save_path(self) -> None:
        """浏览保存路径"""
        default_filename = self.get_default_filename()
        file_path, _ = QFileDialog.getSaveFileName(
            self, _("pulse_dialogs.export_pulse.save_path"), default_filename, "JSON文件 (*.json);;所有文件 (*)"
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
        
    def export_pulses(self) -> None:
        """导出波形"""
        file_path = self.file_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(self, _("pulse_dialogs.export_pulse.path_error"), _("pulse_dialogs.export_pulse.select_save_path"))
            return
            
        selected_items = self.pulse_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, _("pulse_dialogs.export_pulse.selection_error"), _("pulse_dialogs.export_pulse.select_at_least_one"))
            return
            
        try:
            # 收集选中的波形并验证数据
            export_data = {}
            total_steps = 0
            
            for item in selected_items:
                pulse = item.data(Qt.ItemDataRole.UserRole)
                
                # 确保数据格式正确
                pulse_data = list(pulse.data)
                export_data[pulse.name] = pulse_data
                total_steps += len(pulse_data)
                
            # 根据格式选择创建最终数据
            format_type = self.format_combo.currentData()
            if format_type == "standard":
                final_data = {
                    "version": "1.0",
                    "type": "dg-lab-pulses",
                    "created_at": datetime.now().isoformat(),
                    "pulse_count": len(selected_items),
                    "total_steps": total_steps,
                    "compatible_with": "PyDGLab-WS v1.0+",
                    "pulses": export_data
                }
            else:
                final_data = {
                    "pulses": export_data
                }
                
            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, ensure_ascii=False, indent=2)
                
            # 显示详细的导出信息
            duration_ms = total_steps * 100
            format_name = _("pulse_dialogs.export_pulse.standard_format_name") if format_type == 'standard' else _("pulse_dialogs.export_pulse.compatible_format_name")
            
            message = _("pulse_dialogs.export_pulse.export_success_msg").format(
                os.path.basename(file_path),
                len(selected_items),
                total_steps,
                duration_ms,
                duration_ms/1000,
                format_name
            )
            
            QMessageBox.information(self, _("pulse_dialogs.export_pulse.export_success"), message)
            self.accept()
            
        except PermissionError:
            QMessageBox.critical(self, _("pulse_dialogs.export_pulse.permission_error"), _("pulse_dialogs.export_pulse.no_write_permission"))
        except OSError as e:
            QMessageBox.critical(self, _("pulse_dialogs.export_pulse.file_error"), _("pulse_dialogs.export_pulse.cannot_create").format(str(e)))
        except Exception as e:
            QMessageBox.critical(self, _("pulse_dialogs.export_pulse.export_error"), _("pulse_dialogs.export_pulse.save_failed").format(str(e)))


class PulseInfoDialog(QDialog):
    """波形信息对话框"""
    
    def __init__(self, pulse: Pulse, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pulse = pulse
        
        self.setWindowTitle(f"{_('pulse_dialogs.pulse_info.title')} - {pulse.name}")
        self.setModal(True)
        self.resize(400, 300)
        self.setup_ui()
        self.apply_style()
        
    def setup_ui(self) -> None:
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel(f"{_('pulse_dialogs.pulse_info.pulse_name')}: {self.pulse.name}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        
        # 信息表单
        form_layout = QFormLayout()
        
        # 基本信息
        form_layout.addRow(_("pulse_dialogs.pulse_info.index_label"), QLabel(str(self.pulse.index)))
        form_layout.addRow(_("pulse_dialogs.pulse_info.steps_label"), QLabel(str(len(self.pulse.data))))
        
        # 强度统计
        intensities = [step[1][0] for step in self.pulse.data]  # 使用第一个强度值
        if intensities:
            form_layout.addRow(_("pulse_dialogs.pulse_info.min_intensity_label"), QLabel(f"{min(intensities)}%"))
            form_layout.addRow(_("pulse_dialogs.pulse_info.max_intensity_label"), QLabel(f"{max(intensities)}%"))
            form_layout.addRow(_("pulse_dialogs.pulse_info.avg_intensity_label"), QLabel(f"{sum(intensities)/len(intensities):.1f}%"))
            
        layout.addLayout(form_layout)
        
        # 详细数据
        data_label = QLabel(_("pulse_dialogs.pulse_info.detailed_data_label"))
        layout.addWidget(data_label)
        
        self.data_text = QTextEdit()
        self.data_text.setReadOnly(True)
        
        # 格式化显示数据
        data_str = _("pulse_dialogs.pulse_info.step_header") + "\n"
        data_str += "-" * 40 + "\n"
        
        for i, (duration, intensity) in enumerate(self.pulse.data):
            data_str += f"{i+1}\t{duration[0]}ms\t{intensity[0]}%\n"
            
        self.data_text.setText(data_str)
        layout.addWidget(self.data_text)
        
        # 关闭按钮
        close_btn = QPushButton(_("pulse_dialogs.pulse_info.close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
    def apply_style(self) -> None:
        """应用样式"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: white;
            }
            QLabel {
                color: white;
            }
            QTextEdit {
                background-color: #333;
                color: white;
                border: 1px solid #d4af37;
                padding: 5px;
                border-radius: 3px;
                font-family: monospace;
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
        """)
