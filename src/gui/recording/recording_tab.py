"""
录制功能Tab组件 - 全新UI设计

基于设计文档重新实现的现代化录制回放界面
采用左右分栏布局和DG-LAB金黄色主题
"""

import asyncio
import logging
import os
from typing import Optional
from datetime import datetime

from PySide6.QtCore import QTimer, Signal, Qt, QPoint
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QLabel, QPushButton, QProgressBar,
                               QMessageBox, QSplitter, QListWidget,
                               QListWidgetItem, QSlider,
                               QMenu, QInputDialog, QFileDialog, QDialog)

from core.service_controller import ServiceController
from core.recording.recording_models import RecordingState, RecordingSession
from core.recording.playback_handler import PlaybackState
from core.recording.recording_models import PlaybackState as RecordingPlaybackState
from core.recording.dgr_file_manager import DGRFileManager
from gui.ui_interface import UIInterface
from i18n import language_signals, translate
from models import Channel, PlaybackMode

logger = logging.getLogger(__name__)

# DG-LAB主题色彩常量
class DGLabColors:
    # 背景色系 - 深色主题
    BACKGROUND_PRIMARY = "#1A1A1A"        # 主背景
    BACKGROUND_SECONDARY = "#2D2D2D"      # 次背景
    BACKGROUND_CARD = "#333333"           # 卡片背景
    BACKGROUND_INPUT = "#404040"          # 输入框背景
    
    # 金黄色系 (官方主色调)
    ACCENT_GOLD = "#D4AF37"               # 主要金黄色
    ACCENT_GOLD_LIGHT = "#E6C547"         # 浅金黄色
    ACCENT_GOLD_DARK = "#B8941F"          # 深金黄色
    
    # 文字色系
    TEXT_PRIMARY = "#FFFFFF"              # 主要文字
    TEXT_SECONDARY = "#CCCCCC"            # 次要文字
    TEXT_ACCENT = "#D4AF37"               # 强调文字
    TEXT_DISABLED = "#666666"             # 禁用文字
    
    # 状态色系
    STATUS_RECORDING = "#FF4444"          # 录制中
    STATUS_READY = "#4CAF50"              # 就绪
    STATUS_PAUSED = "#FF9800"             # 暂停
    STATUS_WARNING = "#FFC107"            # 警告
    
    # 边框和分割线
    BORDER_PRIMARY = "#D4AF37"            # 主要边框
    BORDER_SECONDARY = "#555555"          # 次要边框
    SEPARATOR = "#444444"                 # 分割线



