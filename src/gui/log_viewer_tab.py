import logging
from typing import Optional

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QTextEdit, QLabel)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor
from models import Channel

from core.dglab_controller import DGLabController
from .ui_interface import UIInterface
from models import SettingsDict
from i18n import translate, language_signals

logger = logging.getLogger(__name__)


class QTextEditHandler(logging.Handler):
    """Custom log handler to output log messages to QTextEdit."""
    
    def __init__(self, log_text_edit: QTextEdit) -> None:
        super().__init__()
        self.log_text_edit: QTextEdit = log_text_edit
        self.max_lines: int = 1000  # 限制最大行数

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        
        # 根据日志级别为消息添加颜色
        if record.levelno >= logging.ERROR:
            msg = f"<b style='color:red;'>{msg}</b>"
        elif record.levelno >= logging.WARNING:
            msg = f"<b style='color:orange;'>{msg}</b>"
        else:
            msg = f"<span>{msg}</span>"
        
        # 在UI线程中插入日志消息
        self.log_text_edit.append(msg)
        
        # 限制日志行数
        self.limit_log_lines()

    def limit_log_lines(self) -> None:
        """限制 QTextEdit 中的最大行数，保留颜色和格式，并保持显示最新日志"""
        document = self.log_text_edit.document()
        
        # 检查是否超过最大行数
        if document.blockCount() > self.max_lines:
            # 计算需要删除的行数
            lines_to_remove = document.blockCount() - self.max_lines
            
            # 移动到文档开头
            cursor = QTextCursor(document)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            
            # 选择并删除多余的行
            for _ in range(lines_to_remove):
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()  # 删除换行符
            
            # 保持滚动条在底部显示最新日志
            scrollbar = self.log_text_edit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())


class LogViewerTab(QWidget):
    def __init__(self, ui_interface: UIInterface, settings: SettingsDict) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.settings: SettingsDict = settings
        
        # 调试信息定时更新
        self.debug_timer: QTimer = QTimer()
        self.debug_timer.timeout.connect(self.update_debug_info)
        self.debug_timer.start(1000)  # 每秒更新一次调试信息
        
        # UI组件类型注解
        self.log_groupbox: QGroupBox
        self.log_text_edit: QTextEdit
        self.debug_group: QGroupBox
        self.param_label: QLabel
        self.controller_params_label: QLabel  # 保存控制器参数标签引用
        
        self.init_ui()
        self.setup_logging()
        
        # 连接语言变更信号
        language_signals.language_changed.connect(self.update_ui_texts)

    @property
    def controller(self) -> Optional[DGLabController]:
        """通过UIInterface获取当前控制器"""
        return self.ui_interface.controller

    def init_ui(self) -> None:
        """初始化调试选项卡UI"""
        layout = QVBoxLayout()
        
        # 日志显示组
        self.log_groupbox = QGroupBox(translate("debug_tab.simple_log"))
        self.log_groupbox.setCheckable(True)
        self.log_groupbox.setChecked(True)
        self.log_groupbox.toggled.connect(self.toggle_log_display)
        
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        
        log_layout = QVBoxLayout()
        log_layout.addWidget(self.log_text_edit)
        self.log_groupbox.setLayout(log_layout)
        
        layout.addWidget(self.log_groupbox)
        
        # 调试信息组
        debug_info_group = QGroupBox(translate("debug_tab.debug_info"))
        debug_info_group.setCheckable(True)
        debug_info_group.setChecked(False)
        debug_info_group.toggled.connect(self.toggle_debug_info)
        self.debug_group = debug_info_group  # 保持引用
        
        debug_info_layout = QVBoxLayout()
        self.controller_params_label = QLabel(translate("debug_tab.controller_params_label"))
        debug_info_layout.addWidget(self.controller_params_label)
        
        self.param_label = QLabel(translate("debug_tab.loading_params"))
        self.param_label.setWordWrap(True)
        debug_info_layout.addWidget(self.param_label)
        
        debug_info_group.setLayout(debug_info_layout)
        layout.addWidget(debug_info_group)
        
        self.setLayout(layout)

    def setup_logging(self) -> None:
        """设置日志系统输出到 QTextEdit 和控制台"""
        # 创建自定义处理器
        text_handler = QTextEditHandler(self.log_text_edit)
        text_handler.setLevel(logging.INFO)
        
        # 设置日志格式
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        text_handler.setFormatter(formatter)
        
        # 将处理器添加到根日志记录器
        root_logger = logging.getLogger()
        root_logger.addHandler(text_handler)

    def toggle_log_display(self, checked: bool) -> None:
        """折叠或展开日志显示框"""
        if checked:
            self.log_text_edit.show()
        else:
            self.log_text_edit.hide()

    def toggle_debug_info(self, checked: bool) -> None:
        """当调试组被启用/禁用时折叠或展开内容"""
        if checked:
            self.debug_timer.start(1000)
        else:
            self.debug_timer.stop()

    def update_debug_info(self) -> None:
        """更新调试信息"""
        if self.controller:
            debug_text = (
                f"Device online: app_status_online= {self.controller.app_status_online}\n "
                f"Enable Panel Control: {self.controller.dglab_service.enable_panel_control}\n"
                f"Fire Mode Disabled: {self.controller.dglab_service.fire_mode_disabled}\n"
                f"Dynamic Bone Mode A: {self.controller.dglab_service.is_dynamic_bone_enabled(Channel.A)}\n"
                f"Dynamic Bone Mode B: {self.controller.dglab_service.is_dynamic_bone_enabled(Channel.B)}\n"
                f"Pulse Mode A: {self.controller.dglab_service.get_pulse_mode(Channel.A)}\n"
                f"Pulse Mode B: {self.controller.dglab_service.get_pulse_mode(Channel.B)}\n"
                f"Fire Mode Strength Step: {self.controller.dglab_service.fire_mode_strength_step}\n"
                f"Enable ChatBox Status: {self.controller.chatbox_service.is_enabled}\n"
                f"GUI Parameters:\n"
                f"A  strength allow update:{getattr(self, 'allow_a_channel_update', 'N/A')}\n"
                f"B  strength allow update:{getattr(self, 'allow_b_channel_update', 'N/A')}\n"
            )
            self.param_label.setText(debug_text)
        else:
            self.param_label.setText(translate("debug_tab.controller_not_initialized"))

    def update_ui_texts(self) -> None:
        """更新UI文本为当前语言"""
        self.log_groupbox.setTitle(translate("debug_tab.simple_log"))
        self.debug_group.setTitle(translate("debug_tab.debug_info"))
        
        # 更新调试信息组内的标签 - 使用直接引用
        self.controller_params_label.setText(translate("debug_tab.controller_params_label"))