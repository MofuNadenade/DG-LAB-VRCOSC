import logging
import asyncio
from typing import List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QLabel, QWidget,
    QPushButton, QListWidget, QListWidgetItem, QProgressBar,
    QSlider, QMessageBox
)

from services.dglab_bluetooth_service import DGLabDevice
from gui.connection.bluetooth.bluetooth_manager import BluetoothConnectionManager
from gui.ui_interface import UIInterface
from i18n import translate
from models import ConnectionState, SettingsDict
from config import save_settings

logger = logging.getLogger(__name__)


class BluetoothConnectionWidget(QWidget):
    """蓝牙连接配置组件（仅UI层）"""
    
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.settings: SettingsDict = ui_interface.settings
        
        # 蓝牙连接管理器 - 处理所有业务逻辑
        self.connection_manager = BluetoothConnectionManager(ui_interface)
        
        # UI组件类型注解
        self.device_discovery_group: QGroupBox
        self.device_control_group: QGroupBox
        self.device_list: QListWidget
        self.scan_button: QPushButton
        self.connect_button: QPushButton
        self.disconnect_button: QPushButton
        self.connection_status_label: QLabel
        self.battery_label: QLabel
        self.device_info_label: QLabel
        
        # 设备参数控制
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
        
        # 状态显示组件类型注解
        self.battery_progress: QProgressBar
        
        self.init_ui()
        self.load_settings()
        self.setup_manager_connections()
        self.setup_tooltips()
        
        # 定时器用于更新连接状态
        self.status_update_timer = QTimer()
        self.status_update_timer.timeout.connect(self.update_connection_status)
        self.status_update_timer.start(1000)  # 每秒更新
    
    def init_ui(self) -> None:
        """初始化蓝牙连接设置UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 创建主要的水平布局
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)
        
        # =================== 左侧：设备发现和连接 ===================
        self.device_discovery_group = QGroupBox(translate("bluetooth.device_discovery"))
        discovery_layout = QVBoxLayout()
        
        # 设备列表
        self.device_list = QListWidget()
        self.device_list.setMaximumHeight(150)
        self.device_list.itemClicked.connect(self.on_device_selected)
        discovery_layout.addWidget(self.device_list)
        
        
        # 按钮布局 - 改为垂直排列
        button_layout = QVBoxLayout()
        button_layout.setSpacing(8)
        
        # 扫描按钮 - 主要操作
        self.scan_button = self._create_action_button(translate("bluetooth.scan_devices"))
        self.scan_button.clicked.connect(self.on_scan_button_clicked)
        button_layout.addWidget(self.scan_button)
        
        # 连接操作按钮组
        connection_buttons_layout = QHBoxLayout()
        connection_buttons_layout.setSpacing(8)
        
        # 连接按钮 - 成功操作
        self.connect_button = self._create_action_button(translate("bluetooth.connect_device"))
        self.connect_button.setEnabled(False)
        self.connect_button.clicked.connect(self.on_connect_button_clicked)
        connection_buttons_layout.addWidget(self.connect_button)
        
        # 断开按钮 - 危险操作
        self.disconnect_button = self._create_action_button(translate("bluetooth.disconnect_device"))
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.clicked.connect(self.on_disconnect_button_clicked)
        connection_buttons_layout.addWidget(self.disconnect_button)
        
        button_layout.addLayout(connection_buttons_layout)
        discovery_layout.addLayout(button_layout)
        
        # 连接状态显示 - 使用增强的状态卡片
        status_card = self._create_status_display()
        discovery_layout.addWidget(status_card)
        
        self.device_discovery_group.setLayout(discovery_layout)
        self.device_discovery_group.setMinimumWidth(400)
        main_layout.addWidget(self.device_discovery_group)
        
        # =================== 右侧：设备参数控制 ===================
        self.device_control_group = QGroupBox(translate("bluetooth.device_control"))
        control_layout = QVBoxLayout()
        
        # 创建参数分组区域
        params_container = self._create_parameter_groups()
        control_layout.addWidget(params_container)
        
        control_layout.addStretch()
        self.device_control_group.setLayout(control_layout)
        main_layout.addWidget(self.device_control_group)
        
        # 设置左右布局比例 - 给右侧参数控制更多空间
        main_layout.setStretch(0, 1)  # 设备发现组 (33%)
        main_layout.setStretch(1, 2)  # 设备控制组 (67%)
        
        layout.addLayout(main_layout)
        layout.addStretch()
        self.setLayout(layout)
    
    def _create_action_button(self, text: str) -> QPushButton:
        """创建简化样式的操作按钮"""
        button = QPushButton(text)
        button.setMinimumHeight(30)
        return button
    
    def _create_simple_slider(self, min_val: int, max_val: int, default_val: int) -> QSlider:
        """创建简化样式的滑块控件"""
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default_val)
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        slider.setTickInterval((max_val - min_val) // 10)
        return slider
    
    def _create_parameter_groups(self) -> QWidget:
        """创建参数分组区域"""
        params_container = QWidget()
        params_main_layout = QVBoxLayout(params_container)
        params_main_layout.setSpacing(20)
        
        # === 强度上限分组 ===
        strength_limits_group = QGroupBox("Strength Limits")
        
        strength_limits_layout = QFormLayout()
        strength_limits_layout.setSpacing(15)
        
        # 通道A强度上限
        a_layout = QHBoxLayout()
        self.strength_limit_a_slider = self._create_simple_slider(0, 200, 200)
        self.strength_limit_a_label = QLabel("200")
        self.strength_limit_a_label.setMinimumWidth(50)
        self.strength_limit_a_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.strength_limit_a_slider.valueChanged.connect(
            lambda v: self.strength_limit_a_label.setText(str(v))  # type: ignore
        )
        a_layout.addWidget(self.strength_limit_a_slider)
        a_layout.addWidget(self.strength_limit_a_label)
        strength_limits_layout.addRow("Channel A:", a_layout)
        
        # 通道B强度上限
        b_layout = QHBoxLayout()
        self.strength_limit_b_slider = self._create_simple_slider(0, 200, 200)
        self.strength_limit_b_label = QLabel("200")
        self.strength_limit_b_label.setMinimumWidth(50)
        self.strength_limit_b_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.strength_limit_b_slider.valueChanged.connect(
            lambda v: self.strength_limit_b_label.setText(str(v))  # type: ignore
        )
        b_layout.addWidget(self.strength_limit_b_slider)
        b_layout.addWidget(self.strength_limit_b_label)
        strength_limits_layout.addRow("Channel B:", b_layout)
        
        strength_limits_group.setLayout(strength_limits_layout)
        params_main_layout.addWidget(strength_limits_group)
        
        # === 频率平衡分组 ===
        freq_balance_group = QGroupBox("Frequency Balance")
        
        freq_balance_layout = QFormLayout()
        freq_balance_layout.setSpacing(15)
        
        # 通道A频率平衡
        freq_a_layout = QHBoxLayout()
        self.freq_balance_a_slider = self._create_simple_slider(0, 255, 160)
        self.freq_balance_a_label = QLabel("160")
        self.freq_balance_a_label.setMinimumWidth(50)
        self.freq_balance_a_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.freq_balance_a_slider.valueChanged.connect(
            lambda v: self.freq_balance_a_label.setText(str(v))  # type: ignore
        )
        freq_a_layout.addWidget(self.freq_balance_a_slider)
        freq_a_layout.addWidget(self.freq_balance_a_label)
        freq_balance_layout.addRow("Channel A:", freq_a_layout)
        
        # 通道B频率平衡
        freq_b_layout = QHBoxLayout()
        self.freq_balance_b_slider = self._create_simple_slider(0, 255, 160)
        self.freq_balance_b_label = QLabel("160")
        self.freq_balance_b_label.setMinimumWidth(50)
        self.freq_balance_b_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.freq_balance_b_slider.valueChanged.connect(
            lambda v: self.freq_balance_b_label.setText(str(v))  # type: ignore
        )
        freq_b_layout.addWidget(self.freq_balance_b_slider)
        freq_b_layout.addWidget(self.freq_balance_b_label)
        freq_balance_layout.addRow("Channel B:", freq_b_layout)
        
        freq_balance_group.setLayout(freq_balance_layout)
        params_main_layout.addWidget(freq_balance_group)
        
        # === 强度平衡分组 ===
        strength_balance_group = QGroupBox("Strength Balance")
        
        strength_balance_layout = QFormLayout()
        strength_balance_layout.setSpacing(15)
        
        # 通道A强度平衡
        str_a_layout = QHBoxLayout()
        self.strength_balance_a_slider = self._create_simple_slider(0, 255, 0)
        self.strength_balance_a_label = QLabel("0")
        self.strength_balance_a_label.setMinimumWidth(50)
        self.strength_balance_a_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.strength_balance_a_slider.valueChanged.connect(
            lambda v: self.strength_balance_a_label.setText(str(v))  # type: ignore
        )
        str_a_layout.addWidget(self.strength_balance_a_slider)
        str_a_layout.addWidget(self.strength_balance_a_label)
        strength_balance_layout.addRow("Channel A:", str_a_layout)
        
        # 通道B强度平衡
        str_b_layout = QHBoxLayout()
        self.strength_balance_b_slider = self._create_simple_slider(0, 255, 0)
        self.strength_balance_b_label = QLabel("0")
        self.strength_balance_b_label.setMinimumWidth(50)
        self.strength_balance_b_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.strength_balance_b_slider.valueChanged.connect(
            lambda v: self.strength_balance_b_label.setText(str(v))  # type: ignore
        )
        str_b_layout.addWidget(self.strength_balance_b_slider)
        str_b_layout.addWidget(self.strength_balance_b_label)
        strength_balance_layout.addRow("Channel B:", str_b_layout)
        
        strength_balance_group.setLayout(strength_balance_layout)
        params_main_layout.addWidget(strength_balance_group)
        
        # === 应用按钮区域 ===
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 20, 0, 0)
        
        self.apply_params_button = QPushButton(translate("bluetooth.apply_parameters"))
        self.apply_params_button.setEnabled(False)
        self.apply_params_button.clicked.connect(self.on_apply_params_clicked)
        
        action_layout.addStretch()
        action_layout.addWidget(self.apply_params_button)
        action_layout.addStretch()
        
        params_main_layout.addLayout(action_layout)
        
        return params_container
    
    def _create_status_display(self) -> QWidget:
        """创建简化的状态显示区域"""
        status_container = QGroupBox(translate("bluetooth.connection_status"))
        
        status_layout = QFormLayout(status_container)
        status_layout.setSpacing(8)
        
        # 连接状态
        self.connection_status_label = QLabel(translate("bluetooth.disconnected"))
        status_layout.addRow("Status:", self.connection_status_label)
        
        # 设备信息
        self.device_info_label = QLabel(translate("bluetooth.no_device"))
        self.device_info_label.setWordWrap(True)
        status_layout.addRow("Device:", self.device_info_label)
        
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
        
        status_layout.addRow("Battery:", battery_widget)
        
        return status_container
    
    def setup_tooltips(self) -> None:
        """设置工具提示说明"""
        # 连接相关按钮
        self.scan_button.setToolTip("Scan for nearby Bluetooth devices")
        self.connect_button.setToolTip("Connect to the selected device")
        self.disconnect_button.setToolTip("Disconnect from the current device")
        
        # 参数相关按钮
        self.apply_params_button.setToolTip("Apply current parameter settings to the connected device")
        
        # 参数滑块提示
        self.strength_limit_a_slider.setToolTip("Set maximum strength limit for Channel A (Range: 0-200)")
        self.strength_limit_b_slider.setToolTip("Set maximum strength limit for Channel B (Range: 0-200)")
        self.freq_balance_a_slider.setToolTip("Set frequency balance for Channel A (Range: 0-255, Default: 160)")
        self.freq_balance_b_slider.setToolTip("Set frequency balance for Channel B (Range: 0-255, Default: 160)")
        self.strength_balance_a_slider.setToolTip("Set strength balance for Channel A (Range: 0-255, Default: 0)")
        self.strength_balance_b_slider.setToolTip("Set strength balance for Channel B (Range: 0-255, Default: 0)")
        
        # 设备列表提示
        self.device_list.setToolTip("List of discovered Bluetooth devices. Click to select, double-click to connect.")
    
    def setup_manager_connections(self) -> None:
        """设置管理器信号连接"""
        # 设备发现相关信号
        self.connection_manager.signals.discovery_started.connect(self.on_discovery_started)
        self.connection_manager.signals.discovery_finished.connect(self.on_discovery_finished)
        self.connection_manager.signals.devices_found.connect(self.on_devices_found)
        self.connection_manager.signals.discovery_error.connect(self.on_discovery_error)
        
        # 连接状态相关信号
        self.connection_manager.signals.connection_state_changed.connect(self.on_connection_state_changed)
        self.connection_manager.signals.device_connected.connect(self.on_device_connected)
        self.connection_manager.signals.device_disconnected.connect(self.on_device_disconnected)
        
        # 设备状态相关信号
        self.connection_manager.signals.battery_level_changed.connect(self.on_battery_level_changed)
    
    def load_settings(self) -> None:
        """加载蓝牙设置到UI元素"""
        default_settings = self.connection_manager.load_default_settings()
        
        # 加载设备参数
        self.strength_limit_a_slider.setValue(default_settings['strength_limit_a'])
        self.strength_limit_b_slider.setValue(default_settings['strength_limit_b'])
        self.freq_balance_a_slider.setValue(default_settings['freq_balance_a'])
        self.freq_balance_b_slider.setValue(default_settings['freq_balance_b'])
        self.strength_balance_a_slider.setValue(default_settings['strength_balance_a'])
        self.strength_balance_b_slider.setValue(default_settings['strength_balance_b'])
        
        # 更新显示标签
        self.strength_limit_a_label.setText(str(default_settings['strength_limit_a']))
        self.strength_limit_b_label.setText(str(default_settings['strength_limit_b']))
        self.freq_balance_a_label.setText(str(default_settings['freq_balance_a']))
        self.freq_balance_b_label.setText(str(default_settings['freq_balance_b']))
        self.strength_balance_a_label.setText(str(default_settings['strength_balance_a']))
        self.strength_balance_b_label.setText(str(default_settings['strength_balance_b']))
    
    def save_settings(self, osc_port: int, language: str) -> None:
        """保存蓝牙设置"""
        # 保存蓝牙参数到管理器
        self.connection_manager.save_settings(
            strength_limit_a=self.strength_limit_a_slider.value(),
            strength_limit_b=self.strength_limit_b_slider.value(),
            freq_balance_a=self.freq_balance_a_slider.value(),
            freq_balance_b=self.freq_balance_b_slider.value(),
            strength_balance_a=self.strength_balance_a_slider.value(),
            strength_balance_b=self.strength_balance_b_slider.value()
        )
        
        # 保存全局设置
        self.settings['osc_port'] = osc_port
        self.settings['language'] = language
        save_settings(self.settings)
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connection_manager.is_connected()
    
    def update_connection_state(self, state: ConnectionState, message: str = "") -> None:
        """更新连接状态"""
        # 根据状态更新UI
        if state == ConnectionState.DISCONNECTED:
            self.connection_status_label.setText(translate("bluetooth.disconnected"))
            self.scan_button.setEnabled(True)
            self.device_list.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            self.apply_params_button.setEnabled(False)
        elif state == ConnectionState.CONNECTING:
            self.connection_status_label.setText(translate("bluetooth.connecting"))
            self.scan_button.setEnabled(False)
            self.device_list.setEnabled(False)
            self.connect_button.setEnabled(False)
        elif state == ConnectionState.CONNECTED:
            self.connection_status_label.setText(translate("bluetooth.connected"))
            self.device_list.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.apply_params_button.setEnabled(True)
        elif state in [ConnectionState.FAILED, ConnectionState.ERROR]:
            self.connection_status_label.setText(message or translate("bluetooth.connection_failed"))
            self.scan_button.setEnabled(True)
            self.device_list.setEnabled(True)
            selected_device = self.connection_manager.selected_device
            if selected_device:
                self.connect_button.setEnabled(True)
        
        # 记录错误日志
        if state in [ConnectionState.FAILED, ConnectionState.ERROR] and message:
            self.ui_interface.log_error(message)
    
    
    def update_ui_texts(self) -> None:
        """更新UI上的文本为当前语言"""
        # 更新组标题
        self.device_discovery_group.setTitle(translate("bluetooth.device_discovery"))
        self.device_control_group.setTitle(translate("bluetooth.device_control"))
        
        # 更新按钮文本
        self.scan_button.setText(translate("bluetooth.scan_devices"))
        self.connect_button.setText(translate("bluetooth.connect_device"))
        self.disconnect_button.setText(translate("bluetooth.disconnect_device"))
        self.apply_params_button.setText(translate("bluetooth.apply_parameters"))
        
        # 更新状态文本
        if not self.is_connected():
            self.connection_status_label.setText(translate("bluetooth.disconnected"))
            self.device_info_label.setText(translate("bluetooth.no_device"))
    
    def update_connection_status(self) -> None:
        """更新连接状态（定时调用）"""
        if self.connection_manager.is_connected():
            # 连接状态正常，无需操作
            pass
        else:
            # 连接断开，更新UI
            if self.disconnect_button.isEnabled():
                self.update_connection_state(ConnectionState.DISCONNECTED)
    
    # =================== UI事件处理方法 ===================
    
    def on_scan_button_clicked(self) -> None:
        """扫描按钮点击事件"""
        asyncio.create_task(self.connection_manager.start_device_discovery(5.0))
    
    def on_connect_button_clicked(self) -> None:
        """连接按钮点击事件"""
        # 获取选中的设备
        selected_device = self.connection_manager.selected_device
        if not selected_device:
            QMessageBox.warning(self, translate("bluetooth.error"), translate("bluetooth.no_device_selected"))
            return
            
        # 获取OSC端口
        osc_port = self.settings.get('osc_port', 9001)
        
        # 启动连接
        self.connection_manager.start_connection(selected_device, osc_port)
    
    def on_disconnect_button_clicked(self) -> None:
        """断开连接按钮点击事件"""
        self.connection_manager.stop_connection()
    
    def on_apply_params_clicked(self) -> None:
        """应用参数按钮点击事件"""
        self.apply_device_parameters()
    
    # =================== 设备发现和连接事件处理 ===================
    
    def on_discovery_started(self) -> None:
        """设备发现开始"""
        # 清空设备列表
        self.device_list.clear()
        
        
        # 禁用扫描按钮
        self.scan_button.setEnabled(False)
        self.scan_button.setText(translate("bluetooth.scanning"))
        self.connect_button.setEnabled(False)
        
        logger.info("开始蓝牙设备扫描")
    
    def on_discovery_finished(self) -> None:
        """设备发现完成"""
        
        # 恢复扫描按钮
        self.scan_button.setEnabled(True)
        self.scan_button.setText(translate("bluetooth.scan_devices"))
        
        logger.info("蓝牙设备扫描完成")
    
    def on_devices_found(self, devices: List[DGLabDevice]) -> None:
        """设备发现回调"""
        self.device_list.clear()
        
        for device in devices:
            item = QListWidgetItem(f"{device['name']} ({device['address']}) - RSSI: {device['rssi']}")
            item.setData(Qt.ItemDataRole.UserRole, device)
            self.device_list.addItem(item)
        
        logger.info(f"发现 {len(devices)} 个蓝牙设备")
    
    def on_discovery_error(self, error_message: str) -> None:
        """设备发现错误"""
        logger.error(f"设备扫描失败: {error_message}")
    
    def on_device_selected(self, item: QListWidgetItem) -> None:
        """设备选择回调"""
        device = item.data(Qt.ItemDataRole.UserRole)
        self.connection_manager.set_selected_device(device)
        self.connect_button.setEnabled(True)
    
    # =================== 管理器信号处理 ===================
    
    def on_connection_state_changed(self, state_value: str, message: str) -> None:
        """连接状态变化处理"""
        try:
            state = ConnectionState(state_value)
            self.update_connection_state(state, message)
        except ValueError:
            logger.error(f"无效的连接状态值: {state_value}")
    
    def on_device_connected(self, device: DGLabDevice) -> None:
        """设备连接成功"""
        device_text = f"{device['name']} ({device['address'][:8]}...)"
        self.device_info_label.setText(device_text)
        
        # 启用控制功能
        self.apply_params_button.setEnabled(True)
        
        # 禁用扫描和连接按钮
        self.scan_button.setEnabled(False)
        self.connect_button.setEnabled(False)
        
        logger.info("设备连接成功，UI已更新")
    
    def on_device_disconnected(self) -> None:
        """设备连接断开"""
        self.device_info_label.setText(translate("bluetooth.no_device"))
        self.battery_label.setText("--")
        
        # 禁用控制功能
        self.apply_params_button.setEnabled(False)
        
        # 启用扫描按钮
        self.scan_button.setEnabled(True)
        selected_device = self.connection_manager.selected_device
        if selected_device:
            self.connect_button.setEnabled(True)
        
        logger.info("设备连接断开，UI已重置")
    
    def on_battery_level_changed(self, battery_level: int) -> None:
        """电量变化处理"""
        self.battery_label.setText(f"{battery_level}%")
        self.battery_progress.setValue(battery_level)
        self.battery_progress.setVisible(True)
    
    # =================== 设备参数控制事件处理 ===================
    
    def apply_device_parameters(self) -> None:
        """应用设备参数"""
        if not self.connection_manager.is_connected():
            QMessageBox.warning(self, translate("common.error"), translate("bluetooth.device_not_connected"))
            return
        
        # 通过服务控制器访问蓝牙服务
        service_controller = self.connection_manager.service_controller
        if not service_controller:
            QMessageBox.warning(self, translate("common.error"), "服务控制器未初始化")
            return
            
        # 获取蓝牙设备服务并检查类型
        from services.dglab_bluetooth_service import DGLabBluetoothService
        from models import Channel
        
        bluetooth_service = service_controller.dglab_device_service
        if not isinstance(bluetooth_service, DGLabBluetoothService):
            QMessageBox.warning(self, translate("common.error"), "当前服务不支持蓝牙设备参数设置")
            return
            
        # 应用设备参数
        try:
            bluetooth_service.set_strength_limit(Channel.A, self.strength_limit_a_slider.value())
            bluetooth_service.set_strength_limit(Channel.B, self.strength_limit_b_slider.value())
            bluetooth_service.set_freq_balance(Channel.A, self.freq_balance_a_slider.value())
            bluetooth_service.set_freq_balance(Channel.B, self.freq_balance_b_slider.value())
            bluetooth_service.set_strength_balance(Channel.A, self.strength_balance_a_slider.value())
            bluetooth_service.set_strength_balance(Channel.B, self.strength_balance_b_slider.value())
            
            QMessageBox.information(self, translate("common.success"), "设备参数已应用")
        except Exception as e:
            QMessageBox.warning(self, translate("common.error"), f"应用参数失败: {e}")
    
    
    # =================== 资源清理 ===================
    
    def cleanup(self) -> None:
        """清理资源"""
        try:
            # 停止定时器
            if self.status_update_timer:
                self.status_update_timer.stop()
            
            # 清理管理器
            asyncio.create_task(self.connection_manager.cleanup())
            
            logger.info("蓝牙UI组件资源已清理")
        except Exception as e:
            logger.error(f"清理蓝牙UI组件资源失败: {e}")