class RecordingTab(QWidget):
    """录制功能Tab - 全新设计"""
    
    # 信号定义
    recording_started = Signal()
    recording_stopped = Signal(RecordingSession)
    playback_started = Signal()
    playback_stopped = Signal()
    
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.service_controller: Optional[ServiceController] = None
        
        # 会话管理
        self.sessions: list[RecordingSession] = []
        self.current_session: Optional[RecordingSession] = None
        
        # 进度条拖拽状态
        self._slider_being_dragged = False
        
        # 循环播放状态
        self._loop_enabled = False
        
        # 动画效果
        self._recording_animation: Optional[QTimer] = None
        self._recording_blink_state = False
        
        # 警告状态标记
        self._connection_warning_shown = False
        self._playback_warning_shown = False
        
        # 移除按钮状态跟踪变量，使用按钮显示/隐藏来管理状态
        
        # UI组件声明
        self.main_splitter: QSplitter
        
        # 左侧录制控制区组件
        self.start_record_btn: QPushButton
        self.stop_record_btn: QPushButton
        self.pause_record_btn: QPushButton
        self.resume_record_btn: QPushButton
        self.recording_status_icon: QLabel
        self.recording_time_label: QLabel
        self.channel_a_progress: QProgressBar
        self.channel_b_progress: QProgressBar
        self.channel_a_value: QLabel
        self.channel_b_value: QLabel
        
        # 右侧文件管理区组件
        self.file_list: QListWidget
        self.import_btn: QPushButton
        self.play_btn: QPushButton
        self.pause_playback_btn: QPushButton
        self.resume_playback_btn: QPushButton
        self.stop_playback_btn: QPushButton
        self.loop_btn: QPushButton
        self.progress_slider: QSlider
        self.current_time_label: QLabel
        self.total_time_label: QLabel
        
        # 顶部状态栏组件
        self.connection_text: QLabel
        self.recording_status_text: QLabel
        self.selected_file_text: QLabel
        
        # 定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(200)  # 200ms更新频率，平衡性能和响应性
        
        self.setup_ui()
        
        # 连接语言更新信号
        language_signals.language_changed.connect(self.update_ui_texts)
        
    def setup_ui(self) -> None:
        """设置主UI布局 - 精简版"""
        # 设置整体背景
        self.setStyleSheet(f"""
            RecordingTab {{
                background: {DGLabColors.BACKGROUND_PRIMARY};
                color: {DGLabColors.TEXT_PRIMARY};
            }}
        """)
        
        # 主布局 - 垂直布局简化
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        # 顶部状态栏 - 简化
        status_bar = self.create_simple_status_bar()
        main_layout.addWidget(status_bar)
        
        # 主要内容区域 - 水平分割器
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(3)
        self.main_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {DGLabColors.SEPARATOR};
            }}
        """)
        
        # 左侧录制控制面板 (固定宽度300px)
        recording_panel = self.create_simple_recording_panel()
        self.main_splitter.addWidget(recording_panel)
        
        # 右侧文件管理面板 (自适应宽度)
        file_management_panel = self.create_simple_file_panel()
        self.main_splitter.addWidget(file_management_panel)
        
        # 设置分割比例 (30:70)
        self.main_splitter.setSizes([300, 700])
        self.main_splitter.setStretchFactor(0, 0)  # 左侧固定
        self.main_splitter.setStretchFactor(1, 1)  # 右侧可伸缩
        
        main_layout.addWidget(self.main_splitter)
        
        self.setLayout(main_layout)
        
    def create_simple_status_bar(self) -> QGroupBox:
        """创建简化的状态栏"""
        bar = QGroupBox()
        bar.setFixedHeight(30)
        bar.setStyleSheet(f"""
            QGroupBox {{
                background: {DGLabColors.BACKGROUND_SECONDARY};
                border-radius: 4px;
                border: none;
            }}
        """)
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        
        # 连接状态
        self.connection_text = QLabel(translate("recording.device_disconnected"))
        self.connection_text.setStyleSheet(f"color: {DGLabColors.STATUS_WARNING}; font-weight: bold;")
        
        # 录制状态
        self.recording_status_text = QLabel(translate("recording.ready"))
        self.recording_status_text.setStyleSheet(f"color: {DGLabColors.TEXT_SECONDARY};")
        
        # 选中文件
        self.selected_file_text = QLabel("")
        self.selected_file_text.setStyleSheet(f"color: {DGLabColors.TEXT_SECONDARY};")
        
        layout.addWidget(self.connection_text)
        layout.addWidget(QLabel(" | "))
        layout.addWidget(self.recording_status_text)
        layout.addWidget(QLabel(" | "))
        layout.addWidget(self.selected_file_text)
        layout.addStretch()
        
        return bar
        
    def create_simple_recording_panel(self) -> QGroupBox:
        """创建简化的录制控制面板"""
        panel = QGroupBox()
        panel.setFixedWidth(300)
        panel.setStyleSheet(f"""
            QGroupBox {{
                background: {DGLabColors.BACKGROUND_SECONDARY};
                border-radius: 6px;
                border: none;
            }}
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # 录制按钮组
        self.start_record_btn = QPushButton(translate("recording.start_recording"))
        self.start_record_btn.setMinimumHeight(50)
        self.start_record_btn.clicked.connect(self._start_record_btn_clicked)
        self.start_record_btn.setStyleSheet(f"""
            QPushButton {{
                background: {DGLabColors.ACCENT_GOLD};
                color: {DGLabColors.BACKGROUND_PRIMARY};
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background: {DGLabColors.ACCENT_GOLD_LIGHT};
            }}
            QPushButton:disabled {{
                background: {DGLabColors.TEXT_DISABLED};
                color: {DGLabColors.TEXT_SECONDARY};
            }}
        """)
        
        self.stop_record_btn = QPushButton(translate("recording.stop_recording"))
        self.stop_record_btn.setMinimumHeight(50)
        self.stop_record_btn.clicked.connect(self._stop_record_btn_clicked)
        self.stop_record_btn.setStyleSheet(f"""
            QPushButton {{
                background: {DGLabColors.STATUS_RECORDING};
                color: {DGLabColors.TEXT_PRIMARY};
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background: #FF6666;
            }}
        """)
        self.stop_record_btn.setVisible(False)
        
        layout.addWidget(self.start_record_btn)
        layout.addWidget(self.stop_record_btn)
        
        # 暂停/继续按钮
        control_layout = QHBoxLayout()
        control_layout.setSpacing(8)
        self.pause_record_btn = QPushButton(translate("recording.pause"))
        self.resume_record_btn = QPushButton(translate("recording.resume"))
        
        for btn in [self.pause_record_btn, self.resume_record_btn]:
            btn.setEnabled(False)
            btn.clicked.connect(self._pause_resume_record_clicked)
            btn.setMinimumHeight(35)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {DGLabColors.TEXT_SECONDARY};
                    border: 1px solid {DGLabColors.BORDER_SECONDARY};
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    border-color: {DGLabColors.ACCENT_GOLD};
                    color: {DGLabColors.ACCENT_GOLD};
                }}
                QPushButton:disabled {{
                    color: {DGLabColors.TEXT_DISABLED};
                    border-color: {DGLabColors.TEXT_DISABLED};
                }}
            """)
        
        control_layout.addWidget(self.pause_record_btn)
        control_layout.addWidget(self.resume_record_btn)
        layout.addLayout(control_layout)
        
        # 添加分隔线
        separator = QLabel()
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background: {DGLabColors.SEPARATOR};")
        layout.addWidget(separator)
        
        # 简化的状态显示
        self.create_compact_status_display(layout)
        
        # 添加弹性空间
        layout.addStretch()
        
        return panel
        
    def create_compact_status_display(self, parent_layout: QVBoxLayout) -> None:
        """创建紧凑的状态显示"""
        # 状态信息区域
        status_group = QGroupBox()
        status_group.setStyleSheet(f"""
            QGroupBox {{
                background: {DGLabColors.BACKGROUND_CARD};
                border-radius: 6px;
                border: 1px solid {DGLabColors.BORDER_SECONDARY};
            }}
        """)
        
        status_layout = QVBoxLayout(status_group)
        status_layout.setContentsMargins(8, 8, 8, 8)
        status_layout.setSpacing(8)
        
        # 录制状态和时长
        status_info_layout = QHBoxLayout()
        self.recording_status_icon = QLabel("●")
        self.recording_status_icon.setFixedSize(12, 12)
        self.recording_status_icon.setStyleSheet(f"color: {DGLabColors.STATUS_READY};")
        
        self.recording_time_label = QLabel(translate("recording.duration").format("00:00"))
        self.recording_time_label.setStyleSheet(f"color: {DGLabColors.TEXT_SECONDARY}; font-size: 13px; font-weight: bold;")
        
        status_info_layout.addWidget(self.recording_status_icon)
        status_info_layout.addWidget(self.recording_time_label)
        status_info_layout.addStretch()
        
        status_layout.addLayout(status_info_layout)
        
        # 通道强度显示 - 紧凑版
        channels_layout = QVBoxLayout()
        channels_layout.setSpacing(6)
        
        # 通道标题
        channels_title = QLabel(translate("recording.channel_strength"))
        channels_title.setStyleSheet(f"color: {DGLabColors.TEXT_SECONDARY}; font-size: 11px; font-weight: bold;")
        channels_layout.addWidget(channels_title)
        
        # A通道
        a_layout = QHBoxLayout()
        a_layout.setSpacing(6)
        
        a_label = QLabel("A")
        a_label.setFixedWidth(18)
        a_label.setFixedHeight(18)
        a_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        a_label.setStyleSheet(f"""
            QLabel {{
                color: {DGLabColors.BACKGROUND_PRIMARY};
                background: {DGLabColors.ACCENT_GOLD};
                font-weight: bold;
                font-size: 10px;
                border-radius: 9px;
            }}
        """)
        
        self.channel_a_progress = QProgressBar()
        self.channel_a_progress.setRange(0, 100)
        self.channel_a_progress.setValue(0)
        self.channel_a_progress.setFixedHeight(16)
        self.channel_a_progress.setTextVisible(False)
        self.channel_a_progress.setStyleSheet(f"""
            QProgressBar {{
                background: {DGLabColors.BACKGROUND_PRIMARY};
                border: none;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {DGLabColors.ACCENT_GOLD}, 
                    stop:1 {DGLabColors.ACCENT_GOLD_LIGHT});
                border: none;
            }}
        """)
        
        self.channel_a_value = QLabel("000")
        self.channel_a_value.setFixedWidth(32)
        self.channel_a_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.channel_a_value.setStyleSheet(f"""
            QLabel {{
                color: {DGLabColors.ACCENT_GOLD};
                font-size: 11px;
                font-weight: bold;
                background: {DGLabColors.BACKGROUND_INPUT};
                border-radius: 4px;
                padding: 2px;
            }}
        """)
        
        a_layout.addWidget(a_label)
        a_layout.addWidget(self.channel_a_progress)
        a_layout.addWidget(self.channel_a_value)
        
        # B通道
        b_layout = QHBoxLayout()
        b_layout.setSpacing(6)
        
        b_label = QLabel("B")
        b_label.setFixedWidth(18)
        b_label.setFixedHeight(18)
        b_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b_label.setStyleSheet(f"""
            QLabel {{
                color: {DGLabColors.BACKGROUND_PRIMARY};
                background: {DGLabColors.ACCENT_GOLD_LIGHT};
                font-weight: bold;
                font-size: 10px;
                border-radius: 9px;
            }}
        """)
        
        self.channel_b_progress = QProgressBar()
        self.channel_b_progress.setRange(0, 100)
        self.channel_b_progress.setValue(0)
        self.channel_b_progress.setFixedHeight(16)
        self.channel_b_progress.setTextVisible(False)
        self.channel_b_progress.setStyleSheet(f"""
            QProgressBar {{
                background: {DGLabColors.BACKGROUND_PRIMARY};
                border: none;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {DGLabColors.ACCENT_GOLD_LIGHT}, 
                    stop:1 #FFE082);
                border: none;
            }}
        """)
        
        self.channel_b_value = QLabel("000")
        self.channel_b_value.setFixedWidth(32)
        self.channel_b_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.channel_b_value.setStyleSheet(f"""
            QLabel {{
                color: {DGLabColors.ACCENT_GOLD_LIGHT};
                font-size: 11px;
                font-weight: bold;
                background: {DGLabColors.BACKGROUND_INPUT};
                border-radius: 4px;
                padding: 2px;
            }}
        """)
        
        b_layout.addWidget(b_label)
        b_layout.addWidget(self.channel_b_progress)
        b_layout.addWidget(self.channel_b_value)
        
        channels_layout.addLayout(a_layout)
        channels_layout.addLayout(b_layout)
        status_layout.addLayout(channels_layout)
        
        parent_layout.addWidget(status_group)
        
        
    def create_simple_file_panel(self) -> QGroupBox:
        """创建简化的文件管理面板"""
        panel = QGroupBox()
        panel.setStyleSheet(f"""
            QGroupBox {{
                background: {DGLabColors.BACKGROUND_SECONDARY};
                border-radius: 6px;
                border: none;
            }}
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 文件工具栏
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)
        
        self.import_btn = QPushButton(translate("recording.import_file"))
        self.import_btn.setMinimumHeight(35)
        self.import_btn.clicked.connect(self._import_btn_clicked)
        self.import_btn.setStyleSheet(f"""
            QPushButton {{
                background: {DGLabColors.ACCENT_GOLD};
                color: {DGLabColors.BACKGROUND_PRIMARY};
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background: {DGLabColors.ACCENT_GOLD_LIGHT};
            }}
        """)
        
        toolbar_layout.addWidget(self.import_btn)
        toolbar_layout.addStretch()
        
        layout.addLayout(toolbar_layout)
        
        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(200)
        self.file_list.setStyleSheet(f"""
            QListWidget {{
                background: {DGLabColors.BACKGROUND_CARD};
                border: 1px solid {DGLabColors.BORDER_SECONDARY};
                border-radius: 4px;
                color: {DGLabColors.TEXT_PRIMARY};
            }}
            QListWidget::item {{
                background: transparent;
                padding: 6px;
                border-radius: 4px;
                margin: 1px;
            }}
            QListWidget::item:selected {{
                background: {DGLabColors.BACKGROUND_INPUT};
                border: 1px solid {DGLabColors.ACCENT_GOLD};
            }}
            QListWidget::item:hover {{
                background: {DGLabColors.BACKGROUND_INPUT};
            }}
        """)
        self.file_list.itemClicked.connect(self._file_item_clicked)
        self.file_list.itemDoubleClicked.connect(self._file_item_double_clicked)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.file_list)
        
        # 简化的播放控制
        self.create_simple_playback_controls(layout)
        
        return panel
        
    def create_simple_playback_controls(self, parent_layout: QVBoxLayout) -> None:
        """创建简化的播放控制"""
        # 播放按钮组
        btn_layout = QHBoxLayout()
        
        self.play_btn = QPushButton(translate("recording.play"))
        self.pause_playback_btn = QPushButton(translate("recording.pause"))
        self.resume_playback_btn = QPushButton(translate("recording.resume"))
        self.stop_playback_btn = QPushButton(translate("recording.stop"))
        self.loop_btn = QPushButton(translate("recording.loop"))
        self.loop_btn.setCheckable(True)
        
        # 初始状态：继续按钮隐藏
        self.resume_playback_btn.setVisible(False)
        
        for btn in [self.play_btn, self.pause_playback_btn, self.resume_playback_btn, self.stop_playback_btn]:
            btn.setEnabled(False)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {DGLabColors.TEXT_SECONDARY};
                    border: 1px solid {DGLabColors.BORDER_SECONDARY};
                    border-radius: 4px;
                    padding: 6px 12px;
                }}
                QPushButton:hover {{
                    border-color: {DGLabColors.ACCENT_GOLD};
                    color: {DGLabColors.ACCENT_GOLD};
                }}
                QPushButton:disabled {{
                    color: {DGLabColors.TEXT_DISABLED};
                    border-color: {DGLabColors.TEXT_DISABLED};
                }}
            """)
        
        self.loop_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {DGLabColors.TEXT_SECONDARY};
                border: 1px solid {DGLabColors.BORDER_SECONDARY};
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                border-color: {DGLabColors.ACCENT_GOLD};
                color: {DGLabColors.ACCENT_GOLD};
            }}
            QPushButton:checked {{
                background: {DGLabColors.ACCENT_GOLD};
                color: {DGLabColors.BACKGROUND_PRIMARY};
                border-color: {DGLabColors.ACCENT_GOLD};
            }}
        """)
        
        # 连接信号
        self.play_btn.clicked.connect(self._play_btn_clicked)
        self.pause_playback_btn.clicked.connect(self._pause_playback_clicked)
        self.resume_playback_btn.clicked.connect(self._resume_playback_clicked)
        self.stop_playback_btn.clicked.connect(self._stop_playback_clicked)
        self.loop_btn.clicked.connect(self._loop_btn_clicked)
        
        btn_layout.addWidget(self.play_btn)
        btn_layout.addWidget(self.pause_playback_btn)
        btn_layout.addWidget(self.resume_playback_btn)
        btn_layout.addWidget(self.stop_playback_btn)
        btn_layout.addWidget(self.loop_btn)
        btn_layout.addStretch()
        
        parent_layout.addLayout(btn_layout)
        
        # 进度条
        progress_layout = QHBoxLayout()
        
        self.current_time_label = QLabel("00:00")
        self.current_time_label.setFixedWidth(35)
        self.current_time_label.setStyleSheet(f"color: {DGLabColors.TEXT_SECONDARY}; font-size: 11px;")
        
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.setValue(0)
        self.progress_slider.setEnabled(False)
        self.progress_slider.sliderPressed.connect(self._progress_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._progress_slider_released)
        self.progress_slider.valueChanged.connect(self._progress_slider_changed)
        self.progress_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {DGLabColors.BORDER_SECONDARY};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {DGLabColors.ACCENT_GOLD};
                width: 12px;
                height: 12px;
                border-radius: 6px;
                margin-top: -4px;
                margin-bottom: -4px;
            }}
            QSlider::sub-page:horizontal {{
                background: {DGLabColors.ACCENT_GOLD};
                border-radius: 2px;
            }}
        """)
        
        self.total_time_label = QLabel("00:00")
        self.total_time_label.setFixedWidth(35)
        self.total_time_label.setStyleSheet(f"color: {DGLabColors.TEXT_SECONDARY}; font-size: 11px;")
        
        progress_layout.addWidget(self.current_time_label)
        progress_layout.addWidget(self.progress_slider)
        progress_layout.addWidget(self.total_time_label)
        
        parent_layout.addLayout(progress_layout)
        
        
        
        
        
    # ================== 事件处理方法 ==================
    
    def _start_record_btn_clicked(self) -> None:
        """开始录制按钮点击"""
        logger.info("用户点击开始录制")
        asyncio.create_task(self.start_recording())
        
    def _stop_record_btn_clicked(self) -> None:
        """停止录制按钮点击"""
        logger.info("用户点击停止录制")
        # 显示确认对话框
        QTimer.singleShot(0, lambda: self._confirm_stop_recording())
            
    def _confirm_stop_recording(self) -> None:
        """确认停止录制"""
        reply = QMessageBox.question(
            self,
            translate("recording.confirm_stop_recording"),
            translate("recording.confirm_stop_recording_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            logger.info("用户确认停止录制")
            asyncio.create_task(self.stop_recording())
        else:
            logger.info("用户取消停止录制")
            
    def _pause_resume_record_clicked(self) -> None:
        """暂停/继续录制按钮点击"""
        logger.info("用户点击暂停/继续录制")
        asyncio.create_task(self.pause_recording())
        
    def _file_item_clicked(self, item: QListWidgetItem) -> None:
        """文件项点击"""
        # 从item数据中获取会话
        session = item.data(256)
        if session:
            logger.info(f"用户选择文件: {session.metadata.session_id[:8]}...")
            self.current_session = session
            self.update_playback_ui_state()
            
    def _file_item_double_clicked(self, item: QListWidgetItem) -> None:
        """文件项双击 - 开始播放"""
        session = item.data(256)
        if session:
            logger.info(f"用户双击播放文件: {session.metadata.session_id[:8]}...")
            self.current_session = session
            self.update_playback_ui_state()
            asyncio.create_task(self.start_playback())
            
    def _import_btn_clicked(self) -> None:
        """导入文件按钮点击"""
        logger.info("用户点击导入文件按钮")
        # 先显示文件选择对话框，然后在回调中处理异步加载
        file_path = self._show_import_dialog()
        if file_path:
            # 使用QTimer.singleShot避免在事件循环中直接创建任务
            QTimer.singleShot(0, lambda: self._safe_load_recording_file(file_path))
            
    def _safe_load_recording_file(self, file_path: str) -> None:
        """安全地加载录制文件"""
        try:
            asyncio.create_task(self._load_recording_from_file(file_path))
        except Exception as e:
            logger.error(f"创建异步任务失败: {e}")
            
    def _show_context_menu(self, position: QPoint) -> None:
        """显示右键菜单"""
        item = self.file_list.itemAt(position)
        if not item:
            return
            
        session = item.data(256)
        if not session:
            return
            
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {DGLabColors.BACKGROUND_CARD};
                border: 1px solid {DGLabColors.BORDER_SECONDARY};
                border-radius: 6px;
                color: {DGLabColors.TEXT_PRIMARY};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background: {DGLabColors.BACKGROUND_INPUT};
                color: {DGLabColors.ACCENT_GOLD};
            }}
        """)
        
        # 播放菜单
        play_action = menu.addAction(translate("recording.context_menu_play"))
        play_action.triggered.connect(lambda: asyncio.create_task(self.start_playback()))
        
        menu.addSeparator()
        
        # 文件操作菜单
        rename_action = menu.addAction(translate("recording.context_menu_rename"))
        rename_action.triggered.connect(lambda: self._rename_file(item, session))
        
        export_action = menu.addAction(translate("recording.context_menu_export"))
        export_action.triggered.connect(lambda: self._export_file(session))
        
        details_action = menu.addAction(translate("recording.context_menu_details"))
        details_action.triggered.connect(lambda: self._show_file_details(session))
        
        menu.addSeparator()
        
        delete_action = menu.addAction(translate("recording.context_menu_delete"))
        delete_action.triggered.connect(lambda: self._delete_file(item, session))
        
        # 显示菜单
        menu.exec(self.file_list.mapToGlobal(position))
            
    def _play_btn_clicked(self) -> None:
        """播放按钮点击"""
        logger.info("用户点击播放按钮")
        asyncio.create_task(self.start_playback())
        
    def _pause_playback_clicked(self) -> None:
        """暂停回放按钮点击"""
        asyncio.create_task(self.pause_playback())
        
    def _resume_playback_clicked(self) -> None:
        """继续回放按钮点击"""
        logger.info("用户点击继续回放按钮")
        asyncio.create_task(self.resume_playback())
        
    def _stop_playback_clicked(self) -> None:
        """停止回放按钮点击"""
        asyncio.create_task(self.stop_playback())
        
    def _loop_btn_clicked(self) -> None:
        """循环播放按钮点击"""
        self._loop_enabled = self.loop_btn.isChecked()
        if self._loop_enabled:
            logger.info("循环播放已启用")
        else:
            logger.info("循环播放已禁用")
        
        # 实时同步播放模式到协议层
        playback_mode = PlaybackMode.LOOP if self._loop_enabled else PlaybackMode.ONCE
        asyncio.create_task(self._sync_playback_mode_to_protocol(playback_mode))
            
        
    def _progress_slider_pressed(self) -> None:
        """进度条开始拖拽"""
        self._slider_being_dragged = True
        
    def _progress_slider_released(self) -> None:
        """进度条拖拽释放"""
        self._slider_being_dragged = False
        # 执行跳转
        if self.service_controller:
            device_service = self.service_controller.dglab_device_service
            if device_service:
                playback_handler = device_service.get_playback_handler()
                if playback_handler and self.current_session:
                    total_snapshots = playback_handler.get_total_snapshots()
                    if total_snapshots > 0:
                        target_position = int((self.progress_slider.value() / 100) * total_snapshots)
                        asyncio.create_task(playback_handler.seek_to_position(target_position))
                        
    def _progress_slider_changed(self, value: int) -> None:
        """进度条值变化"""
        if self._slider_being_dragged and self.current_session:
            # 拖拽时更新时间显示预览
            if self.current_session.metadata:
                duration_ms = self.current_session.get_duration_ms()
                current_time_ms = int((value / 100) * duration_ms)
                current_minutes, current_seconds = divmod(current_time_ms // 1000, 60)
                self.current_time_label.setText(f"{current_minutes:02d}:{current_seconds:02d}")
        
    # ================== 业务逻辑方法 ==================
    
    def set_service_controller(self, service_controller: ServiceController) -> None:
        """设置服务控制器"""
        self.service_controller = service_controller
        
        # 设置回放回调函数
        playback_handler = service_controller.dglab_device_service.get_playback_handler()
        playback_handler.set_progress_changed_callback(self._on_playback_progress_changed)
        playback_handler.set_state_changed_callback(self._on_playback_state_changed)
        playback_handler.set_error_callback(self._on_playback_error)
        
        # 更新连接状态
        self.update_connection_status()
        
    def update_connection_status(self) -> None:
        """更新连接状态显示"""
        is_connected = False
        
        if self.service_controller:
            device_service = self.service_controller.dglab_device_service
            if device_service:
                # 检查设备服务是否真正运行中
                is_connected = device_service.is_service_running()
        
        if is_connected:
            self.connection_text.setText(translate("recording.device_connected"))
            self.connection_text.setStyleSheet(f"color: {DGLabColors.STATUS_READY}; font-weight: bold;")
            self.start_record_btn.setEnabled(True)
            self.stop_record_btn.setEnabled(True)
        else:
            self.connection_text.setText(translate("recording.device_disconnected"))
            self.connection_text.setStyleSheet(f"color: {DGLabColors.STATUS_WARNING}; font-weight: bold;")
            self.start_record_btn.setEnabled(False)
            self.stop_record_btn.setEnabled(False)
            
    def update_status(self) -> None:
        """更新状态显示（使用统一更新方法）"""
        self.update_all_ui_state()
            
    def update_recording_status(self) -> None:
        """更新录制状态"""
        if not self.service_controller:
            return
            
        device_service = self.service_controller.dglab_device_service
        if not device_service:
            return
            
        record_handler = device_service.get_record_handler()
            
        if not record_handler:
            return
            
        state = record_handler.get_recording_state()
        current_session = record_handler.get_current_session()
        
        # 更新状态显示
        if state == RecordingState.IDLE:
            self._stop_recording_animation()
            self.recording_status_icon.setText("●")
            # 显示开始录制按钮，隐藏停止录制按钮
            self.start_record_btn.setVisible(True)
            self.stop_record_btn.setVisible(False)
            self.pause_record_btn.setEnabled(False)
            self.resume_record_btn.setEnabled(False)
            
        elif state == RecordingState.RECORDING:
            self._start_recording_animation()
            # 隐藏开始录制按钮，显示停止录制按钮
            self.start_record_btn.setVisible(False)
            self.stop_record_btn.setVisible(True)
            self.pause_record_btn.setEnabled(True)
            self.resume_record_btn.setEnabled(False)
            
        elif state == RecordingState.PAUSED:
            self._stop_recording_animation()
            self.recording_status_icon.setText("●")
            # 保持停止录制按钮可见，暂停状态下也可以停止
            self.start_record_btn.setVisible(False)
            self.stop_record_btn.setVisible(True)
            self.pause_record_btn.setEnabled(False)
            self.resume_record_btn.setEnabled(True)
        
        # 使用统一方法更新状态文本
        self._update_recording_status_text(state)
            
        # 更新录制时间
        if current_session and current_session.metadata:
            if state == RecordingState.RECORDING:
                elapsed = datetime.now() - current_session.metadata.start_time
                minutes, seconds = divmod(int(elapsed.total_seconds()), 60)
                self.recording_time_label.setText(translate("recording.duration").format(f"{minutes:02d}:{seconds:02d}"))
            else:
                duration_ms = current_session.get_duration_ms()
                minutes, seconds = divmod(duration_ms // 1000, 60)
                self.recording_time_label.setText(translate("recording.duration").format(f"{minutes:02d}:{seconds:02d}"))
        else:
            self.recording_time_label.setText(translate("recording.duration").format("00:00"))
            
        # 更新通道强度显示
        pulse_data_a = device_service.get_current_pulse_data(Channel.A)
        pulse_data_b = device_service.get_current_pulse_data(Channel.B)

        # 计算强度平均值
        strength_a = sum(pulse_data_a[1]) / len(pulse_data_a[1]) if pulse_data_a else 0
        strength_b = sum(pulse_data_b[1]) / len(pulse_data_b[1]) if pulse_data_b else 0
        
        self.channel_a_progress.setValue(int(strength_a))
        self.channel_b_progress.setValue(int(strength_b))
        self.channel_a_value.setText(f"{int(strength_a):03d}")
        self.channel_b_value.setText(f"{int(strength_b):03d}")
        
    def update_playback_status(self) -> None:
        """更新回放状态"""
        if not self.service_controller:
            return
            
        device_service = self.service_controller.dglab_device_service
        if not device_service:
            return
            
        playback_handler = device_service.get_playback_handler()
        if not playback_handler:
            return
            
        state = playback_handler.get_playback_state()
        
        # 使用统一方法更新播放控件状态
        self._update_playback_ui_controls(state, bool(self.current_session))
        
        # 处理循环播放逻辑
        if state == PlaybackState.IDLE and self._loop_enabled and self.current_session:
            current_position = playback_handler.get_current_position()
            total_snapshots = playback_handler.get_total_snapshots()
            
            # 如果播放完毕且启用循环，重新开始播放
            if total_snapshots > 0 and current_position >= total_snapshots:
                logger.info("循环播放：重新开始播放")
                asyncio.create_task(self._restart_playback())
            
        # 更新进度条 - 只在不拖拽时更新
        if not self._slider_being_dragged:
            current_position = playback_handler.get_current_position()
            total_snapshots = playback_handler.get_total_snapshots()
            if total_snapshots > 0:
                progress_percent = int((current_position / total_snapshots) * 100)
                self.progress_slider.setValue(progress_percent)
                
                # 更新时间显示
                if self.current_session and self.current_session.metadata:
                    duration_ms = self.current_session.get_duration_ms()
                    current_time_ms = int((current_position / total_snapshots) * duration_ms)
                    current_minutes, current_seconds = divmod(current_time_ms // 1000, 60)
                    self.current_time_label.setText(f"{current_minutes:02d}:{current_seconds:02d}")
        
    def update_playback_ui_state(self) -> None:
        """更新回放UI状态（仅处理会话相关的UI元素）"""
        has_selected = self.current_session is not None
        
        # 更新进度条和时间显示
        self.progress_slider.setEnabled(has_selected)
        
        if has_selected and self.current_session and self.current_session.metadata:
            duration_ms = self.current_session.get_duration_ms()
            minutes, seconds = divmod(duration_ms // 1000, 60)
            self.total_time_label.setText(f"{minutes:02d}:{seconds:02d}")
        else:
            self.total_time_label.setText("00:00")
            self.current_time_label.setText("00:00")
            self.progress_slider.setValue(0)
            
        # 更新播放控件状态（根据当前播放状态）
        if self.service_controller:
            device_service = self.service_controller.dglab_device_service
            if device_service:
                playback_handler = device_service.get_playback_handler()
                if playback_handler:
                    state = playback_handler.get_playback_state()
                    self._update_playback_ui_controls(state, has_selected)
                    return
        
        # 如果没有服务控制器，默认设置为空闲状态
        self._update_playback_ui_controls(PlaybackState.IDLE, has_selected)
            
    def update_status_bar(self) -> None:
        """更新状态栏信息 - 简化版"""
        if not self.service_controller:
            self.recording_status_text.setText(translate("recording.device_disconnected"))
            self.selected_file_text.setText("")
            return
            
        # 获取录制状态
        device_service = self.service_controller.dglab_device_service
        if device_service:
            record_handler = device_service.get_record_handler()
            if record_handler:
                recording_state = record_handler.get_recording_state()
                
                # 获取播放状态（用于录制空闲时的状态显示）
                playback_state = None
                if recording_state == RecordingState.IDLE:
                    playback_handler = device_service.get_playback_handler()
                    if playback_handler:
                        playback_state = playback_handler.get_playback_state()
                
                # 使用统一方法更新状态文本
                self._update_recording_status_text(recording_state, playback_state)
                    
                # 检查系统健康状态
                self._check_system_health(recording_state)
                    
        # 更新选中文件信息
        if self.current_session and self.current_session.metadata:
            file_name = f"{translate('recording.recording_prefix')}{self.current_session.metadata.start_time.strftime('%Y%m%d_%H%M%S')}.dgr"
            self.selected_file_text.setText(translate("recording.selected_file").format(file_name))
        else:
            self.selected_file_text.setText("")
            
    def add_recording_session(self, session: RecordingSession):
        """添加录制会话到列表"""
        self.sessions.append(session)
        
        # 生成完整的文件名显示
        file_name = f"{translate('recording.recording_prefix')}{session.metadata.start_time.strftime('%Y%m%d_%H%M%S')}.dgr"
        duration = self.format_duration(session.get_duration_ms())
        time_str = session.metadata.start_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 创建简单的文本项
        display_text = f"{file_name} - {duration}\n{time_str}"
        item = QListWidgetItem(display_text)
        item.setData(256, session)  # 存储会话数据
        
        self.file_list.addItem(item)
        
        # 自动选中最新的项
        self.file_list.setCurrentItem(item)
        self.current_session = session
        self.update_playback_ui_state()
        
    def format_duration(self, duration_ms: int) -> str:
        """格式化时长显示"""
        total_seconds = duration_ms // 1000
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"
        
    # ================== 异步业务方法 ==================
    
    async def start_recording(self) -> None:
        """开始录制"""
        if not self.service_controller:
            self.show_error(translate("recording.device_service_not_connected"))
            return
            
        try:
            device_service = self.service_controller.dglab_device_service
            if not device_service:
                self.show_error(translate("recording.device_service_unavailable"))
                return
                
            record_handler = device_service.get_record_handler()
            if not record_handler:
                self.show_error(translate("recording.record_handler_unavailable"))
                return
                
            # 检查设备连接状态（只记录日志，不弹窗）
            if not device_service.is_service_running():
                logger.warning("设备连接不稳定，录制可能失败")
                
            success = await record_handler.start_recording()
            if success:
                self.recording_started.emit()
                logger.info("录制已开始")
            else:
                self.show_error(translate("recording.record_start_failed"))
                
        except asyncio.TimeoutError:
            logger.error("开始录制超时")
            self.show_error(translate("recording.record_timeout"))
        except ConnectionError as e:
            logger.error(f"设备连接错误: {e}")
            self.show_error(translate("recording.device_disconnected_during_record"))
        except Exception as e:
            logger.error(f"开始录制时出错: {e}")
            self.show_error(f"开始录制失败: {str(e)}")
            
    async def pause_recording(self) -> None:
        """暂停/继续录制"""
        if not self.service_controller:
            return
            
        try:
            device_service = self.service_controller.dglab_device_service
            if device_service:
                record_handler = device_service.get_record_handler()
                    
                if record_handler:
                    state = record_handler.get_recording_state()
                    if state == RecordingState.RECORDING:
                        await record_handler.pause_recording()
                    elif state == RecordingState.PAUSED:
                        await record_handler.resume_recording()
        except Exception as e:
            logger.error(f"暂停/继续录制时出错: {e}")
            
    async def stop_recording(self) -> None:
        """停止录制"""
        if not self.service_controller:
            return
            
        try:
            device_service = self.service_controller.dglab_device_service
            if device_service:
                record_handler = device_service.get_record_handler()
                    
                if record_handler:
                    session = await record_handler.stop_recording()
                    if session:
                        self.add_recording_session(session)
                        self.recording_stopped.emit(session)
                        logger.info(f"录制已停止，会话ID: {session.metadata.session_id}")
                    else:
                        self.show_error(translate("recording.record_stop_failed"))
        except Exception as e:
            logger.error(f"停止录制时出错: {e}")
            self.show_error(translate("recording.record_stop_failed"))
            
    async def start_playback(self) -> None:
        """开始回放"""
        if not self.service_controller:
            self.show_error(translate("recording.device_service_not_connected"))
            return
            
        if not self.current_session:
            self.show_error("请先选择要回放的录制文件")
            return
            
        try:
            osc_action_service = self.service_controller.osc_action_service
            if osc_action_service:
                osc_action_service.set_current_pulse(Channel.A, None)
                osc_action_service.set_current_pulse(Channel.B, None)

            device_service = self.service_controller.dglab_device_service
            if not device_service:
                self.show_error(translate("recording.device_service_unavailable"))
                return
                
            playback_handler = device_service.get_playback_handler()
            if not playback_handler:
                self.show_error("回放处理器不可用，请检查设备连接")
                return
                
            # 检查设备连接状态（只记录日志，不弹窗）
            if not device_service.is_service_running():
                logger.warning("设备连接不稳定，回放可能失败")
                
            # 验证录制文件完整性
            if not self.current_session.snapshots:
                self.show_error("录制文件为空，无法回放")
                return
                
            if not self.current_session.metadata:
                self.show_error("录制文件缺少元数据，无法回放")
                return
                
            loaded = await playback_handler.load_session(self.current_session)
            if not loaded:
                self.show_error("加载录制会话失败，文件可能已损坏")
                return
            
            # 同步播放模式到协议层
            playback_mode = PlaybackMode.LOOP if self._loop_enabled else PlaybackMode.ONCE
            await self._sync_playback_mode_to_protocol(playback_mode)
            
            success = await playback_handler.start_playback()
            if success:
                self.playback_started.emit()
                logger.info(f"开始回放会话: {self.current_session.metadata.session_id}")
            else:
                self.show_error("开始回放失败，请检查设备状态")
                
        except asyncio.TimeoutError:
            logger.error("回放操作超时")
            self.show_error("回放操作超时，请检查设备连接")
        except ConnectionError as e:
            logger.error(f"设备连接错误: {e}")
            self.show_error("设备连接中断，无法开始回放")
        except ValueError as e:
            logger.error(f"录制文件格式错误: {e}")
            self.show_error("录制文件格式不正确，无法回放")
        except Exception as e:
            logger.error(f"开始回放时出错: {e}")
            self.show_error(f"开始回放失败: {str(e)}")
            
    async def pause_playback(self) -> None:
        """暂停回放"""
        if not self.service_controller:
            return
            
        try:
            device_service = self.service_controller.dglab_device_service
            if device_service:
                playback_handler = device_service.get_playback_handler()
                    
                if playback_handler:
                    state = playback_handler.get_playback_state()
                    if state == PlaybackState.PLAYING:
                        await playback_handler.pause_playback()
                        logger.info("回放已暂停")
        except Exception as e:
            logger.error(f"暂停回放时出错: {e}")
            
    async def resume_playback(self) -> None:
        """继续回放"""
        if not self.service_controller:
            return
            
        try:
            device_service = self.service_controller.dglab_device_service
            if device_service:
                playback_handler = device_service.get_playback_handler()
                    
                if playback_handler:
                    state = playback_handler.get_playback_state()
                    if state == PlaybackState.PAUSED:
                        await playback_handler.resume_playback()
                        logger.info("回放已继续")
        except Exception as e:
            logger.error(f"继续回放时出错: {e}")
            
    async def stop_playback(self) -> None:
        """停止回放"""
        if not self.service_controller:
            return
            
        try:
            device_service = self.service_controller.dglab_device_service
            if device_service:
                playback_handler = device_service.get_playback_handler()
                    
                if playback_handler:
                    success = await playback_handler.stop_playback()
                    if success:
                        self.playback_stopped.emit()
                        logger.info("回放已停止")
                    else:
                        self.show_error("停止回放失败")
        except Exception as e:
            logger.error(f"停止回放时出错: {e}")
            self.show_error("停止回放失败")
            
    async def _restart_playback(self) -> None:
        """重新开始播放（用于循环播放）"""
        if not self.service_controller or not self.current_session:
            return
            
        try:
            device_service = self.service_controller.dglab_device_service
            if device_service:
                playback_handler = device_service.get_playback_handler()
                if playback_handler:
                    # 跳转到开始位置
                    await playback_handler.seek_to_position(0)
                    # 开始播放
                    success = await playback_handler.start_playback()
                    if success:
                        logger.info("循环播放：重新开始播放成功")
                    else:
                        logger.error("循环播放：重新开始播放失败")
        except Exception as e:
            logger.error(f"循环播放重启时出错: {e}")
            
    # ================== 动画效果方法 ==================
    
    def _start_recording_animation(self):
        """开始录制动画效果"""
        if self._recording_animation:
            self._recording_animation.stop()
            
        self._recording_animation = QTimer()
        self._recording_animation.timeout.connect(self._update_recording_animation)
        self._recording_animation.start(1000)  # 1秒间隔闪烁
        self._recording_blink_state = False
        
    def _stop_recording_animation(self):
        """停止录制动画效果"""
        if self._recording_animation:
            self._recording_animation.stop()
            self._recording_animation = None
            
    def _update_recording_animation(self):
        """更新录制动画 - 红色LED闪烁效果"""
        self._recording_blink_state = not self._recording_blink_state
        
        if self._recording_blink_state:
            # 亮红色
            self.recording_status_icon.setText("🔴")
            self.recording_status_icon.setStyleSheet(f"""
                color: {DGLabColors.STATUS_RECORDING}; 
                font-size: 18px;
                background: rgba(255, 68, 68, 0.2);
                border-radius: 12px;
                padding: 2px;
            """)
        else:
            # 暗红色
            self.recording_status_icon.setText("●")
            self.recording_status_icon.setStyleSheet(f"""
                color: #AA2222; 
                font-size: 16px;
                background: transparent;
                padding: 2px;
            """)
            
    # ================== 系统健康检查 ==================
    
    def _check_system_health(self, recording_state: Optional[RecordingState] = None):
        """检查系统健康状态，处理异常情况"""
        try:
            if not self.service_controller:
                return
                
            device_service = self.service_controller.dglab_device_service
            if not device_service:
                return
                
            # 检查设备连接状态
            is_connected = device_service.is_service_running()
            
            # 如果正在录制但设备断线，显示警告
            if recording_state == RecordingState.RECORDING and not is_connected:
                if not self._connection_warning_shown:
                    self._connection_warning_shown = True
                    self.show_warning(translate("recording.device_disconnected_recording_incomplete"))
                    logger.warning("录制期间设备连接中断")
                    
            # 重新连接后清除警告标记
            if is_connected and self._connection_warning_shown:
                self._connection_warning_shown = False
                
            # 检查回放状态
            playback_handler = device_service.get_playback_handler()
            if playback_handler:
                playback_state = playback_handler.get_playback_state()
                if playback_state == PlaybackState.PLAYING and not is_connected:
                    if not self._playback_warning_shown:
                        self._playback_warning_shown = True
                        self.show_warning(translate("recording.device_disconnected_playback_stopped"))
                        logger.warning("回放期间设备连接中断")
                        # 自动停止回放
                        asyncio.create_task(self.stop_playback())
                        
            # 重新连接后清除回放警告标记
            if is_connected and self._playback_warning_shown:
                self._playback_warning_shown = False
                
        except Exception as e:
            logger.error(f"系统健康检查出错: {e}")
    
    # ================== 辅助方法 ==================
    
    def show_error(self, message: str) -> None:
        """显示错误消息"""
        QTimer.singleShot(0, lambda: self._show_error_dialog(message))
        
    def show_warning(self, message: str) -> None:
        """显示警告消息"""
        QTimer.singleShot(0, lambda: self._show_warning_dialog(message))
        
    async def _save_recording_to_file(self, session: RecordingSession, file_path: str) -> bool:
        """保存录制会话到文件
        
        Args:
            session: 录制会话
            file_path: 保存路径
            
        Returns:
            bool: 是否保存成功
        """
        try:
            file_manager = DGRFileManager()
            await file_manager.save_recording(session, file_path)
            
            logger.info(f"录制会话已保存: {file_path}")
            return True
            
        except Exception as e:
            error_msg = f"保存录制失败: {e}"
            logger.error(error_msg)
            QTimer.singleShot(0, lambda: QMessageBox.critical(
                self, "保存失败", error_msg, QMessageBox.StandardButton.Ok
            ))
            return False


    def show_info(self, message: str) -> None:
        """显示信息消息"""
        QTimer.singleShot(0, lambda: self._show_info_dialog(message))
        
    def show_success(self, message: str) -> None:
        """显示成功消息"""
        QTimer.singleShot(0, lambda: self._show_success_dialog(message))
        
    def _show_error_dialog(self, message: str) -> None:
        """显示错误对话框"""
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle("错误")
        dialog.setText(message)
        dialog.setStyleSheet(f"""
            QMessageBox {{
                background: {DGLabColors.BACKGROUND_PRIMARY};
                color: {DGLabColors.TEXT_PRIMARY};
            }}
            QMessageBox QLabel {{
                color: {DGLabColors.TEXT_PRIMARY};
            }}
            QMessageBox QPushButton {{
                background: {DGLabColors.STATUS_RECORDING};
                color: {DGLabColors.TEXT_PRIMARY};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 60px;
            }}
            QMessageBox QPushButton:hover {{
                background: #FF6666;
            }}
        """)
        dialog.exec()
        
    def _show_warning_dialog(self, message: str) -> None:
        """显示警告对话框"""
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("警告")
        dialog.setText(message)
        dialog.setStyleSheet(f"""
            QMessageBox {{
                background: {DGLabColors.BACKGROUND_PRIMARY};
                color: {DGLabColors.TEXT_PRIMARY};
            }}
            QMessageBox QLabel {{
                color: {DGLabColors.TEXT_PRIMARY};
            }}
            QMessageBox QPushButton {{
                background: {DGLabColors.STATUS_WARNING};
                color: {DGLabColors.BACKGROUND_PRIMARY};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 60px;
            }}
            QMessageBox QPushButton:hover {{
                background: #FFD54F;
            }}
        """)
        dialog.exec()
        
    def _show_info_dialog(self, message: str) -> None:
        """显示信息对话框"""
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setWindowTitle("信息")
        dialog.setText(message)
        dialog.setStyleSheet(f"""
            QMessageBox {{
                background: {DGLabColors.BACKGROUND_PRIMARY};
                color: {DGLabColors.TEXT_PRIMARY};
            }}
            QMessageBox QLabel {{
                color: {DGLabColors.TEXT_PRIMARY};
            }}
            QMessageBox QPushButton {{
                background: {DGLabColors.ACCENT_GOLD};
                color: {DGLabColors.BACKGROUND_PRIMARY};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 60px;
            }}
            QMessageBox QPushButton:hover {{
                background: {DGLabColors.ACCENT_GOLD_LIGHT};
            }}
        """)
        dialog.exec()
        
    def _show_success_dialog(self, message: str) -> None:
        """显示成功对话框"""
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setWindowTitle("成功")
        dialog.setText(message)
        dialog.setStyleSheet(f"""
            QMessageBox {{
                background: {DGLabColors.BACKGROUND_PRIMARY};
                color: {DGLabColors.TEXT_PRIMARY};
            }}
            QMessageBox QLabel {{
                color: {DGLabColors.TEXT_PRIMARY};
            }}
            QMessageBox QPushButton {{
                background: {DGLabColors.STATUS_READY};
                color: {DGLabColors.TEXT_PRIMARY};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 60px;
            }}
            QMessageBox QPushButton:hover {{
                background: #66BB6A;
            }}
        """)
        dialog.exec()
        
    def _rename_file(self, item: QListWidgetItem, session: RecordingSession):
        """重命名文件"""
        try:
            current_name = f"录制_{session.metadata.start_time.strftime('%H%M')}"
            
            dialog = QInputDialog(self)
            dialog.setWindowTitle("重命名文件")
            dialog.setLabelText("请输入新的文件名:")
            dialog.setTextValue(current_name)
            dialog.setStyleSheet(f"""
                QInputDialog {{
                    background: {DGLabColors.BACKGROUND_PRIMARY};
                    color: {DGLabColors.TEXT_PRIMARY};
                }}
                QInputDialog QLabel {{
                    color: {DGLabColors.TEXT_PRIMARY};
                }}
                QInputDialog QLineEdit {{
                    background: {DGLabColors.BACKGROUND_INPUT};
                    color: {DGLabColors.TEXT_PRIMARY};
                    border: 1px solid {DGLabColors.BORDER_SECONDARY};
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 14px;
                }}
                QInputDialog QLineEdit:focus {{
                    border-color: {DGLabColors.ACCENT_GOLD};
                }}
                QInputDialog QPushButton {{
                    background: {DGLabColors.ACCENT_GOLD};
                    color: {DGLabColors.BACKGROUND_PRIMARY};
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                    min-width: 60px;
                }}
                QInputDialog QPushButton:hover {{
                    background: {DGLabColors.ACCENT_GOLD_LIGHT};
                }}
            """)
            
            ok = dialog.exec()
            new_name = dialog.textValue()
            
            if ok and new_name and new_name != current_name:
                # 验证文件名
                if self._validate_filename(new_name):
                    # 更新显示文本
                    duration = self.format_duration(session.get_duration_ms())
                    time_str = session.metadata.start_time.strftime("%m-%d %H:%M")
                    display_text = f"{new_name}.dgr - {duration}\n{time_str}"
                    item.setText(display_text)
                    
                    self.show_success(f"文件已重命名为: {new_name}.dgr")
                    logger.info(f"文件重命名成功: {current_name} -> {new_name}")
                else:
                    self.show_error("文件名包含无效字符，请使用字母、数字、中文或下划线")
        except Exception as e:
            logger.error(f"重命名文件时出错: {e}")
            self.show_error(f"重命名失败: {str(e)}")
            
    def _validate_filename(self, filename: str) -> bool:
        """验证文件名是否有效"""
        if not filename or len(filename.strip()) == 0:
            return False
            
        # 检查非法字符
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        for char in invalid_chars:
            if char in filename:
                return False
                
        # 检查长度
        if len(filename) > 100:
            return False
            
        return True
            
    def _export_file(self, session: RecordingSession):
        """导出文件"""
        try:
            default_name = f"录制_{session.metadata.start_time.strftime('%Y%m%d_%H%M%S')}.dgr"
            
            dialog = QFileDialog(self)
            dialog.setWindowTitle("导出录制文件")
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            dialog.setNameFilter(translate("recording.recording_files_filter"))
            dialog.selectFile(default_name)
            dialog.setStyleSheet(f"""
                QFileDialog {{
                    background: {DGLabColors.BACKGROUND_PRIMARY};
                    color: {DGLabColors.TEXT_PRIMARY};
                }}
                QFileDialog QLabel {{
                    color: {DGLabColors.TEXT_PRIMARY};
                }}
                QFileDialog QTreeView {{
                    background: {DGLabColors.BACKGROUND_SECONDARY};
                    color: {DGLabColors.TEXT_PRIMARY};
                }}
                QFileDialog QLineEdit {{
                    background: {DGLabColors.BACKGROUND_INPUT};
                    color: {DGLabColors.TEXT_PRIMARY};
                    border: 1px solid {DGLabColors.BORDER_SECONDARY};
                }}
                QFileDialog QPushButton {{
                    background: {DGLabColors.ACCENT_GOLD};
                    color: {DGLabColors.BACKGROUND_PRIMARY};
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                    min-width: 60px;
                }}
                QFileDialog QPushButton:hover {{
                    background: {DGLabColors.ACCENT_GOLD_LIGHT};
                }}
            """)
            
            if dialog.exec():
                file_paths = dialog.selectedFiles()
                if file_paths:
                    file_path = file_paths[0]
                    
                    # 确保文件扩展名
                    if not file_path.lower().endswith('.dgr'):
                        file_path += '.dgr'
                    
                    # 检查文件是否已存在
                    if os.path.exists(file_path):
                        reply = QMessageBox.question(
                            self, "文件已存在", 
                            f"文件 {os.path.basename(file_path)} 已存在。\n是否要覆盖它？",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                            QMessageBox.StandardButton.No
                        )
                        if reply != QMessageBox.StandardButton.Yes:
                            return
                    
                    # 实现文件保存逻辑
                    asyncio.create_task(self._save_recording_to_file(session, file_path))
                    
                    # 异步执行导出操作
                    asyncio.create_task(self._perform_export(session, file_path))
                    
        except Exception as e:
            logger.error(f"导出文件时出错: {e}")
            self.show_error(f"导出失败: {str(e)}")
            
    async def _perform_export(self, session: RecordingSession, file_path: str):
        """异步执行文件导出"""
        try:
            # 模拟导出延迟
            await asyncio.sleep(0.5)
            
            # 实际保存文件
            file_manager = DGRFileManager()
            await file_manager.save_recording(session, file_path)
            
            # 导出成功
            filename = os.path.basename(file_path)
            logger.info(f"文件导出成功: {filename}")
            
        except Exception as e:
            logger.error(f"执行文件导出时出错: {e}")
            
            
    def _show_import_dialog(self) -> Optional[str]:
        """显示导入文件对话框（主线程）"""
        try:
            dialog = QFileDialog(self)
            dialog.setWindowTitle("导入录制文件")
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            dialog.setNameFilter(f"{translate('recording.recording_files_filter')};;{translate('recording.all_files_filter')}")
            dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            dialog.setStyleSheet(f"""
                QFileDialog {{
                    background: {DGLabColors.BACKGROUND_PRIMARY};
                    color: {DGLabColors.TEXT_PRIMARY};
                }}
                QFileDialog QLabel {{
                    color: {DGLabColors.TEXT_PRIMARY};
                }}
                QFileDialog QTreeView {{
                    background: {DGLabColors.BACKGROUND_SECONDARY};
                    color: {DGLabColors.TEXT_PRIMARY};
                }}
                QFileDialog QLineEdit {{
                    background: {DGLabColors.BACKGROUND_INPUT};
                    color: {DGLabColors.TEXT_PRIMARY};
                    border: 1px solid {DGLabColors.BORDER_SECONDARY};
                }}
                QFileDialog QPushButton {{
                    background: {DGLabColors.ACCENT_GOLD};
                    color: {DGLabColors.BACKGROUND_PRIMARY};
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                    min-width: 60px;
                }}
                QFileDialog QPushButton:hover {{
                    background: {DGLabColors.ACCENT_GOLD_LIGHT};
                }}
            """)
            
            if dialog.exec():
                file_paths = dialog.selectedFiles()
                if file_paths:
                    return file_paths[0]
            return None
                    
        except Exception as e:
            logger.error(f"显示导入对话框时出错: {e}")
            return None
            
    async def _load_recording_from_file(self, file_path: str) -> None:
        """从文件加载录制会话"""
        try:
            # 使用DGRFileManager加载文件
            file_manager = DGRFileManager()
            session = await file_manager.load_recording(file_path)
            
            # 添加到会话列表
            self.sessions.append(session)
            
            # 生成完整的文件名显示
            file_name = f"{translate('recording.import_prefix')}{session.metadata.start_time.strftime('%Y%m%d_%H%M%S')}.dgr"
            duration = self.format_duration(session.get_duration_ms())
            time_str = session.metadata.start_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 创建文件列表项
            display_text = f"{file_name} - {duration}\n{time_str}"
            item = QListWidgetItem(display_text)
            item.setData(256, session)  # 存储会话数据
            
            self.file_list.addItem(item)
            
            # 自动选中导入的文件
            self.file_list.setCurrentItem(item)
            self.current_session = session
            self.update_playback_ui_state()
            
            logger.info(f"录制文件导入成功: {file_path}")
            
        except FileNotFoundError:
            logger.error("文件不存在，请检查文件路径")
        except ValueError as e:
            logger.error(f"文件格式无效: {str(e)}")
        except Exception as e:
            logger.error(f"加载录制文件失败: {e}")
            
    def _delete_file(self, item: QListWidgetItem, session: RecordingSession):
        """删除文件"""
        try:
            # 检查文件是否正在录制中
            if self.service_controller:
                device_service = self.service_controller.dglab_device_service
                if device_service:
                    record_handler = device_service.get_record_handler()
                    if record_handler:
                        current_session = record_handler.get_current_session()
                        if current_session and current_session.metadata.session_id == session.metadata.session_id:
                            self.show_warning(translate("recording.cannot_delete_recording_file"))
                            return
            
            # 检查文件是否正在播放中
            if self.current_session and self.current_session.metadata.session_id == session.metadata.session_id:
                if self.service_controller:
                    device_service = self.service_controller.dglab_device_service
                    if device_service:
                        playback_handler = device_service.get_playback_handler()
                        if playback_handler and playback_handler.get_playback_state() != PlaybackState.IDLE:
                            self.show_warning(translate("recording.cannot_delete_playing_file"))
                            return
            
            # 创建自定义确认对话框
            dialog = QDialog(self)
            dialog.setWindowTitle(translate("recording.confirm_delete_file"))
            dialog.setFixedSize(450, 250)
            dialog.setModal(True)
            
            # 主布局
            main_layout = QVBoxLayout(dialog)
            main_layout.setSpacing(15)
            main_layout.setContentsMargins(20, 20, 20, 20)
            
            # 图标和主文本
            header_layout = QHBoxLayout()
            icon_label = QLabel("?")
            icon_label.setFixedSize(50, 50)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setStyleSheet(f"""
                QLabel {{
                    background: {DGLabColors.ACCENT_GOLD};
                    color: {DGLabColors.BACKGROUND_PRIMARY};
                    font-size: 24px;
                    font-weight: bold;
                    border-radius: 25px;
                }}
            """)
            
            main_text = QLabel(translate("recording.confirm_delete_file_msg"))
            main_text.setStyleSheet(f"""
                QLabel {{
                    color: {DGLabColors.TEXT_PRIMARY};
                    font-size: 16px;
                    font-weight: bold;
                }}
            """)
            
            header_layout.addWidget(icon_label)
            header_layout.addWidget(main_text)
            header_layout.addStretch()
            main_layout.addLayout(header_layout)
            
            # 详细信息
            file_name = f"{translate('recording.recording_prefix')}{session.metadata.start_time.strftime('%Y%m%d_%H%M%S')}.dgr"
            duration = self.format_duration(session.get_duration_ms())
            detail_text = f"{translate('recording.file_name').format(file_name)}\n{translate('recording.create_time').format(session.metadata.start_time.strftime('%Y-%m-%d %H:%M:%S'))}\n{translate('recording.recording_duration').format(duration)}"
            
            detail_label = QLabel(detail_text)
            detail_label.setStyleSheet(f"""
                QLabel {{
                    color: {DGLabColors.TEXT_SECONDARY};
                    font-size: 12px;
                    background: {DGLabColors.BACKGROUND_INPUT};
                    border: 1px solid {DGLabColors.BORDER_SECONDARY};
                    border-radius: 6px;
                    padding: 10px;
                }}
            """)
            detail_label.setWordWrap(True)
            main_layout.addWidget(detail_label)
            
            # 按钮
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            
            delete_btn = QPushButton(translate("recording.context_menu_delete"))
            delete_btn.setFixedSize(80, 35)
            delete_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {DGLabColors.STATUS_RECORDING};
                    color: {DGLabColors.TEXT_PRIMARY};
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: #FF6666;
                }}
            """)
            
            cancel_btn = QPushButton(translate("recording.context_menu_cancel"))
            cancel_btn.setFixedSize(80, 35)
            cancel_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {DGLabColors.BORDER_SECONDARY};
                    color: {DGLabColors.TEXT_PRIMARY};
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: #666666;
                }}
            """)
            
            button_layout.addWidget(cancel_btn)
            button_layout.addWidget(delete_btn)
            main_layout.addLayout(button_layout)
            
            # 对话框样式
            dialog.setStyleSheet(f"""
                QDialog {{
                    background: {DGLabColors.BACKGROUND_PRIMARY};
                    color: {DGLabColors.TEXT_PRIMARY};
                }}
            """)
            
            # 连接信号
            delete_btn.clicked.connect(dialog.accept)
            cancel_btn.clicked.connect(dialog.reject)
            cancel_btn.setDefault(True)
            
            # 显示对话框
            result = dialog.exec()
            
            if result == QDialog.DialogCode.Accepted:
                # 执行删除操作
                row = self.file_list.row(item)
                self.file_list.takeItem(row)
                
                # 从会话列表中移除
                if session in self.sessions:
                    self.sessions.remove(session)
                    
                # 清除选中状态
                if self.current_session == session:
                    self.current_session = None
                    self.update_playback_ui_state()
                
                self.show_success(translate("recording.file_removed_from_list"))
                logger.info(f"文件已从列表中移除: {session.metadata.session_id}")
                
        except Exception as e:
            logger.error(f"从列表中移除文件时出错: {e}")
            self.show_error(f"移除失败: {str(e)}")
                
    def _show_file_details(self, session: RecordingSession):
        """显示文件详细信息"""
        # 创建详细信息对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("录制文件详情")
        dialog.setFixedSize(400, 300)
        dialog.setStyleSheet(f"""
            QDialog {{
                background: {DGLabColors.BACKGROUND_PRIMARY};
                color: {DGLabColors.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {DGLabColors.TEXT_PRIMARY};
            }}
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 文件信息
        info_text = f"""
        <h3 style="color: {DGLabColors.ACCENT_GOLD};">文件信息</h3>
        <p><b>会话ID:</b> {session.metadata.session_id[:16]}...</p>
        <p><b>创建时间:</b> {session.metadata.start_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><b>录制时长:</b> {self.format_duration(session.get_duration_ms())}</p>
        <p><b>快照数量:</b> {len(session.snapshots)}个</p>
        
        <h3 style="color: {DGLabColors.ACCENT_GOLD};">通道信息</h3>
        <p><b>数据点数:</b> {len(session.snapshots)} × 2通道</p>
        <p><b>采样频率:</b> 10Hz (每100ms)</p>
        """
        
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_button = QPushButton("确定")
        ok_button.setStyleSheet(f"""
            QPushButton {{
                background: {DGLabColors.ACCENT_GOLD};
                color: {DGLabColors.BACKGROUND_PRIMARY};
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {DGLabColors.ACCENT_GOLD_LIGHT};
            }}
        """)
        ok_button.clicked.connect(dialog.accept)
        button_layout.addWidget(ok_button)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
        
    
    # ================== 回放回调方法 ==================
    
    def _on_playback_progress_changed(self, current: int, total: int, percentage: float) -> None:
        """回放进度变化回调"""
        if not self._slider_being_dragged:
            # 更新进度滑块
            progress_percent = int(percentage)
            self.progress_slider.setValue(progress_percent)
            
            # 更新时间显示
            if self.current_session and self.current_session.metadata:
                duration_ms = self.current_session.get_duration_ms()
                current_time_ms = int((current / total) * duration_ms) if total > 0 else 0
                current_minutes, current_seconds = divmod(current_time_ms // 1000, 60)
                self.current_time_label.setText(f"{current_minutes:02d}:{current_seconds:02d}")
        
        logger.debug(f"播放进度: {current}/{total} ({percentage:.1f}%)")
        
    def _on_playback_state_changed(self, old_state: RecordingPlaybackState, new_state: RecordingPlaybackState) -> None:
        """回放状态变化回调"""        
        if new_state == RecordingPlaybackState.PLAYING:
            self._update_ui_for_playing_state()
        elif new_state == RecordingPlaybackState.PAUSED:
            self._update_ui_for_paused_state()
        elif new_state == RecordingPlaybackState.IDLE:
            self._update_ui_for_idle_state()
    
    def _on_playback_error(self, error_type: str, message: str) -> None:
        """回放错误回调"""
        logger.error(f"回放错误 [{error_type}]: {message}")
        self.show_error(f"回放错误: {message}")
    
    def _update_ui_for_playing_state(self) -> None:
        """更新UI到播放状态"""
        self.play_btn.setEnabled(False)
        self.pause_playback_btn.setEnabled(True)
        self.stop_playback_btn.setEnabled(True)
        self._update_recording_status_text(RecordingState.IDLE, PlaybackState.PLAYING)
        logger.debug("UI状态: 播放中")
        
    def _update_ui_for_paused_state(self) -> None:
        """更新UI到暂停状态"""
        self.play_btn.setEnabled(True)
        self.pause_playback_btn.setEnabled(False)
        self.resume_playback_btn.setEnabled(True)
        self.stop_playback_btn.setEnabled(True)
        self._update_recording_status_text(RecordingState.IDLE, PlaybackState.PAUSED)
        logger.debug("UI状态: 已暂停")
        
    def _update_ui_for_idle_state(self) -> None:
        """更新UI到空闲状态"""
        self.play_btn.setEnabled(True)
        self.pause_playback_btn.setEnabled(False)
        self.resume_playback_btn.setEnabled(False)
        self.stop_playback_btn.setEnabled(False)
        self._update_recording_status_text(RecordingState.IDLE, PlaybackState.IDLE)
        
        # 播放完成后重置进度到开始位置
        self.progress_slider.setValue(0)
        self.current_time_label.setText("00:00")
        logger.debug("UI状态: 就绪")
    
    def _update_recording_status_text(self, recording_state: RecordingState, playback_state: Optional[PlaybackState] = None) -> None:
        """统一更新录制状态文本
        
        Args:
            recording_state: 录制状态
            playback_state: 播放状态（当录制状态为IDLE时有效）
        """
        if recording_state == RecordingState.RECORDING:
            self.recording_status_text.setText(translate("recording.status.recording"))
        elif recording_state == RecordingState.PAUSED:
            self.recording_status_text.setText(translate("recording.recording_paused"))
        elif recording_state == RecordingState.IDLE:
            # 录制空闲时，检查播放状态
            if playback_state == PlaybackState.PLAYING:
                self.recording_status_text.setText(translate("recording.status.playing"))
            elif playback_state == PlaybackState.PAUSED:
                self.recording_status_text.setText(translate("recording.status.paused"))
            else:
                self.recording_status_text.setText(translate("recording.ready"))
        else:
            # 未知状态或设备未连接
            self.recording_status_text.setText(translate("recording.device_disconnected"))
    
    def _update_playback_ui_controls(self, playback_state: PlaybackState, has_session: bool = False) -> None:
        """统一更新播放控件状态
        
        Args:
            playback_state: 当前播放状态
            has_session: 是否有选中的录制会话
        """
        if playback_state == PlaybackState.PLAYING:
            # 播放中：隐藏播放和继续按钮，显示暂停和停止按钮
            self.play_btn.setVisible(False)
            self.pause_playback_btn.setVisible(True)
            self.resume_playback_btn.setVisible(False)
            self.stop_playback_btn.setEnabled(True)
        elif playback_state == PlaybackState.PAUSED:
            # 暂停中：隐藏播放和暂停按钮，显示继续和停止按钮
            self.play_btn.setVisible(False)
            self.pause_playback_btn.setVisible(False)
            self.resume_playback_btn.setVisible(True)
            self.stop_playback_btn.setEnabled(True)
        else:  # PlaybackState.IDLE
            # 空闲状态：显示播放按钮，隐藏暂停和继续按钮
            self.play_btn.setVisible(True)
            self.play_btn.setEnabled(has_session)
            self.pause_playback_btn.setVisible(False)
            self.resume_playback_btn.setVisible(False)
            self.stop_playback_btn.setEnabled(False)
    
    async def _sync_playback_mode_to_protocol(self, playback_mode: PlaybackMode) -> None:
        """同步播放模式到协议层"""
        if not self.service_controller:
            return
        
        device_service = self.service_controller.dglab_device_service
        if device_service:
            # 通过设备服务设置播放模式
            device_service.set_playback_mode(playback_mode)
        
    def update_all_ui_state(self):
        """统一更新所有UI状态（简化的入口方法）"""
        if not self.service_controller:
            # 设备未连接状态
            self.update_connection_status()
            self._update_recording_status_text(RecordingState.IDLE, None)
            self._update_playback_ui_controls(PlaybackState.IDLE, bool(self.current_session))
            return
        
        # 设备已连接，更新所有状态
        self.update_connection_status()
        self.update_recording_status()
        self.update_playback_status()
        self.update_status_bar()
        
    def cleanup_resources(self) -> None:
        """清理资源和断开连接"""
        try:
            # 停止定时器
            if self.update_timer.isActive():
                self.update_timer.stop()
                
            # 停止录制动画定时器
            if self._recording_animation and self._recording_animation.isActive():
                self._recording_animation.stop()
                
            # 断开语言更新信号
            language_signals.language_changed.disconnect(self.update_ui_texts)
            
            logger.debug("录制标签页资源已清理")
        except Exception as e:
            logger.error(f"清理录制标签页资源时出错: {e}")
        
    def update_ui_texts(self):
        """更新UI文本（语言切换时调用）"""
        # 更新按钮文本
        self.start_record_btn.setText(translate("recording.start_recording"))
        self.stop_record_btn.setText(translate("recording.stop_recording"))
        self.pause_record_btn.setText(translate("recording.pause"))
        self.resume_record_btn.setText(translate("recording.resume"))
        self.import_btn.setText(translate("recording.import_file"))
        self.play_btn.setText(translate("recording.play"))
        self.pause_playback_btn.setText(translate("recording.pause"))
        self.resume_playback_btn.setText(translate("recording.resume"))
        self.stop_playback_btn.setText(translate("recording.stop"))
        self.loop_btn.setText(translate("recording.loop"))
        
        # 更新状态文本（根据实际状态）
        self.update_status_bar()
        # 更新连接状态（根据实际连接状态）
        self.update_connection_status()
        
        # 更新时长显示
        self.recording_time_label.setText(translate("recording.duration").format("00:00"))
        
        # 更新选中文件显示
        if self.current_session and self.current_session.metadata:
            file_name = f"{translate('recording.recording_prefix')}{self.current_session.metadata.start_time.strftime('%Y%m%d_%H%M%S')}.dgr"
            self.selected_file_text.setText(translate("recording.selected_file").format(file_name))