import asyncio
import logging
from typing import Optional

from PySide6.QtCore import Qt, QLocale, QTimer
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
                               QComboBox, QSpinBox, QLabel, QPushButton, QLineEdit, QCheckBox, QMessageBox, QSizePolicy, QWidget)

from config import get_active_ip_addresses, save_settings
from core.service_controller import ServiceController
from gui.connection.websocket.websocket_manager import logger, WebSocketConnectionManager
from gui.ui_interface import UIInterface
from gui.widgets import EditableComboBox
from i18n import translate
from models import ConnectionState, SettingsDict

logger = logging.getLogger(__name__)


class WebSocketConnectionWidget(QWidget):
    """WebSocket连接配置组件"""
    
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.settings: SettingsDict = ui_interface.settings
        
        # WebSocket连接管理器
        self.connection_manager = WebSocketConnectionManager(ui_interface)
        
        # UI组件类型注解
        self.connection_settings_group: QGroupBox
        self.connection_settings_layout: QFormLayout
        self.device_pairing_group: QGroupBox
        self.device_pairing_layout: QVBoxLayout
        self.network_group_layout: QHBoxLayout
        self.ip_combobox: QComboBox
        self.port_spinbox: QSpinBox
        self.enable_remote_checkbox: QCheckBox
        self.remote_address_edit: QLineEdit
        self.get_public_ip_button: QPushButton
        self.remote_address_layout: QHBoxLayout
        self.connection_status_label: QLabel
        self.start_button: QPushButton
        self.qrcode_label: QLabel
        self.original_qrcode_pixmap: Optional[QPixmap]  # 保存原始二维码图像

        # 保存表单标签的引用，用于语言切换时更新
        self.interface_label: QLabel
        self.websocket_port_label: QLabel
        self.status_label: QLabel
        self.remote_address_label: QLabel

        # 初始化原始二维码
        self.original_qrcode_pixmap = None

        self.init_ui()
        self.load_settings()
        
        # 连接WebSocket连接管理器的信号
        self._connect_manager_signals()

    def _connect_manager_signals(self) -> None:
        """连接WebSocket连接管理器的信号"""
        self.connection_manager.signals.public_ip_received.connect(self._on_public_ip_received)
        self.connection_manager.signals.validation_error.connect(self._on_validation_error)
        self.connection_manager.signals.qrcode_updated.connect(self.update_qrcode)
    
    @property
    def service_controller(self) -> Optional[ServiceController]:
        """通过WebSocket连接管理器获取服务控制器"""
        return self.connection_manager.service_controller

    def init_ui(self) -> None:
        """初始化WebSocket连接设置UI"""
        layout = QVBoxLayout()
        # 移除布局边距和间距
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 创建网络配置区域的水平布局
        self.network_group_layout = QHBoxLayout()
        self.network_group_layout.setContentsMargins(0, 0, 0, 0)
        self.network_group_layout.setSpacing(5)  # 保持少量间距

        # =================== 左侧：连接设置组 ===================
        self.connection_settings_group = QGroupBox(translate("connection_tab.connection_settings"))
        self.connection_settings_layout = QFormLayout()

        # 网卡选择
        active_ips = get_active_ip_addresses()
        ip_options = [f"{interface}: {ip}" for interface, ip in active_ips.items()]

        self.ip_combobox = EditableComboBox(ip_options)
        # 强制使用英文区域设置，避免数字显示为繁体中文
        self.ip_combobox.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.interface_label = QLabel(translate("connection_tab.interface_label"))
        self.connection_settings_layout.addRow(self.interface_label, self.ip_combobox)

        # 端口选择
        self.port_spinbox = QSpinBox()
        # 强制使用英文区域设置，避免数字显示为繁体中文
        self.port_spinbox.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.port_spinbox.setRange(1024, 65535)
        websocket_settings = self.settings.get('connection', {}).get('websocket', {})
        self.port_spinbox.setValue(websocket_settings.get('port', 8080))
        self.websocket_port_label = QLabel(translate("connection_tab.websocket_port_label"))
        self.connection_settings_layout.addRow(self.websocket_port_label, self.port_spinbox)

        # 创建远程地址控制布局
        self.remote_address_layout = QHBoxLayout()

        # 创建开启异地复选框
        self.enable_remote_checkbox = QCheckBox(translate("connection_tab.enable_remote"))
        self.enable_remote_checkbox.setChecked(websocket_settings.get('enable_remote', False))
        self.enable_remote_checkbox.stateChanged.connect(self.on_remote_enabled_changed)

        # 远程地址输入框
        self.remote_address_edit = QLineEdit()
        # 强制使用英文区域设置，避免数字显示为繁体中文
        self.remote_address_edit.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.remote_address_edit.setText(websocket_settings.get('remote_address', ''))
        self.remote_address_edit.setEnabled(self.enable_remote_checkbox.isChecked())
        self.remote_address_edit.textChanged.connect(self.on_remote_address_changed)
        self.remote_address_edit.setPlaceholderText(translate("connection_tab.please_enter_valid_ip"))

        # 获取公网地址按钮
        self.get_public_ip_button = QPushButton(translate("connection_tab.get_public_ip"))
        self.get_public_ip_button.clicked.connect(self.get_public_ip)
        self.get_public_ip_button.setEnabled(self.enable_remote_checkbox.isChecked())

        # 将控件添加到布局
        self.remote_address_layout.addWidget(self.enable_remote_checkbox)
        self.remote_address_layout.addWidget(self.remote_address_edit)
        self.remote_address_layout.addWidget(self.get_public_ip_button)

        self.remote_address_label = QLabel(translate("connection_tab.remote_address_label"))
        self.connection_settings_layout.addRow(self.remote_address_label, self.remote_address_layout)

        # 添加客户端连接状态标签
        self.connection_status_label = QLabel(translate("connection_tab.offline"))
        self.connection_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_status_label.setStyleSheet("""
            QLabel {
                background-color: red;
                color: white;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        self.connection_status_label.adjustSize()
        self.status_label = QLabel(translate("connection_tab.status_label"))
        self.connection_settings_layout.addRow(self.status_label, self.connection_status_label)

        # 启动按钮
        self.start_button = QPushButton(translate("connection_tab.connect"))
        self.start_button.setStyleSheet("background-color: green; color: white;")
        self.start_button.clicked.connect(self.start_button_clicked)
        self.connection_settings_layout.addRow(self.start_button)

        # 设置连接设置组布局
        self.connection_settings_group.setLayout(self.connection_settings_layout)
        self.connection_settings_group.setMinimumWidth(350)  # 设置最小宽度
        self.network_group_layout.addWidget(self.connection_settings_group)

        # =================== 右侧：设备配对组 ===================
        self.device_pairing_group = QGroupBox(translate("connection_tab.device_pairing"))
        self.device_pairing_layout = QVBoxLayout()

        # 说明文字
        pairing_instruction = QLabel(translate("connection_tab.pairing_instruction"))
        pairing_instruction.setWordWrap(True)
        pairing_instruction.setStyleSheet("color: #666; margin-bottom: 10px;")
        self.device_pairing_layout.addWidget(pairing_instruction)

        # 二维码显示区域
        self.qrcode_label = QLabel()
        # 设置QR码固定尺寸策略，保持正方形
        self.qrcode_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.qrcode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qrcode_label.setFixedSize(280, 280)  # 固定为正方形
        # 设置初始样式和占位文字
        self.qrcode_label.setText(translate("connection_tab.qrcode_placeholder"))
        self._set_qrcode_style(has_qrcode=False)
        
        self.device_pairing_layout.addWidget(self.qrcode_label)

        # 设置设备配对组布局
        self.device_pairing_layout.setContentsMargins(10, 10, 10, 10)  # 减少内边距
        self.device_pairing_group.setLayout(self.device_pairing_layout)
        # 移除固定最小宽度，让组大小完全由QR码决定
        self.network_group_layout.addWidget(self.device_pairing_group)

        # 让连接设置组占用剩余空间，设备配对组最小化
        self.network_group_layout.setStretch(0, 1)  # 连接设置组可扩展
        self.network_group_layout.setStretch(1, 0)  # 设备配对组固定最小尺寸

        # 添加网络配置区域到主布局
        layout.addLayout(self.network_group_layout)
        layout.addStretch()  # 添加弹性空间

        self.setLayout(layout)

    def load_settings(self) -> None:
        """Apply the loaded settings to the UI elements."""
        # 根据设置选择对应的网卡
        websocket_settings = self.settings.get('connection', {}).get('websocket', {})
        for i in range(self.ip_combobox.count()):
            interface_ip = self.ip_combobox.itemText(i).split(": ")
            if len(interface_ip) >= 2:
                _, ip = interface_ip[0], interface_ip[1]
                if ip == websocket_settings.get('ip'):
                    self.ip_combobox.setCurrentIndex(i)
                    logger.info("set to previous used network interface")
                    break

    def save_settings(self, osc_port: int, language: str) -> None:
        """保存WebSocket设置"""
        selected_interface_ip = self.ip_combobox.currentText().split(": ")
        if len(selected_interface_ip) >= 2:
            interface_name, ip = selected_interface_ip[0], selected_interface_ip[1]
        else:
            interface_name, ip = "", ""
        
        self.connection_manager.save_settings(
            interface_name=interface_name,
            ip=ip,
            websocket_port=self.port_spinbox.value(),
            enable_remote=self.enable_remote_checkbox.isChecked(),
            remote_address=self.remote_address_edit.text()
        )
        
        # 保存全局设置
        self.settings['osc_port'] = osc_port
        self.settings['language'] = language
        save_settings(self.settings)

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connection_manager.is_connected()

    def update_qrcode(self, qrcode_pixmap: QPixmap) -> None:
        """更新二维码并保存原始图像"""
        self.original_qrcode_pixmap = qrcode_pixmap
        self._set_qrcode_style(has_qrcode=True)
        self.scale_qrcode()
        logger.info("二维码已更新")

    def _set_qrcode_style(self, has_qrcode: bool = False) -> None:
        """设置QR码标签样式"""
        if has_qrcode:
            self.qrcode_label.setStyleSheet("""
                QLabel {
                    border: 2px solid #4CAF50;
                    border-radius: 10px;
                    background-color: white;
                }
            """)
        else:
            self.qrcode_label.setStyleSheet("""
                QLabel {
                    border: 2px dashed #ccc;
                    border-radius: 10px;
                    background-color: #f9f9f9;
                    color: #999;
                    font-size: 14px;
                }
            """)

    def scale_qrcode(self) -> None:
        """根据标签当前尺寸按比例缩放QR码"""
        if self.original_qrcode_pixmap and not self.original_qrcode_pixmap.isNull():
            # 获取当前标签尺寸
            label_size = self.qrcode_label.size()
            # QR码内容占标签的90%，留出10%作为边距
            qr_size = int(min(label_size.width(), label_size.height()) * 0.9)
            
            scaled_pixmap = self.original_qrcode_pixmap.scaled(
                qr_size, qr_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.qrcode_label.setPixmap(scaled_pixmap)

    def clear_qrcode(self) -> None:
        """清理二维码显示"""
        self.qrcode_label.clear()
        self.original_qrcode_pixmap = None
        # 恢复占位文字和样式
        self.qrcode_label.setText(translate("connection_tab.qrcode_placeholder"))
        self._set_qrcode_style(has_qrcode=False)
        logger.info("二维码已清理")

    def _calculate_proportional_qr_size(self) -> int:
        """基于窗口比例计算QR码尺寸"""
        # 获取窗口尺寸
        window = self.window()
        if window:
            window_size = window.size()
        else:
            window_size = self.size()
        
        # 计算基于窗口较大边的比例
        base_size = max(window_size.width(), window_size.height())
        # QR码占窗口的固定比例
        qr_size = int(base_size * 0.4)
        
        return qr_size

    def _update_qr_label_size(self) -> None:
        """更新QR码标签的尺寸"""
        new_size = self._calculate_proportional_qr_size()
        self.qrcode_label.setFixedSize(new_size, new_size)

    def _update_qr_size_and_scale(self) -> None:
        """更新QR码尺寸并重新缩放内容"""
        self._update_qr_label_size()
        self.scale_qrcode()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """窗口大小改变时按比例调整QR码尺寸"""
        # 先执行父类的resize事件处理
        super().resizeEvent(event)
        # 延迟更新QR码尺寸以保证布局完成
        QTimer.singleShot(0, self._update_qr_size_and_scale)

    def update_connection_state(self, state: ConnectionState, message: str = "") -> None:
        text: str
        style: str
        enabled: bool

        if state == ConnectionState.DISCONNECTED:
            text = translate('connection_tab.connect')
            style = 'background-color: green; color: white;'
            enabled = True
        elif state == ConnectionState.CONNECTING:
            text = translate('connection_tab.cancel')
            style = 'background-color: orange; color: white;'
            enabled = True
        elif state == ConnectionState.WAITING:
            text = translate('connection_tab.disconnect')
            style = 'background-color: blue; color: white;'
            enabled = True
        elif state == ConnectionState.CONNECTED:
            text = translate('connection_tab.disconnect')
            style = 'background-color: red; color: white;'
            enabled = True
        elif state == ConnectionState.FAILED:
            text = message or translate('connection_tab.failed')
            style = 'background-color: red; color: white;'
            enabled = True
        elif state == ConnectionState.ERROR:
            text = message or translate('connection_tab.error')
            style = 'background-color: darkred; color: white;'
            enabled = True

        self.start_button.setText(text)
        self.start_button.setStyleSheet(style)
        self.start_button.setEnabled(enabled)

        self.update_client_state(state == ConnectionState.CONNECTED)

        # 在连接断开时清理二维码
        if state == ConnectionState.DISCONNECTED:
            self.clear_qrcode()

        # 记录错误日志
        if state in [ConnectionState.FAILED, ConnectionState.ERROR] and message:
            self.ui_interface.log_error(message)

    def update_client_state(self, is_online: bool) -> None:
        """根据设备连接状态更新标签的文本和颜色"""
        if is_online:
            self.connection_status_label.setText(translate('connection_tab.online'))
            self.connection_status_label.setStyleSheet("""
                QLabel {
                    background-color: green;
                    color: white;
                    border-radius: 5px;
                    padding: 5px;
                }
            """)
        else:
            self.connection_status_label.setText(translate('connection_tab.offline'))
            self.connection_status_label.setStyleSheet("""
                QLabel {
                    background-color: red;
                    color: white;
                    border-radius: 5px;
                    padding: 5px;
                }
            """)

        self.connection_status_label.adjustSize()

    def start_button_clicked(self) -> None:
        """启动按钮点击 - 委托给WebSocket连接管理器"""
        if self.connection_manager.is_connected():
            # 停止连接
            self.connection_manager.stop_connection()
        else:
            # 启动连接
            selected_ip = self.ip_combobox.currentText().split(": ")[-1]
            osc_port = self.settings.get('osc_port', 9001)
            
            self.connection_manager.start_connection(
                selected_ip=selected_ip,
                websocket_port=self.port_spinbox.value(),
                osc_port=osc_port,
                enable_remote=self.enable_remote_checkbox.isChecked(),
                remote_address=self.remote_address_edit.text() if self.enable_remote_checkbox.isChecked() else None
            )

    def get_public_ip(self) -> None:
        """获取公网IP - 委托给WebSocket连接管理器"""
        asyncio.create_task(self.connection_manager.get_public_ip())

    def validate_ip_address(self, ip: str) -> bool:
        """验证IP地址 - 委托给WebSocket连接管理器"""
        return self.connection_manager.validate_remote_address(ip)

    def on_remote_enabled_changed(self, state: int) -> None:
        """处理开启异地复选框状态变化"""
        is_enabled = bool(state)
        self.remote_address_edit.setEnabled(is_enabled)
        self.get_public_ip_button.setEnabled(is_enabled)

        # 检查远程地址的有效性
        if is_enabled:
            remote_address = self.remote_address_edit.text()
            if remote_address and not self.validate_ip_address(remote_address):
                # 如果远程地址无效，禁用启动按钮 - 使用统一接口
                self._set_button_disabled()
            else:
                # 远程地址有效或为空，启用启动按钮 - 使用统一接口
                self.ui_interface.set_connection_state(ConnectionState.DISCONNECTED)
        else:
            # 未启用远程连接时恢复启动按钮状态 - 使用统一接口
            self.ui_interface.set_connection_state(ConnectionState.DISCONNECTED)

    def on_remote_address_changed(self, text: str) -> None:
        """处理远程地址输入变化"""
        enable_remote = self.enable_remote_checkbox.isChecked()

        # 当启用远程连接时才进行验证
        if enable_remote and text:
            is_valid = self.validate_ip_address(text)
            # IP地址格式无效时显示红色边框
            if not is_valid:
                self.remote_address_edit.setStyleSheet("""
                    QLineEdit {
                        border: 1px solid red;
                        padding: 2px;
                    }
                """)
                # 禁用启动按钮
                self._set_button_disabled()
            else:
                # IP地址格式有效时恢复正常边框
                self.remote_address_edit.setStyleSheet("")
                # 启用启动按钮 - 使用统一接口
                self.ui_interface.set_connection_state(ConnectionState.DISCONNECTED)
        else:
            # 未启用远程连接或地址为空时恢复正常状态
            self.remote_address_edit.setStyleSheet("")
            self.ui_interface.set_connection_state(ConnectionState.DISCONNECTED)

    def _set_button_disabled(self) -> None:
        """禁用按钮状态（用于地址验证失败等情况）"""
        self.start_button.setEnabled(False)
        self.start_button.setStyleSheet("background-color: grey; color: white;")

    def update_ui_texts(self) -> None:
        """更新UI上的文本为当前语言"""
        
        # 更新组标题和标签
        self.connection_settings_group.setTitle(translate("connection_tab.connection_settings"))
        self.device_pairing_group.setTitle(translate("connection_tab.device_pairing"))
        
        # 更新表单标签
        self.interface_label.setText(translate("connection_tab.interface_label"))
        self.websocket_port_label.setText(translate("connection_tab.websocket_port_label"))
        self.status_label.setText(translate("connection_tab.status_label"))
        self.remote_address_label.setText(translate("connection_tab.remote_address_label"))
        
        # 更新其他UI文本
        self.enable_remote_checkbox.setText(translate("connection_tab.enable_remote"))
        self.remote_address_edit.setPlaceholderText(translate("connection_tab.please_enter_valid_ip"))
        self.get_public_ip_button.setText(translate("connection_tab.get_public_ip"))

        # 更新客户端状态
        self.update_connection_state(self.ui_interface.get_connection_state())
    
    # 信号槽方法 - 处理WebSocket连接管理器的通知
    def _on_public_ip_received(self, public_ip: str) -> None:
        """接收到公网IP"""
        self.remote_address_edit.setText(public_ip)
        # 注意：获取公网IP后不自动保存，需用户手动点击保存按钮
    
    def _on_validation_error(self, error_message: str) -> None:
        """接收到验证错误"""
        QMessageBox.warning(self, translate("common.error"), error_message)
