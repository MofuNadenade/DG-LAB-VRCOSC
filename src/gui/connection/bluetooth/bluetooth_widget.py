"""
蓝牙连接配置组件

简化版本，参考WebSocket连接组件的设计：
- 移除复杂的信号机制  
- 使用定时器轮询状态更新
- 简化方法调用链
- 严格类型检查
"""

import asyncio
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QLabel, QWidget,
    QPushButton, QListWidget, QListWidgetItem, QProgressBar,
    QSlider, QMessageBox
)

from config import save_settings
from gui.connection.bluetooth.bluetooth_manager import BluetoothConnectionManager
from gui.ui_interface import UIInterface
from i18n import translate
from models import SettingsDict, ConnectionState, WebsocketDeviceParamsDict

logger = logging.getLogger(__name__)


class BluetoothConnectionWidget(QWidget):
    """蓝牙连接配置组件（简化版本）"""
    
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.settings: SettingsDict = ui_interface.settings
        
        # 蓝牙连接管理器
        self.connection_manager = BluetoothConnectionManager(ui_interface)
        
        # UI组件声明
        self.device_discovery_group: QGroupBox
        self.device_control_group: QGroupBox
        self.device_list: QListWidget
        self.scan_button: QPushButton
        self.connect_button: QPushButton
        self.disconnect_button: QPushButton
        self.connection_status_label: QLabel
        self.battery_label: QLabel
        self.device_info_label: QLabel
        self.battery_progress: QProgressBar
        
        # 设备参数控制组件
        self.strength_limit_a_slider: QSlider
        self.strength_limit_b_slider: QSlider
        self.strength_limit_a_label: QLabel
        self.strength_limit_b_label: QLabel
        self.freq_balance_a_slider: QSlider
        self.freq_balance_b_slider: QSlider
        self.freq_balance_a_label: QLabel
        self.freq_balance_b_label: QLabel
        self.strength_balance_a_slider: QSlider
        self.strength_balance_b_slider: QSlider
        self.strength_balance_a_label: QLabel
        self.strength_balance_b_label: QLabel
        self.apply_params_button: QPushButton
        
        # 初始化UI
        self.init_ui()
        self.load_settings()
        self.setup_tooltips()
        
        # 初始状态：禁用设备控制组
        self.set_device_control_enabled(False)
        
        # 连接蓝牙连接管理器的信号
        self._connect_manager_signals()

    def _connect_manager_signals(self) -> None:
        """连接蓝牙连接管理器的信号"""
        self.connection_manager.signals.battery_level_updated.connect(self.update_battery_level)

    def update_battery_level(self, battery_level: int) -> None:
        """更新电量显示"""
        self.battery_label.setText(f"{battery_level}%")
        self.battery_progress.setValue(battery_level)
        self.battery_progress.setVisible(True)

    def init_ui(self) -> None:
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 主要的水平布局
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)
        
        # 左侧：设备发现和连接
        self.create_device_discovery_group()
        main_layout.addWidget(self.device_discovery_group)
        
        # 右侧：设备参数控制
        self.create_device_control_group()
        main_layout.addWidget(self.device_control_group)
        
        # 设置左右布局比例
        main_layout.setStretch(0, 1)  # 设备发现组
        main_layout.setStretch(1, 2)  # 设备控制组
        
        layout.addLayout(main_layout)
        self.setLayout(layout)

    def create_device_discovery_group(self) -> None:
        """创建设备发现组"""
        self.device_discovery_group = QGroupBox(translate("bluetooth.device_discovery"))
        layout = QVBoxLayout()
        
        # 设备列表
        self.device_list = QListWidget()
        self.device_list.setMaximumHeight(150)
        self.device_list.itemClicked.connect(self.on_device_selected)
        layout.addWidget(self.device_list)
        
        # 按钮布局
        button_layout = QVBoxLayout()
        button_layout.setSpacing(8)
        
        # 扫描按钮
        self.scan_button = QPushButton(translate("bluetooth.scan_devices"))
        self.scan_button.setMinimumHeight(30)
        self.scan_button.clicked.connect(self.on_scan_clicked)
        button_layout.addWidget(self.scan_button)
        
        # 连接操作按钮组
        connection_layout = QHBoxLayout()
        connection_layout.setSpacing(8)
        
        self.connect_button = QPushButton(translate("bluetooth.connect_device"))
        self.connect_button.setMinimumHeight(30)
        self.connect_button.setEnabled(False)
        self.connect_button.clicked.connect(self.on_connect_clicked)
        connection_layout.addWidget(self.connect_button)
        
        self.disconnect_button = QPushButton(translate("bluetooth.disconnect_device"))
        self.disconnect_button.setMinimumHeight(30)
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.clicked.connect(self.on_disconnect_clicked)
        connection_layout.addWidget(self.disconnect_button)
        
        button_layout.addLayout(connection_layout)
        layout.addLayout(button_layout)
        
        # 状态显示
        status_group = self.create_status_display()
        layout.addWidget(status_group)
        
        self.device_discovery_group.setLayout(layout)
        self.device_discovery_group.setMinimumWidth(400)

    def create_status_display(self) -> QGroupBox:
        """创建状态显示区域"""
        status_group = QGroupBox(translate("bluetooth.connection_status"))
        layout = QFormLayout()
        layout.setSpacing(8)
        
        # 连接状态
        self.connection_status_label = QLabel(translate("bluetooth.disconnected"))
        layout.addRow(translate("bluetooth.status") + ":", self.connection_status_label)
        
        # 设备信息
        self.device_info_label = QLabel(translate("bluetooth.no_device"))
        self.device_info_label.setWordWrap(True)
        layout.addRow(translate("bluetooth.device") + ":", self.device_info_label)
        
        # 电量显示
        battery_widget = QWidget()
        battery_layout = QHBoxLayout(battery_widget)
        battery_layout.setContentsMargins(0, 0, 0, 0)
        battery_layout.setSpacing(8)
        
        self.battery_label = QLabel("--")
        battery_layout.addWidget(self.battery_label)
        
        self.battery_progress = QProgressBar()
        self.battery_progress.setMaximum(100)
        self.battery_progress.setVisible(False)
        self.battery_progress.setFixedHeight(20)
        battery_layout.addWidget(self.battery_progress)
        
        layout.addRow(translate("bluetooth.battery") + ":", battery_widget)
        
        status_group.setLayout(layout)
        return status_group

    def create_device_control_group(self) -> None:
        """创建设备控制组"""
        self.device_control_group = QGroupBox(translate("bluetooth.device_control"))
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        
        # 参数分组容器
        params_container = self.create_parameter_groups()
        layout.addWidget(params_container)
        
        self.device_control_group.setLayout(layout)

    def create_parameter_groups(self) -> QWidget:
        """创建参数分组区域"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        
        # 强度上限分组
        strength_limits_group = QGroupBox(translate("bluetooth.strength_limits"))
        self.create_strength_limits_group(strength_limits_group)
        layout.addWidget(strength_limits_group)
        
        # 频率平衡分组  
        freq_balance_group = QGroupBox(translate("bluetooth.frequency_balance"))
        self.create_freq_balance_group(freq_balance_group)
        layout.addWidget(freq_balance_group)
        
        # 强度平衡分组
        strength_balance_group = QGroupBox(translate("bluetooth.strength_balance"))
        self.create_strength_balance_group(strength_balance_group)
        layout.addWidget(strength_balance_group)
        
        # 添加弹性空间，将按钮推到底部
        layout.addStretch()
        
        # 在按钮上方添加分隔空间
        layout.addSpacing(20)
        
        # 应用按钮 - 最大化并放在底部
        self.apply_params_button = QPushButton(translate("bluetooth.apply_parameters"))
        self.apply_params_button.setStyleSheet("""
            QPushButton:enabled {
                background-color: green;
                color: white;
            }
            QPushButton:disabled {
                background-color: lightgray;
                color: gray;
            }
        """)
        self.apply_params_button.setEnabled(False)
        self.apply_params_button.clicked.connect(self.on_apply_params_clicked)
        layout.addWidget(self.apply_params_button)
        return container

    def create_strength_limits_group(self, group: QGroupBox) -> None:
        """创建强度上限分组"""
        layout = QFormLayout()
        layout.setSpacing(15)
        
        # A通道
        self.strength_limit_a_slider = QSlider(Qt.Orientation.Horizontal)
        self.strength_limit_a_slider.setRange(0, 200)
        self.strength_limit_a_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.strength_limit_a_slider.setTickInterval(20)
        self.strength_limit_a_label = QLabel()
        self.strength_limit_a_label.setMinimumWidth(50)
        self.strength_limit_a_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.strength_limit_a_slider.valueChanged.connect(self._update_strength_limit_a_label)
        
        a_layout = QHBoxLayout()
        a_layout.addWidget(self.strength_limit_a_slider)
        a_layout.addWidget(self.strength_limit_a_label)
        layout.addRow(translate("pulse_editor.channel_a") + ":", a_layout)
        
        # B通道
        self.strength_limit_b_slider = QSlider(Qt.Orientation.Horizontal)
        self.strength_limit_b_slider.setRange(0, 200)
        self.strength_limit_b_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.strength_limit_b_slider.setTickInterval(20)
        self.strength_limit_b_label = QLabel()
        self.strength_limit_b_label.setMinimumWidth(50)
        self.strength_limit_b_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.strength_limit_b_slider.valueChanged.connect(self._update_strength_limit_b_label)
        
        b_layout = QHBoxLayout()
        b_layout.addWidget(self.strength_limit_b_slider)
        b_layout.addWidget(self.strength_limit_b_label)
        layout.addRow(translate("pulse_editor.channel_b") + ":", b_layout)
        
        group.setLayout(layout)

    def create_freq_balance_group(self, group: QGroupBox) -> None:
        """创建频率平衡分组"""
        layout = QFormLayout()
        layout.setSpacing(15)
        
        # A通道
        self.freq_balance_a_slider = QSlider(Qt.Orientation.Horizontal)
        self.freq_balance_a_slider.setRange(0, 255)
        self.freq_balance_a_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.freq_balance_a_slider.setTickInterval(25)
        self.freq_balance_a_label = QLabel()
        self.freq_balance_a_label.setMinimumWidth(50)
        self.freq_balance_a_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.freq_balance_a_slider.valueChanged.connect(self._update_freq_balance_a_label)
        
        freq_a_layout = QHBoxLayout()
        freq_a_layout.addWidget(self.freq_balance_a_slider)
        freq_a_layout.addWidget(self.freq_balance_a_label)
        layout.addRow(translate("pulse_editor.channel_a") + ":", freq_a_layout)
        
        # B通道
        self.freq_balance_b_slider = QSlider(Qt.Orientation.Horizontal)
        self.freq_balance_b_slider.setRange(0, 255)
        self.freq_balance_b_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.freq_balance_b_slider.setTickInterval(25)
        self.freq_balance_b_label = QLabel()
        self.freq_balance_b_label.setMinimumWidth(50)
        self.freq_balance_b_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.freq_balance_b_slider.valueChanged.connect(self._update_freq_balance_b_label)
        
        freq_b_layout = QHBoxLayout()
        freq_b_layout.addWidget(self.freq_balance_b_slider)
        freq_b_layout.addWidget(self.freq_balance_b_label)
        layout.addRow(translate("pulse_editor.channel_b") + ":", freq_b_layout)
        
        group.setLayout(layout)

    def create_strength_balance_group(self, group: QGroupBox) -> None:
        """创建强度平衡分组"""
        layout = QFormLayout()
        layout.setSpacing(15)
        
        # A通道
        self.strength_balance_a_slider = QSlider(Qt.Orientation.Horizontal)
        self.strength_balance_a_slider.setRange(0, 255)
        self.strength_balance_a_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.strength_balance_a_slider.setTickInterval(25)
        self.strength_balance_a_label = QLabel()
        self.strength_balance_a_label.setMinimumWidth(50)
        self.strength_balance_a_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.strength_balance_a_slider.valueChanged.connect(self._update_strength_balance_a_label)
        
        str_a_layout = QHBoxLayout()
        str_a_layout.addWidget(self.strength_balance_a_slider)
        str_a_layout.addWidget(self.strength_balance_a_label)
        layout.addRow(translate("pulse_editor.channel_a") + ":", str_a_layout)
        
        # B通道
        self.strength_balance_b_slider = QSlider(Qt.Orientation.Horizontal)
        self.strength_balance_b_slider.setRange(0, 255)
        self.strength_balance_b_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.strength_balance_b_slider.setTickInterval(25)
        self.strength_balance_b_label = QLabel()
        self.strength_balance_b_label.setMinimumWidth(50)
        self.strength_balance_b_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.strength_balance_b_slider.valueChanged.connect(self._update_strength_balance_b_label)
        
        str_b_layout = QHBoxLayout()
        str_b_layout.addWidget(self.strength_balance_b_slider)
        str_b_layout.addWidget(self.strength_balance_b_label)
        layout.addRow(translate("pulse_editor.channel_b") + ":", str_b_layout)
        
        group.setLayout(layout)

    def setup_tooltips(self) -> None:
        """设置工具提示"""
        self.scan_button.setToolTip(translate("bluetooth.scan_tooltip"))
        self.connect_button.setToolTip(translate("bluetooth.connect_tooltip"))
        self.disconnect_button.setToolTip(translate("bluetooth.disconnect_tooltip"))
        self.apply_params_button.setToolTip(translate("bluetooth.apply_params_tooltip"))
        
        self.strength_limit_a_slider.setToolTip(translate("bluetooth.strength_limit_a_tooltip"))
        self.strength_limit_b_slider.setToolTip(translate("bluetooth.strength_limit_b_tooltip"))
        self.freq_balance_a_slider.setToolTip(translate("bluetooth.freq_balance_a_tooltip"))
        self.freq_balance_b_slider.setToolTip(translate("bluetooth.freq_balance_b_tooltip"))
        self.strength_balance_a_slider.setToolTip(translate("bluetooth.strength_balance_a_tooltip"))
        self.strength_balance_b_slider.setToolTip(translate("bluetooth.strength_balance_b_tooltip"))
        
        self.device_list.setToolTip(translate("bluetooth.device_list_tooltip"))

    def load_settings(self) -> None:
        """加载设置"""
        # 加载滑块值
        bluetooth_settings = self.settings.get('connection', {}).get('bluetooth', {})

        self.strength_limit_a_slider.setValue(bluetooth_settings.get('strength_limit_a', 200))
        self.strength_limit_b_slider.setValue(bluetooth_settings.get('strength_limit_b', 200))
        self.freq_balance_a_slider.setValue(bluetooth_settings.get('freq_balance_a', 160))
        self.freq_balance_b_slider.setValue(bluetooth_settings.get('freq_balance_b', 160))
        self.strength_balance_a_slider.setValue(bluetooth_settings.get('strength_balance_a', 0))
        self.strength_balance_b_slider.setValue(bluetooth_settings.get('strength_balance_b', 0))

    def save_settings(self, osc_port: int, language: str) -> None:
        """保存设置"""
        # 保存蓝牙参数
        self.connection_manager.save_settings(self.get_device_params())
        
        # 保存全局设置
        self.settings['osc_port'] = osc_port
        self.settings['language'] = language
        save_settings(self.settings)

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.connection_manager.is_connected()

    def set_device_control_enabled(self, enabled: bool) -> None:
        """设置设备控制组启用状态
        
        Args:
            enabled: 是否启用设备控制组
        """
        # 强度上限滑块
        self.strength_limit_a_slider.setEnabled(enabled)
        self.strength_limit_b_slider.setEnabled(enabled)
        
        # 频率平衡滑块
        self.freq_balance_a_slider.setEnabled(enabled)
        self.freq_balance_b_slider.setEnabled(enabled)
        
        # 强度平衡滑块
        self.strength_balance_a_slider.setEnabled(enabled)
        self.strength_balance_b_slider.setEnabled(enabled)
        
        # 应用参数按钮
        self.apply_params_button.setEnabled(enabled)

    def update_ui_texts(self) -> None:
        """更新UI文本"""
        self.device_discovery_group.setTitle(translate("bluetooth.device_discovery"))
        self.device_control_group.setTitle(translate("bluetooth.device_control"))
        
        self.scan_button.setText(translate("bluetooth.scan_devices"))
        self.connect_button.setText(translate("bluetooth.connect_device"))
        self.disconnect_button.setText(translate("bluetooth.disconnect_device"))
        self.apply_params_button.setText(translate("bluetooth.apply_parameters"))
        
        if not self.is_connected():
            self.connection_status_label.setText(translate("bluetooth.disconnected"))
            self.device_info_label.setText(translate("bluetooth.no_device"))

    def update_connection_state(self, state: ConnectionState, message: str = "") -> None:
        """更新连接状态"""
        if state == ConnectionState.DISCONNECTED:
            self._update_disconnected_state()
        elif state == ConnectionState.CONNECTING:
            self._update_connecting_state()
        elif state == ConnectionState.WAITING:
            self._update_waiting_state()
        elif state == ConnectionState.CONNECTED:
            self._update_connected_state()
        elif state == ConnectionState.FAILED:
            self._update_failed_state(message)
        elif state == ConnectionState.ERROR:
            self._update_error_state(message)

    def _update_status_labels(self, status_key: str, device_info: str = "", battery_visible: bool = True) -> None:
        """更新状态标签"""
        self.connection_status_label.setText(translate(status_key))
        if device_info:
            self.device_info_label.setText(device_info)
        else:
            self.device_info_label.setText(translate("bluetooth.no_device"))
        
        if not battery_visible:
            self.battery_label.setText("--")
            self.battery_progress.setVisible(False)

    def _update_button_states(self, scan_enabled: bool, connect_enabled: bool, 
                            disconnect_enabled: bool, apply_enabled: bool) -> None:
        """更新按钮状态"""
        self.scan_button.setEnabled(scan_enabled)
        self.disconnect_button.setEnabled(disconnect_enabled)
        self.apply_params_button.setEnabled(apply_enabled)
        
        # 连接按钮的状态需要特殊处理
        if connect_enabled and self.connection_manager.get_selected_device():
            self.connect_button.setEnabled(True)
        else:
            self.connect_button.setEnabled(False)

    def _update_disconnected_state(self) -> None:
        """更新断开连接状态"""
        self._update_status_labels("bluetooth.disconnected", battery_visible=False)
        self._update_button_states(scan_enabled=True, connect_enabled=True, 
                                 disconnect_enabled=False, apply_enabled=False)
        self.set_device_control_enabled(False)

    def _update_connecting_state(self) -> None:
        """更新连接中状态"""
        self._update_status_labels("bluetooth.connecting")
        self._update_button_states(scan_enabled=False, connect_enabled=False, 
                                 disconnect_enabled=True, apply_enabled=False)
        self.set_device_control_enabled(False)

    def _update_waiting_state(self) -> None:
        """更新等待状态"""
        self._update_status_labels("bluetooth.waiting")
        self._update_button_states(scan_enabled=False, connect_enabled=False, 
                                 disconnect_enabled=True, apply_enabled=False)
        self.set_device_control_enabled(False)

    def _update_connected_state(self) -> None:
        """更新已连接状态"""
        # 获取连接的设备信息
        device_info = ""
        connected_device = self.connection_manager.get_connected_device()
        if connected_device:
            device_info = f"{connected_device['name']} ({connected_device['address']})"
        
        self._update_status_labels("bluetooth.connected", device_info)
        self._update_button_states(scan_enabled=False, connect_enabled=False, 
                                 disconnect_enabled=True, apply_enabled=True)
        self.set_device_control_enabled(True)

    def _update_failed_state(self, message: str = "") -> None:
        """更新连接失败状态"""
        status_text = message or translate("bluetooth.connection_failed")
        self.connection_status_label.setText(status_text)
        self._update_status_labels("bluetooth.connection_failed", battery_visible=False)
        self._update_button_states(scan_enabled=True, connect_enabled=True, 
                                 disconnect_enabled=False, apply_enabled=False)
        self.set_device_control_enabled(False)

    def _update_error_state(self, message: str = "") -> None:
        """更新错误状态"""
        status_text = message or translate("common.error")
        self.connection_status_label.setText(status_text)
        self.device_info_label.setText(translate("bluetooth.no_device"))
        self.battery_label.setText("--")
        self.battery_progress.setVisible(False)
        self._update_button_states(scan_enabled=True, connect_enabled=True, 
                                 disconnect_enabled=False, apply_enabled=False)
        self.set_device_control_enabled(False)

    def get_device_params(self) -> WebsocketDeviceParamsDict:
        """获取设备参数"""
        return {
            "strength_limit_a": self.strength_limit_a_slider.value(),
            "strength_limit_b": self.strength_limit_b_slider.value(),
            "freq_balance_a": self.freq_balance_a_slider.value(),
            "freq_balance_b": self.freq_balance_b_slider.value(),
            "strength_balance_a": self.strength_balance_a_slider.value(),
            "strength_balance_b": self.strength_balance_b_slider.value(),
        }

    # =================== 事件处理 ===================

    def on_scan_clicked(self) -> None:
        """扫描按钮点击"""
        self.scan_button.setEnabled(False)
        self.scan_button.setText(translate("bluetooth.scanning"))
        
        asyncio.create_task(self._scan_devices())

    async def _scan_devices(self) -> None:
        """异步扫描设备"""
        try:
            devices = await self.connection_manager.discover_devices(5.0)
            
            # 更新设备列表
            self.device_list.clear()
            for device in devices:
                item = QListWidgetItem(f"{device['name']} ({device['address']}) - RSSI: {device['rssi']}")
                item.setData(Qt.ItemDataRole.UserRole, device)
                self.device_list.addItem(item)
                
            logger.info(f"发现 {len(devices)} 个蓝牙设备")
            
        except Exception as e:
            logger.error(f"设备扫描失败: {e}")
        finally:
            # 恢复按钮状态
            self.scan_button.setEnabled(True)
            self.scan_button.setText(translate("bluetooth.scan_devices"))

    def on_device_selected(self, item: QListWidgetItem) -> None:
        """设备选择"""
        device = item.data(Qt.ItemDataRole.UserRole)
        self.connection_manager.set_selected_device(device)
        self.connect_button.setEnabled(True)

    def on_connect_clicked(self) -> None:
        """连接按钮点击"""
        selected_device = self.connection_manager.get_selected_device()
        if not selected_device:
            QMessageBox.warning(self, translate("common.error"), translate("bluetooth.no_device_selected"))
            return
            
        osc_port = self.settings.get('osc_port', 9001)
        device_params = self.get_device_params()
        self.connection_manager.start_connection(selected_device, osc_port, device_params)

    def on_disconnect_clicked(self) -> None:
        """断开连接按钮点击"""
        self.connection_manager.stop_connection()

    def on_apply_params_clicked(self) -> None:
        """应用参数按钮点击"""
        if not self.is_connected():
            QMessageBox.warning(self, translate("common.error"), translate("bluetooth.device_not_connected"))
            return
            
        try:
            # 通过管理器应用参数
            success = self.connection_manager.apply_device_params(self.get_device_params())
            
            if success:
                QMessageBox.information(self, translate("common.success"), "设备参数已应用")
            else:
                QMessageBox.warning(self, translate("common.error"), "应用参数失败")
            
        except Exception as e:
            QMessageBox.warning(self, translate("common.error"), f"应用参数失败: {e}")

    # =================== 标签更新方法 ===================

    def _update_strength_limit_a_label(self, value: int) -> None:
        """更新强度上限A标签"""
        self.strength_limit_a_label.setText(str(value))

    def _update_strength_limit_b_label(self, value: int) -> None:
        """更新强度上限B标签"""
        self.strength_limit_b_label.setText(str(value))

    def _update_freq_balance_a_label(self, value: int) -> None:
        """更新频率平衡A标签"""
        self.freq_balance_a_label.setText(str(value))

    def _update_freq_balance_b_label(self, value: int) -> None:
        """更新频率平衡B标签"""
        self.freq_balance_b_label.setText(str(value))

    def _update_strength_balance_a_label(self, value: int) -> None:
        """更新强度平衡A标签"""
        self.strength_balance_a_label.setText(str(value))

    def _update_strength_balance_b_label(self, value: int) -> None:
        """更新强度平衡B标签"""
        self.strength_balance_b_label.setText(str(value))
