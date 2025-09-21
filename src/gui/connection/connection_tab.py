import logging
from typing import Optional

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
                               QComboBox, QSpinBox, QLabel, QPushButton, QMessageBox, QStackedWidget, QSizePolicy)

from config import save_settings
from gui.connection.websocket.websocket_widget import WebSocketConnectionWidget
from gui.connection.bluetooth.bluetooth_widget import BluetoothConnectionWidget
from gui.widgets import SegmentedControl
from i18n import translate, language_signals, LANGUAGES, get_current_language, set_language
from models import ConnectionState, SettingsDict, ConnectionMode
from gui.ui_interface import UIInterface
from gui.styles import CommonColors

logger = logging.getLogger(__name__)


class ConnectionTab(QWidget):
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.settings: SettingsDict = ui_interface.settings

        # UI组件类型注解
        self.global_settings_group: QGroupBox
        self.global_settings_layout: QFormLayout
        self.connection_mode_group: QGroupBox
        self.connection_mode_layout: QFormLayout
        self.connection_mode_control: SegmentedControl
        self.connection_stack: QStackedWidget
        self.osc_port_spinbox: QSpinBox
        self.language_layout: QHBoxLayout
        self.language_label: QLabel
        self.language_combo: QComboBox
        self.save_settings_button: QPushButton

        # 连接组件
        self.websocket_widget: WebSocketConnectionWidget
        self.bluetooth_widget: BluetoothConnectionWidget
        
        # 当前连接模式
        self.current_connection_mode: ConnectionMode = ConnectionMode.WEBSOCKET

        # 保存表单标签的引用，用于语言切换时更新
        self.osc_port_label: QLabel
        self.connection_mode_label: QLabel

        self.init_ui()
        self.load_settings()

        # 连接语言变更信号
        language_signals.language_changed.connect(self.update_ui_texts)

    def init_ui(self) -> None:
        """初始化连接设置选项卡UI"""
        layout = QVBoxLayout()
        layout.setSpacing(8)  # 减少组件间的垂直间距

        # =================== 连接模式选择组 ===================
        self.connection_mode_group = QGroupBox(translate("connection_tab.connection_mode"))
        self.connection_mode_layout = QFormLayout()
        self.connection_mode_layout.setContentsMargins(15, 8, 15, 8)  # 减少上下内边距
        self.connection_mode_layout.setVerticalSpacing(6)  # 减少垂直间距
        self.connection_mode_layout.setHorizontalSpacing(12)  # 标签和控件间距

        # 连接模式分段控制器（WebSocket/蓝牙）
        segments = [
            translate("connection_tab.websocket_mode"),
            translate("connection_tab.bluetooth_mode")
        ]
        self.connection_mode_control = SegmentedControl(segments)
        self.connection_mode_control.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.connection_mode_control.selectionChanged.connect(self.on_connection_mode_changed)
        
        # 添加标签和控件到表单布局
        self.connection_mode_label = QLabel(translate("connection_tab.connection_mode_label"))
        self.connection_mode_layout.addRow(self.connection_mode_label, self.connection_mode_control)
        
        self.connection_mode_group.setLayout(self.connection_mode_layout)
        layout.addWidget(self.connection_mode_group)

        # =================== 连接配置堆栈 ===================
        self.connection_stack = QStackedWidget()

        # 创建WebSocket连接组件
        self.websocket_widget = WebSocketConnectionWidget(self.ui_interface)
        self.connection_stack.addWidget(self.websocket_widget)

        # 创建蓝牙连接组件
        self.bluetooth_widget = BluetoothConnectionWidget(self.ui_interface)
        self.connection_stack.addWidget(self.bluetooth_widget)

        layout.addWidget(self.connection_stack)
        layout.addStretch()  # 添加弹性空间

        # =================== 全局设置组 ===================
        self.global_settings_group = QGroupBox(translate("connection_tab.global_settings"))
        self.global_settings_layout = QFormLayout()

        # OSC端口选择
        self.osc_port_spinbox = QSpinBox()
        self.osc_port_spinbox.setRange(1024, 65535)
        self.osc_port_spinbox.setValue(self.settings.get('osc_port', 9001))
        self.osc_port_label = QLabel(translate("connection_tab.osc_port_label"))
        self.global_settings_layout.addRow(self.osc_port_label, self.osc_port_spinbox)

        # 语言选择
        self.language_layout = QHBoxLayout()
        self.language_label = QLabel(translate("main.settings.language_label"))

        language_options = list(LANGUAGES.values())
        self.language_combo = QComboBox()
        self.language_combo.addItems(language_options)

        # 设置语言数据
        for i, (lang_code, _) in enumerate(LANGUAGES.items()):
            self.language_combo.setItemData(i, lang_code)

        # 设置当前语言
        current_language = self.settings.get('language') or get_current_language()
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == current_language:
                self.language_combo.setCurrentIndex(i)
                break

        # 连接语言选择变更信号
        self.language_combo.currentTextChanged.connect(self.on_language_changed)

        self.language_layout.addWidget(self.language_label)
        self.language_layout.addWidget(self.language_combo)
        self.language_layout.addStretch()

        self.global_settings_layout.addRow(self.language_layout)

        # 添加保存设置按钮
        self.save_settings_button = QPushButton(translate("connection_tab.save_settings"))
        self.save_settings_button.setStyleSheet(CommonColors.get_primary_button_style())
        self.save_settings_button.clicked.connect(self.save_all_settings)
        self.global_settings_layout.addRow(self.save_settings_button)

        self.global_settings_group.setLayout(self.global_settings_layout)
        layout.addWidget(self.global_settings_group)

        # 设置主布局的内边距
        layout.setContentsMargins(10, 10, 10, 10)  # 减少整体内边距
        self.setLayout(layout)

    def load_settings(self) -> None:
        """加载设置到UI元素"""
        # 根据设置设置连接模式
        connection_settings = self.settings.get('connection', {})
        connection_mode = connection_settings.get('mode', ConnectionMode.WEBSOCKET.value)
        
        if connection_mode == ConnectionMode.BLUETOOTH.value:
            self.current_connection_mode = ConnectionMode.BLUETOOTH
            self.connection_mode_control.set_selected_index(1)  # 蓝牙
            self.connection_stack.setCurrentWidget(self.bluetooth_widget)
        else:
            self.current_connection_mode = ConnectionMode.WEBSOCKET
            self.connection_mode_control.set_selected_index(0)  # WebSocket
            self.connection_stack.setCurrentWidget(self.websocket_widget)
        
        self.connection_mode_control.setEnabled(True)

    def on_connection_mode_changed(self, index: int) -> None:
        """连接模式切换处理 - 使用分段控制器"""
        if index == 1:
            # 切换到蓝牙模式
            self.current_connection_mode = ConnectionMode.BLUETOOTH
            self.connection_stack.setCurrentWidget(self.bluetooth_widget)
            # 保存连接模式设置
            if 'connection' not in self.settings:
                self.settings['connection'] = {}
            self.settings['connection']['mode'] = ConnectionMode.BLUETOOTH.value
            logger.info("切换到蓝牙连接模式")
        else:
            # 切换到WebSocket模式 (index == 0)
            self.current_connection_mode = ConnectionMode.WEBSOCKET
            self.connection_stack.setCurrentWidget(self.websocket_widget)
            # 保存连接模式设置
            if 'connection' not in self.settings:
                self.settings['connection'] = {}
            self.settings['connection']['mode'] = ConnectionMode.WEBSOCKET.value
            logger.info("切换到WebSocket连接模式")
    
    def save_all_settings(self) -> None:
        """保存所有设置按钮点击事件"""
        try:
            # 委托给当前连接组件保存设置
            osc_port = self.osc_port_spinbox.value()
            language = self.language_combo.currentData()
            
            # 调用对应组件的保存方法
            if self.current_connection_mode == ConnectionMode.BLUETOOTH:
                self.bluetooth_widget.save_settings(osc_port, language)
            else:
                self.websocket_widget.save_settings(osc_port, language)
            
            # 保存连接模式设置
            save_settings(self.settings)
            
            # 显示保存成功提示
            QMessageBox.information(self, translate("common.save_success"), translate("connection_tab.settings_saved_successfully"))
            
        except Exception as e:
            # 显示保存失败提示
            error_msg = translate("connection_tab.save_settings_failed").format(str(e))
            QMessageBox.warning(self, translate("common.error"), error_msg)

    def update_connection_state(self, state: ConnectionState, message: str = "") -> None:
        """更新连接状态 - 委托给当前连接组件"""
        # 委托给当前连接组件处理状态更新
        if self.current_connection_mode == ConnectionMode.BLUETOOTH:
            self.bluetooth_widget.update_connection_state(state, message)
        else:
            self.websocket_widget.update_connection_state(state, message)
        
        # 更新连接模式分段控制器的启用状态
        self.connection_mode_control.setEnabled(state == ConnectionState.DISCONNECTED)

    def on_language_changed(self) -> None:
        """处理语言选择变更，立即生效但不保存到文件"""
        selected_language: Optional[str] = self.language_combo.currentData()
        if selected_language:
            success: bool = set_language(selected_language)
            if success:
                logger.info(f"Language changed to {LANGUAGES.get(selected_language, selected_language)} ({selected_language})")

    def update_ui_texts(self) -> None:
        """更新UI上的文本为当前语言"""
        
        # 更新组标题和标签
        self.connection_mode_group.setTitle(translate("connection_tab.connection_mode"))
        self.global_settings_group.setTitle(translate("connection_tab.global_settings"))
        self.language_label.setText(translate("main.settings.language_label"))
        
        # 更新表单标签
        self.connection_mode_label.setText(translate("connection_tab.connection_mode_label"))
        self.osc_port_label.setText(translate("connection_tab.osc_port_label"))
        self.save_settings_button.setText(translate("connection_tab.save_settings"))
        
        # 更新分段控制器的标签 - 使用更优雅的方式
        segments = [
            translate("connection_tab.websocket_mode"),
            translate("connection_tab.bluetooth_mode")
        ]
        
        # 直接更新分段文本，无需重新创建
        self.connection_mode_control.update_segments(segments)

        # 委托给当前连接组件更新文本
        self.websocket_widget.update_ui_texts()
        self.bluetooth_widget.update_ui_texts()

    def get_current_connection_mode(self) -> ConnectionMode:
        """获取当前连接模式"""
        return self.current_connection_mode