import logging
from PySide6.QtWidgets import  QVBoxLayout, QGroupBox, QLabel, QWidget

from typing import Optional

from core.service_controller import ServiceController
from gui.connection.bluetooth.bluetooth_manager import BluetoothConnectionManager
from gui.ui_interface import UIInterface
from i18n import translate
from models import ConnectionState, SettingsDict

logger = logging.getLogger(__name__)


class BluetoothConnectionWidget(QWidget):
    """蓝牙连接配置组件"""
    
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.settings: SettingsDict = ui_interface.settings
        
        # 蓝牙连接管理器
        self.connection_manager = BluetoothConnectionManager(ui_interface)
        
        # UI组件类型注解
        self.bluetooth_settings_group: QGroupBox
        self.placeholder_label: QLabel

        self.init_ui()
    
    @property
    def service_controller(self) -> Optional[ServiceController]:
        """通过蓝牙连接管理器获取服务控制器"""
        # 暂时返回None，后续实现
        return None

    def init_ui(self) -> None:
        """初始化蓝牙连接设置UI"""
        layout = QVBoxLayout()
        # 移除布局边距和间距
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 蓝牙设置组
        self.bluetooth_settings_group = QGroupBox(translate("connection_tab.bluetooth_settings"))
        bluetooth_layout = QVBoxLayout()
        bluetooth_layout.setContentsMargins(10, 10, 10, 10)  # 保持组内的少量边距

        # 占位文字
        self.placeholder_label = QLabel(translate("connection_tab.bluetooth_placeholder"))
        self.placeholder_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 14px;
                padding: 20px;
                text-align: center;
                background-color: #f9f9f9;
                border: 2px dashed #ccc;
                border-radius: 10px;
            }
        """)
        bluetooth_layout.addWidget(self.placeholder_label)

        self.bluetooth_settings_group.setLayout(bluetooth_layout)
        layout.addWidget(self.bluetooth_settings_group)
        layout.addStretch()  # 添加弹性空间

        self.setLayout(layout)

    def load_settings(self) -> None:
        """加载蓝牙设置到UI元素"""
        # 暂时为空，后续实现
        pass

    def save_settings(self, osc_port: int, language: str) -> None:
        """保存蓝牙设置"""
        self.connection_manager.save_settings()
        
        # 保存全局设置
        self.settings['osc_port'] = osc_port
        self.settings['language'] = language

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connection_manager.is_connected()

    def update_connection_state(self, state: ConnectionState, message: str = "") -> None:
        """更新连接状态（暂时为空实现）"""
        # 暂时为空，后续实现
        pass

    def update_ui_texts(self) -> None:
        """更新UI上的文本为当前语言"""
        self.bluetooth_settings_group.setTitle(translate("connection_tab.bluetooth_settings"))
        self.placeholder_label.setText(translate("connection_tab.bluetooth_placeholder"))

    def start_button_clicked(self) -> None:
        """启动按钮点击 - 委托给蓝牙连接管理器"""
        if self.connection_manager.is_connected():
            # 停止连接
            self.connection_manager.stop_connection()
        else:
            # 启动连接
            self.connection_manager.start_connection()
