"""
波形编辑器主标签页

基于DG-LAB官方APP界面设计的波形编辑器
"""

import asyncio
import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QMessageBox, QInputDialog,
    QSplitter, QGroupBox, QButtonGroup, QFrame, QDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCloseEvent

from models import PulseOperation, Channel
from core.dglab_pulse import Pulse
from i18n import translate, language_signals
from .ui_interface import UIInterface
from .pulse_widgets import PulsePreviewWidget, PulseStepEditor, ParameterControlPanel
from .pulse_dialogs import NewPulseDialog, ImportPulseDialog, ExportPulseDialog, PulseInfoDialog
from .pulse_detailed_editor import DetailedPulseStepDialog

logger = logging.getLogger(__name__)


class PulseEditorTab(QWidget):
    """波形编辑器主标签页"""
    
    pulse_saved = Signal(str)  # 波形保存信号
    pulse_deleted = Signal(str)  # 波形删除信号
    
    def __init__(self, ui_interface: UIInterface):
        super().__init__()
        self.ui_interface = ui_interface
        self.current_channel = Channel.A
        self.current_pulse: Optional[Pulse] = None
        self.is_modified = False
        self.is_playing = False
        self.test_channel = Channel.A  # 记录测试播放时使用的通道
        
        # UI组件
        self.pulse_list: QListWidget
        self.preview_widget: PulsePreviewWidget
        self.pulse_editor: PulseStepEditor
        self.param_panel: ParameterControlPanel
        self.channel_a_btn: QPushButton
        self.channel_b_btn: QPushButton
        self.save_btn: QPushButton
        
        # 预声明在setup_ui中初始化的组件
        self.pulse_list_title: QLabel
        self.operations_group: QGroupBox
        self.new_btn: QPushButton
        self.copy_btn: QPushButton
        self.delete_btn: QPushButton
        self.import_btn: QPushButton
        self.export_btn: QPushButton
        self.info_btn: QPushButton
        self.preview_group: QGroupBox
        self.channel_button_group: QButtonGroup
        self.editor_group: QGroupBox
        self.add_step_btn: QPushButton
        self.clear_btn: QPushButton
        self.test_btn: QPushButton
        
        self.setup_ui()
        self.connect_signals()
        self.apply_theme()
        self.load_pulses()
        
        # 连接语言切换信号
        language_signals.language_changed.connect(self.update_ui_texts)
        
    def setup_ui(self) -> None:
        """设置UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧面板
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # 右侧面板
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # 设置分割比例
        splitter.setSizes([250, 600])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
        
    def create_left_panel(self) -> QWidget:
        """创建左侧波形列表面板"""
        panel = QWidget()
        panel.setMaximumWidth(300)
        layout = QVBoxLayout(panel)
        
        # 标题
        self.pulse_list_title = QLabel(translate("pulse_editor.pulse_list"))
        self.pulse_list_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.pulse_list_title.setFont(font)
        layout.addWidget(self.pulse_list_title)
        
        # 波形列表
        self.pulse_list = QListWidget()
        self.pulse_list.setAlternatingRowColors(True)
        layout.addWidget(self.pulse_list)
        
        # 操作按钮组
        self.operations_group = QGroupBox(translate("pulse_editor.operations"))
        btn_group = self.operations_group
        btn_layout = QVBoxLayout(btn_group)
        
        # 新建按钮
        self.new_btn = QPushButton(translate("pulse_editor.new_pulse"))
        self.new_btn.clicked.connect(self.new_pulse)
        btn_layout.addWidget(self.new_btn)
        
        # 复制按钮
        self.copy_btn = QPushButton(translate("pulse_editor.copy_pulse"))
        self.copy_btn.clicked.connect(self.copy_pulse)
        self.copy_btn.setEnabled(False)
        btn_layout.addWidget(self.copy_btn)
        
        # 删除按钮
        self.delete_btn = QPushButton(translate("pulse_editor.delete_pulse"))
        self.delete_btn.clicked.connect(self.delete_pulse)
        self.delete_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_btn)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        btn_layout.addWidget(line)
        
        # 导入按钮
        self.import_btn = QPushButton(translate("pulse_editor.import_pulse"))
        self.import_btn.clicked.connect(self.import_pulses)
        btn_layout.addWidget(self.import_btn)
        
        # 导出按钮
        self.export_btn = QPushButton(translate("pulse_editor.export_pulse"))
        self.export_btn.clicked.connect(self.export_pulses)
        btn_layout.addWidget(self.export_btn)
        
        # 信息按钮
        self.info_btn = QPushButton(translate("pulse_editor.pulse_info"))
        self.info_btn.clicked.connect(self.show_pulse_info)
        self.info_btn.setEnabled(False)
        btn_layout.addWidget(self.info_btn)
        
        layout.addWidget(btn_group)
        
        return panel
        
    def create_right_panel(self) -> QWidget:
        """创建右侧编辑面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 波形预览区域
        self.preview_group = QGroupBox(translate("pulse_editor.pulse_preview"))
        preview_group = self.preview_group
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_widget = PulsePreviewWidget()
        preview_layout.addWidget(self.preview_widget)
        
        layout.addWidget(preview_group)
        
        # 通道选择和控制按钮
        control_layout = QHBoxLayout()
        
        # 通道选择组
        channel_group = QWidget()
        channel_layout = QHBoxLayout(channel_group)
        channel_layout.setContentsMargins(0, 0, 0, 0)
        
        self.channel_a_btn = QPushButton(translate("pulse_editor.channel_a"))
        self.channel_b_btn = QPushButton(translate("pulse_editor.channel_b"))
        
        # 设置按钮组
        self.channel_button_group = QButtonGroup()
        self.channel_button_group.addButton(self.channel_a_btn, 0)
        self.channel_button_group.addButton(self.channel_b_btn, 1)
        self.channel_button_group.setExclusive(True)
        
        for btn in [self.channel_a_btn, self.channel_b_btn]:
            btn.setCheckable(True)
            channel_layout.addWidget(btn)
        
        self.channel_a_btn.setChecked(True)  # 默认选中A通道
        control_layout.addWidget(channel_group)
        
        control_layout.addStretch()
        
        # 控制按钮
        self.test_btn = QPushButton(translate("pulse_editor.test_play"))
        self.test_btn.clicked.connect(self.toggle_test_play)
        control_layout.addWidget(self.test_btn)
        
        self.save_btn = QPushButton(translate("pulse_editor.save_pulse"))
        self.save_btn.clicked.connect(self.save_current_pulse)
        self.save_btn.setEnabled(False)
        control_layout.addWidget(self.save_btn)
        
        layout.addLayout(control_layout)
        
        # 脉冲编辑器
        self.editor_group = QGroupBox(translate("pulse_editor.pulse_editor"))
        editor_group = self.editor_group
        editor_layout = QVBoxLayout(editor_group)
        
        self.pulse_editor = PulseStepEditor()
        editor_layout.addWidget(self.pulse_editor)
        
        # 编辑器控制按钮
        editor_control_layout = QHBoxLayout()
        
        self.add_step_btn = QPushButton(translate("pulse_editor.add_step"))
        self.add_step_btn.clicked.connect(self.add_pulse_step)
        editor_control_layout.addWidget(self.add_step_btn)
        
        self.clear_btn = QPushButton(translate("pulse_editor.clear_all"))
        self.clear_btn.clicked.connect(self.clear_all_steps)
        editor_control_layout.addWidget(self.clear_btn)
        
        editor_control_layout.addStretch()
        
        editor_layout.addLayout(editor_control_layout)
        layout.addWidget(editor_group)
        
        # 参数控制面板
        self.param_panel = ParameterControlPanel()
        layout.addWidget(self.param_panel)
        
        return panel
        
    def connect_signals(self) -> None:
        """连接信号"""
        # 波形列表选择
        self.pulse_list.itemSelectionChanged.connect(self.on_pulse_selection_changed)
        self.pulse_list.itemDoubleClicked.connect(self.on_pulse_double_clicked)
        
        # 通道选择
        self.channel_button_group.buttonClicked.connect(self.on_channel_changed)
        
        # 脉冲编辑器
        self.pulse_editor.step_changed.connect(self.on_pulse_step_changed)
        self.pulse_editor.frequency_changed.connect(self.on_pulse_step_frequency_changed)
        self.pulse_editor.step_added.connect(self.on_pulse_step_added)
        self.pulse_editor.step_removed.connect(self.on_pulse_step_removed)
        self.pulse_editor.detailed_edit_requested.connect(self.on_detailed_edit_requested)
        
        # 参数面板
        self.param_panel.frequency_changed.connect(self.on_frequency_changed)
        self.param_panel.frequency_mode_changed.connect(self.on_frequency_mode_changed)
        
    def apply_theme(self) -> None:
        """应用深色主题"""
        self.setStyleSheet("""
            QWidget {
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
            QListWidget {
                background-color: #2b2b2b;
                border: 1px solid #d4af37;
                border-radius: 5px;
                color: white;
                alternate-background-color: #333;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #444;
            }
            QListWidget::item:selected {
                background-color: #d4af37;
                color: black;
            }
            QListWidget::item:hover {
                background-color: #555;
            }
            QPushButton {
                background-color: #d4af37;
                color: black;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #f0c040;
            }
            QPushButton:pressed {
                background-color: #b8860b;
            }
            QPushButton:disabled {
                background-color: #666;
                color: #999;
            }
            QPushButton:checked {
                background-color: #d4af37;
                color: black;
            }
            QPushButton[objectName="channel_button"] {
                background-color: #333;
                color: white;
                border: 1px solid #d4af37;
            }
            QPushButton[objectName="channel_button"]:checked {
                background-color: #d4af37;
                color: black;
            }
            QLabel {
                color: white;
            }
            QSplitter::handle {
                background-color: #d4af37;
                width: 2px;
            }
            QFrame[frameShape="4"] {
                color: #d4af37;
            }
        """)
        
        # 为通道按钮设置特殊样式
        self.channel_a_btn.setObjectName("channel_button")
        self.channel_b_btn.setObjectName("channel_button")
        
    def load_pulses(self) -> None:
        """加载波形列表"""
        self.pulse_list.clear()
        
        if self.ui_interface.registries.pulse_registry:
            for pulse in self.ui_interface.registries.pulse_registry.pulses:
                item = QListWidgetItem(pulse.name)
                item.setData(Qt.ItemDataRole.UserRole, pulse)
                
                # 设置统一的工具提示
                item.setToolTip(f"{pulse.name} ({len(pulse.data)} {translate('pulse_editor.steps_count')})")
                
                self.pulse_list.addItem(item)
            
            # 自动选择第一个波形进行编辑
            if self.pulse_list.count() > 0:
                first_item = self.pulse_list.item(0)
                self.pulse_list.setCurrentItem(first_item)
                # 手动触发选择事件
                pulse = first_item.data(Qt.ItemDataRole.UserRole)
                self.load_pulse_for_editing(pulse)
                
    def on_pulse_selection_changed(self) -> None:
        """波形选择改变处理"""
        selected_items = self.pulse_list.selectedItems()
        has_selection = len(selected_items) > 0
        
        # 更新按钮状态
        self.copy_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection and selected_items[0].data(Qt.ItemDataRole.UserRole).index >= 15)  # 只能删除自定义波形
        self.info_btn.setEnabled(has_selection)
        
        if has_selection:
            pulse = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.load_pulse_for_editing(pulse)
        else:
            self.clear_editor()
            
    def on_pulse_double_clicked(self, item: QListWidgetItem) -> None:
        """波形双击处理 - 加载到编辑器"""
        pulse = item.data(Qt.ItemDataRole.UserRole)
        self.load_pulse_for_editing(pulse)
        
    def load_pulse_for_editing(self, pulse: Pulse) -> None:
        """加载波形到编辑器"""
        if self.is_modified:
            reply = QMessageBox.question(self, translate("pulse_editor.unsaved_changes"), 
                                       translate("pulse_editor.unsaved_changes_msg"),
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
                
        self.current_pulse = pulse
        self.is_modified = False
        
        # 更新脉冲编辑器（保留原始频率信息）
        logger.debug(f"PulseEditorTab: 加载波形 '{pulse.name}'，数据长度: {len(pulse.data)}")
        logger.debug(f"PulseEditorTab: 波形数据前3个: {pulse.data[:3]}")
        self.pulse_editor.set_pulse_data(pulse.data)
        
        # 分析波形的频率模式
        frequencies = [step[0][0] for step in pulse.data] if pulse.data else [10]
        is_uniform_frequency = len(set(frequencies)) <= 1
        
        if is_uniform_frequency and frequencies:
            # 如果是统一频率，设置为固定模式并更新面板显示
            self.param_panel.set_frequency_mode("fixed")
            self.param_panel.freq_slider.setValue(frequencies[0])
            self.pulse_editor.set_frequency(frequencies[0])
            logger.debug(f"PulseEditorTab: 检测到统一频率: {frequencies[0]}ms，设置为固定模式")
        else:
            # 如果是混合频率，设置为独立模式
            self.param_panel.set_frequency_mode("individual")
            # 使用第一个步骤的频率作为面板显示值
            if frequencies:
                self.param_panel.freq_slider.setValue(frequencies[0])
            self.pulse_editor.set_frequency(self.param_panel.get_frequency())
            logger.debug(f"PulseEditorTab: 检测到混合频率，设置为独立模式")
        
        # 更新预览（使用编辑器的实际数据确保一致性）
        current_data = self.pulse_editor.get_pulse_data()
        self.preview_widget.set_pulse_data(current_data)
        
        # 更新保存按钮状态
        self.save_btn.setEnabled(False)
        
        logger.info(f"Loaded pulse for editing: {pulse.name}")
        
    def clear_editor(self) -> None:
        """清空编辑器"""
        self.current_pulse = None
        self.is_modified = False
        self.preview_widget.set_pulse_data([])
        self.pulse_editor.clear_bars()
        self.save_btn.setEnabled(False)
        
    def on_channel_changed(self, button: QPushButton) -> None:
        """通道选择改变"""
        if button == self.channel_a_btn:
            self.current_channel = Channel.A
        else:
            self.current_channel = Channel.B
            
        logger.info(f"Channel changed to: {self.current_channel}")
        
    def on_pulse_step_changed(self, position: int, value: int) -> None:
        """脉冲步骤改变"""
        if not self.current_pulse:
            return
            
        logger.debug(f"Step {position} intensity changed to {value}%")
        self.is_modified = True
        self.save_btn.setEnabled(True)
        
        # 更新预览
        current_data = self.pulse_editor.get_pulse_data()
        self.preview_widget.set_pulse_data(current_data)
        
    def on_pulse_step_added(self) -> None:
        """脉冲步骤添加"""
        self.is_modified = True
        self.save_btn.setEnabled(True)
        
        # 更新预览
        current_data = self.pulse_editor.get_pulse_data()
        self.preview_widget.set_pulse_data(current_data)
        
    def on_pulse_step_removed(self, position: int) -> None:
        """脉冲步骤移除"""
        self.is_modified = True
        self.save_btn.setEnabled(True)
        
        # 更新预览
        current_data = self.pulse_editor.get_pulse_data()
        self.preview_widget.set_pulse_data(current_data)
        
    def on_frequency_changed(self, frequency: int) -> None:
        """频率参数改变"""
        # 更新脉冲编辑器的频率设置
        self.pulse_editor.set_frequency(frequency)
        
        # 在固定频率模式下，更新所有现有条形的频率
        if self.param_panel.get_frequency_mode() == "fixed":
            self.pulse_editor.update_all_frequencies(frequency)
        
        self.is_modified = True
        self.save_btn.setEnabled(True)
        
        # 更新预览（使用编辑器的实际数据）
        current_data = self.pulse_editor.get_pulse_data()
        self.preview_widget.set_pulse_data(current_data)
        
    def on_frequency_mode_changed(self, mode: str) -> None:
        """频率模式改变"""
        logger.info(f"Frequency mode changed to: {mode}")
        
        if mode == "fixed":
            # 切换到固定模式时，将所有条形的频率统一为当前滑块值
            current_frequency = self.param_panel.get_frequency()
            self.pulse_editor.update_all_frequencies(current_frequency)
            
            self.is_modified = True
            self.save_btn.setEnabled(True)
            
            # 更新预览
            current_data = self.pulse_editor.get_pulse_data()
            self.preview_widget.set_pulse_data(current_data)
            
    def on_pulse_step_frequency_changed(self, position: int, frequency: int) -> None:
        """单个步骤频率改变"""
        logger.debug(f"Step {position} frequency changed to {frequency}")
        
        self.is_modified = True
        self.save_btn.setEnabled(True)
        
        # 更新预览
        current_data = self.pulse_editor.get_pulse_data()
        self.preview_widget.set_pulse_data(current_data)
        
    def on_detailed_edit_requested(self, position: int, pulse_operation: PulseOperation) -> None:
        """处理精细编辑请求"""
        dialog = DetailedPulseStepDialog(pulse_operation, position, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 获取编辑后的数据
            updated_pulse_operation = dialog.get_pulse_operation()
            
            # 更新编辑器中的数据
            self.pulse_editor.update_step_data(position, updated_pulse_operation)
            
            # 标记为已修改
            self.is_modified = True
            self.save_btn.setEnabled(True)
            
            # 更新预览
            current_data = self.pulse_editor.get_pulse_data()
            self.preview_widget.set_pulse_data(current_data)
            
            logger.info(f"Updated step {position + 1} with detailed editing")
        
    def new_pulse(self) -> None:
        """新建波形"""
        dialog = NewPulseDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.validate_input():
                name, template_data, _ = dialog.get_pulse_data()
                
                # 检查名称是否已存在
                if self.ui_interface.registries.pulse_registry:
                    if self.ui_interface.registries.pulse_registry.has_pulse_name(name):
                        QMessageBox.warning(self, translate("pulse_editor.name_conflict"), translate("pulse_editor.name_exists").format(name))
                        return
                        
                # 创建新波形
                try:
                    pulse = self.ui_interface.registries.pulse_registry.register_pulse(name, template_data)
                    self.load_pulses()
                    
                    # 选中新创建的波形
                    for i in range(self.pulse_list.count()):
                        item = self.pulse_list.item(i)
                        if item.data(Qt.ItemDataRole.UserRole) == pulse:
                            self.pulse_list.setCurrentItem(item)
                            break
                            
                    logger.info(f"Created new pulse: {name}")
                    QMessageBox.information(self, translate("pulse_editor.create_success"), translate("pulse_editor.create_success_msg").format(name))
                    
                except Exception as e:
                    QMessageBox.critical(self, translate("pulse_editor.create_failed"), translate("pulse_editor.create_failed_msg").format(str(e)))
                    
    def copy_pulse(self) -> None:
        """复制波形"""
        selected_items = self.pulse_list.selectedItems()
        if not selected_items:
            return
            
        source_pulse = selected_items[0].data(Qt.ItemDataRole.UserRole)
        
        # 获取新名称
        new_name, ok = QInputDialog.getText(self, translate("pulse_editor.copy_pulse_title"), 
                                          translate("pulse_editor.copy_name_prompt"), 
                                          text=translate("pulse_editor.copy_default_name").format(source_pulse.name))
        
        if ok and new_name.strip():
            new_name = new_name.strip()
            
            # 检查名称是否已存在
            if self.ui_interface.registries.pulse_registry:
                if self.ui_interface.registries.pulse_registry.has_pulse_name(new_name):
                    QMessageBox.warning(self, translate("pulse_editor.name_conflict"), translate("pulse_editor.name_exists").format(new_name))
                    return
                    
            try:
                # 复制数据
                copied_data = [step for step in source_pulse.data]
                pulse = self.ui_interface.registries.pulse_registry.register_pulse(new_name, copied_data)
                
                self.load_pulses()
                
                # 选中新复制的波形
                for i in range(self.pulse_list.count()):
                    item = self.pulse_list.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == pulse:
                        self.pulse_list.setCurrentItem(item)
                        break
                        
                logger.info(f"Copied pulse: {source_pulse.name} -> {new_name}")
                QMessageBox.information(self, translate("pulse_editor.copy_success"), translate("pulse_editor.copy_success_msg").format(new_name))
                
            except Exception as e:
                QMessageBox.critical(self, translate("pulse_editor.copy_failed"), translate("pulse_editor.copy_failed_msg").format(str(e)))
                
    def delete_pulse(self) -> None:
        """删除波形"""
        selected_items = self.pulse_list.selectedItems()
        if not selected_items:
            return
            
        pulse = selected_items[0].data(Qt.ItemDataRole.UserRole)
        
        # 只能删除自定义波形
        if pulse.index < 15:
            QMessageBox.warning(self, translate("pulse_editor.delete_failed"), translate("pulse_editor.cannot_delete_preset"))
            return
            
        reply = QMessageBox.question(self, translate("pulse_editor.confirm_delete"), 
                                   translate("pulse_editor.confirm_delete_msg").format(pulse.name),
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 如果正在编辑这个波形，清空编辑器
                if self.current_pulse == pulse:
                    self.clear_editor()
                    
                # 从注册表中移除
                if self.ui_interface.registries.pulse_registry:
                    self.ui_interface.registries.pulse_registry.unregister_pulse(pulse)
                        
                self.load_pulses()
                self.pulse_deleted.emit(pulse.name)
                
                logger.info(f"Deleted pulse: {pulse.name}")
                QMessageBox.information(self, translate("pulse_editor.delete_success"), translate("pulse_editor.delete_success_msg").format(pulse.name))
                
            except Exception as e:
                QMessageBox.critical(self, translate("pulse_editor.delete_failed"), translate("pulse_editor.delete_failed_msg").format(str(e)))
                
    def save_current_pulse(self) -> None:
        """保存当前波形"""
        if not self.current_pulse or not self.is_modified:
            return
            
        try:
            # 获取当前编辑的数据
            current_data = self.pulse_editor.get_pulse_data()
            
            # 更新波形数据
            self.current_pulse.data = current_data
            
            # 保存到配置
            self.save_pulses_to_config()
            
            self.is_modified = False
            self.save_btn.setEnabled(False)
            self.pulse_saved.emit(self.current_pulse.name)
            
            logger.info(f"Saved pulse: {self.current_pulse.name}")
            QMessageBox.information(self, translate("pulse_editor.save_success"), translate("pulse_editor.save_success_msg").format(self.current_pulse.name))
            
        except Exception as e:
            QMessageBox.critical(self, translate("pulse_editor.save_failed"), translate("pulse_editor.save_failed_msg").format(str(e)))
            
    def save_pulses_to_config(self) -> None:
        """保存波形到配置文件"""
        if self.ui_interface.registries.pulse_registry and self.ui_interface.settings:
            try:
                # 导出所有波形
                all_pulses = self.ui_interface.registries.pulse_registry.export_to_config()
                
                # 更新settings
                self.ui_interface.settings['pulses'] = all_pulses
                
                # 保存到文件
                self.ui_interface.save_settings()
                logger.info(f"Saved {len(all_pulses)} pulses to config")
                
            except Exception as e:
                logger.error(f"Failed to save pulses to config: {e}")
                raise
                
    def add_pulse_step(self) -> None:
        """添加脉冲步骤"""
        self.pulse_editor.add_step(50.0)  # 默认50%强度
        
    def clear_all_steps(self) -> None:
        """清空所有步骤"""
        if not self.current_pulse:
            return
            
        reply = QMessageBox.question(self, translate("pulse_editor.confirm_clear"), 
                                   translate("pulse_editor.confirm_clear_msg"),
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.pulse_editor.clear_bars()
            self.preview_widget.set_pulse_data([])
            self.is_modified = True
            self.save_btn.setEnabled(True)
            
    def toggle_test_play(self) -> None:
        """切换测试播放"""
        if not self.current_pulse:
            QMessageBox.warning(self, translate("pulse_editor.cannot_test"), translate("pulse_editor.select_pulse_first"))
            return
            
        if not self.is_playing:
            # 开始播放
            current_data = self.pulse_editor.get_pulse_data()
            if not current_data:
                QMessageBox.warning(self, translate("pulse_editor.cannot_test"), translate("pulse_editor.empty_waveform"))
                return
                
            self.preview_widget.set_pulse_data(current_data)
            self.preview_widget.start_animation()
            self.test_btn.setText(translate("pulse_editor.stop_play"))
            self.is_playing = True
            self.test_channel = self.current_channel  # 记录测试时的通道
            
            # 如果有控制器，在设备上播放
            if self.ui_interface.controller:
                try:
                    # 创建临时脉冲对象
                    temp_pulse = Pulse(-1, translate("pulse_editor.test_waveform"), current_data)
                    
                    # 在当前通道播放
                    asyncio.create_task(self.ui_interface.controller.dglab_service.set_test_pulse(self.current_channel, temp_pulse))
                        
                    logger.info(f"Playing test pulse on channel {self.current_channel}")
                    
                except Exception as e:
                    logger.error(f"Failed to play test pulse: {e}")
                    # 如果设备播放失败，至少保证UI动画正常
                    logger.warning("Device playback failed, continuing with UI preview only")
        else:
            # 停止播放
            self.preview_widget.stop_animation()
            self.test_btn.setText(translate("pulse_editor.test_play"))
            self.is_playing = False
            
            # 恢复设备上的原始波形
            if self.ui_interface.controller:
                try:
                    # 恢复当前通道的正常波形
                    asyncio.create_task(self.ui_interface.controller.dglab_service.update_pulse_data())
                    logger.info(f"Restored normal pulse on channel {self.current_channel}")
                except Exception as e:
                    logger.error(f"Failed to restore normal pulse: {e}")
            
    def import_pulses(self) -> None:
        """导入波形"""
        dialog = ImportPulseDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_pulses = dialog.get_selected_pulses()
            
            if not selected_pulses:
                return
                
            imported_count = 0
            skipped_count = 0
            
            for pulse_data in selected_pulses:
                name = pulse_data['name']
                data = pulse_data['data']
                
                # 检查名称是否已存在
                if self.ui_interface.registries.pulse_registry:
                    if self.ui_interface.registries.pulse_registry.has_pulse_name(name):
                        skipped_count += 1
                        continue
                        
                try:
                    self.ui_interface.registries.pulse_registry.register_pulse(name, data)
                    imported_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to import pulse {name}: {e}")
                    skipped_count += 1
                    
            # 刷新列表
            self.load_pulses()
            
            # 保存到配置
            if imported_count > 0:
                try:
                    self.save_pulses_to_config()
                except Exception as e:
                    logger.error(f"Failed to save imported pulses: {e}")
                    
            # 显示结果
            message = translate("pulse_editor.import_complete").format(imported_count, skipped_count)
            QMessageBox.information(self, translate("pulse_editor.import_result"), message)
            
    def export_pulses(self) -> None:
        """导出波形"""
        if not self.ui_interface.registries.pulse_registry:
            QMessageBox.warning(self, translate("pulse_editor.export_failed"), translate("pulse_editor.registry_unavailable"))
            return
            
        # 获取自定义波形（索引>=15的波形）
        custom_pulses = [pulse for pulse in self.ui_interface.registries.pulse_registry.pulses if pulse.index >= 15]
        
        if not custom_pulses:
            QMessageBox.information(self, translate("pulse_editor.no_custom_pulses"), translate("pulse_editor.no_custom_pulses_msg"))
            return
            
        dialog = ExportPulseDialog(custom_pulses, self)
        dialog.exec()
        
    def show_pulse_info(self) -> None:
        """显示波形信息"""
        selected_items = self.pulse_list.selectedItems()
        if not selected_items:
            return
            
        pulse = selected_items[0].data(Qt.ItemDataRole.UserRole)
        dialog = PulseInfoDialog(pulse, self)
        dialog.exec()
        
    def update_ui_texts(self) -> None:
        """更新UI文本"""
        # 更新脉冲列表标题
        self.pulse_list_title.setText(translate("pulse_editor.pulse_list"))
        
        # 更新组框标题
        self.operations_group.setTitle(translate("pulse_editor.operations"))
        self.preview_group.setTitle(translate("pulse_editor.pulse_preview"))
        self.editor_group.setTitle(translate("pulse_editor.pulse_editor"))
        
        # 更新左侧面板按钮
        self.new_btn.setText(translate("pulse_editor.new_pulse"))
        self.copy_btn.setText(translate("pulse_editor.copy_pulse"))
        self.delete_btn.setText(translate("pulse_editor.delete_pulse"))
        self.import_btn.setText(translate("pulse_editor.import_pulse"))
        self.export_btn.setText(translate("pulse_editor.export_pulse"))
        self.info_btn.setText(translate("pulse_editor.pulse_info"))
        
        # 更新右侧面板按钮
        self.channel_a_btn.setText(translate("pulse_editor.channel_a"))
        self.channel_b_btn.setText(translate("pulse_editor.channel_b"))
        self.test_btn.setText(translate("pulse_editor.test_play") if not self.is_playing else translate("pulse_editor.stop_play"))
        self.save_btn.setText(translate("pulse_editor.save_pulse"))
        self.add_step_btn.setText(translate("pulse_editor.add_step"))
        self.clear_btn.setText(translate("pulse_editor.clear_all"))
        
        # 更新参数控制面板
        self.param_panel.update_ui_texts()
        
        # 更新脉冲列表的工具提示
        self._update_pulse_list_tooltips()
        
    def _update_pulse_list_tooltips(self) -> None:
        """更新脉冲列表的工具提示文本"""
        for i in range(self.pulse_list.count()):
            item = self.pulse_list.item(i)
            if item:
                pulse = item.data(Qt.ItemDataRole.UserRole)
                if pulse:
                    # 设置统一的工具提示
                    item.setToolTip(f"{pulse.name} ({len(pulse.data)} {translate('pulse_editor.steps_count')})")
        
    def closeEvent(self, event: QCloseEvent) -> None:
        """关闭事件"""
        if self.is_modified:
            reply = QMessageBox.question(self, translate("pulse_editor.unsaved_changes"), 
                                       translate("pulse_editor.unsaved_changes_save"),
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Yes:
                self.save_current_pulse()
                event.accept()
            elif reply == QMessageBox.StandardButton.No:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
