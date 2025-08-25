import asyncio
import logging
from typing import Awaitable, Callable, Optional

import requests
from PySide6.QtCore import Qt, QLocale, QTimer
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
                               QComboBox, QSpinBox, QLabel, QPushButton, QLineEdit, QCheckBox, QMessageBox, QSizePolicy)

from config import get_active_ip_addresses, save_settings
from core.dglab_controller import DGLabController
from core.osc_common import OSCActionType
from i18n import translate, language_signals, LANGUAGES, get_current_language, set_language
from models import Channel, ConnectionState, OSCValue, SettingsDict
from services.chatbox_service import ChatboxService
from services.dglab_service_interface import IDGLabService
from services.dglab_websocket_service import DGLabWebSocketService
from services.osc_service import OSCService
from .ui_interface import UIInterface
from .widgets import EditableComboBox

logger = logging.getLogger(__name__)


class NetworkConfigTab(QWidget):
    def __init__(self, ui_interface: UIInterface, settings: SettingsDict) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.settings: SettingsDict = settings
        self.server_task: Optional[asyncio.Task[None]] = None

        # UI组件类型注解
        self.network_config_group: QGroupBox
        self.form_layout: QFormLayout
        self.ip_combobox: QComboBox
        self.port_spinbox: QSpinBox
        self.osc_port_spinbox: QSpinBox
        self.enable_remote_checkbox: QCheckBox
        self.remote_address_edit: QLineEdit
        self.get_public_ip_button: QPushButton
        self.remote_address_layout: QHBoxLayout
        self.connection_status_label: QLabel
        self.start_button: QPushButton
        self.language_layout: QHBoxLayout
        self.language_label: QLabel
        self.language_combo: QComboBox
        self.qrcode_label: QLabel
        self.original_qrcode_pixmap: Optional[QPixmap]  # 保存原始二维码图像

        # 保存表单标签的引用，用于语言切换时更新
        self.interface_label: QLabel
        self.websocket_port_label: QLabel
        self.osc_port_label: QLabel
        self.status_label: QLabel
        self.remote_address_label: QLabel

        # 初始化原始二维码
        self.original_qrcode_pixmap = None

        self.init_ui()
        self.load_settings()

        # 连接语言变更信号
        language_signals.language_changed.connect(self.update_ui_texts)

    @property
    def controller(self) -> Optional[DGLabController]:
        """通过UIInterface获取当前控制器"""
        return self.ui_interface.controller

    def init_ui(self) -> None:
        """初始化连接设置选项卡UI"""
        layout = QVBoxLayout()

        # 创建一个水平布局，用于放置网络配置和二维码
        network_layout = QHBoxLayout()

        # 创建网络配置组
        self.network_config_group = QGroupBox(translate("connection_tab.title"))
        self.form_layout = QFormLayout()

        # 网卡选择
        active_ips = get_active_ip_addresses()
        ip_options = [f"{interface}: {ip}" for interface, ip in active_ips.items()]

        self.ip_combobox = EditableComboBox(ip_options)
        # 强制使用英文区域设置，避免数字显示为繁体中文
        self.ip_combobox.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.interface_label = QLabel(translate("connection_tab.interface_label"))
        self.form_layout.addRow(self.interface_label, self.ip_combobox)

        # 端口选择
        self.port_spinbox = QSpinBox()
        # 强制使用英文区域设置，避免数字显示为繁体中文
        self.port_spinbox.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.port_spinbox.setRange(1024, 65535)
        self.port_spinbox.setValue(self.settings.get('port', 8080))
        self.websocket_port_label = QLabel(translate("connection_tab.websocket_port_label"))
        self.form_layout.addRow(self.websocket_port_label, self.port_spinbox)

        # OSC端口选择
        self.osc_port_spinbox = QSpinBox()
        # 强制使用英文区域设置，避免数字显示为繁体中文
        self.osc_port_spinbox.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.osc_port_spinbox.setRange(1024, 65535)
        self.osc_port_spinbox.setValue(self.settings.get('osc_port', 9000))
        self.osc_port_label = QLabel(translate("connection_tab.osc_port_label"))
        self.form_layout.addRow(self.osc_port_label, self.osc_port_spinbox)

        # 创建远程地址控制布局
        self.remote_address_layout = QHBoxLayout()

        # 创建开启异地复选框
        self.enable_remote_checkbox = QCheckBox(translate("connection_tab.enable_remote"))
        self.enable_remote_checkbox.setChecked(self.settings.get('enable_remote', False))
        self.enable_remote_checkbox.stateChanged.connect(self.on_remote_enabled_changed)

        # 远程地址输入框
        self.remote_address_edit = QLineEdit()
        # 强制使用英文区域设置，避免数字显示为繁体中文
        self.remote_address_edit.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.remote_address_edit.setText(self.settings.get('remote_address', ''))
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
        self.form_layout.addRow(self.remote_address_label, self.remote_address_layout)

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
        self.form_layout.addRow(self.status_label, self.connection_status_label)

        # 启动按钮
        self.start_button = QPushButton(translate("connection_tab.connect"))
        self.start_button.setStyleSheet("background-color: green; color: white;")
        self.start_button.clicked.connect(self.start_server_button_clicked)
        self.form_layout.addRow(self.start_button)

        # 语言选择
        self.language_layout = QHBoxLayout()
        self.language_label = QLabel(translate("main.settings.language_label"))

        language_options = list(LANGUAGES.values())
        self.language_combo = EditableComboBox(language_options)

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

        self.form_layout.addRow(self.language_layout)

        self.network_config_group.setLayout(self.form_layout)
        network_layout.addWidget(self.network_config_group)

        # 二维码显示
        self.qrcode_label = QLabel()
        # 设置QR码自适应尺寸策略
        self.qrcode_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.qrcode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qrcode_label.setMinimumSize(300, 300)  # 设置最小可显示尺寸
        network_layout.addWidget(self.qrcode_label, 1)  # stretch=1占据剩余空间

        layout.addLayout(network_layout)
        layout.addStretch()  # 添加弹性空间

        self.setLayout(layout)

    def load_settings(self) -> None:
        """Apply the loaded settings to the UI elements."""
        # 根据设置选择对应的网卡
        for i in range(self.ip_combobox.count()):
            interface_ip = self.ip_combobox.itemText(i).split(": ")
            if len(interface_ip) >= 2:
                _, ip = interface_ip[0], interface_ip[1]
                if ip == self.settings.get('ip'):
                    self.ip_combobox.setCurrentIndex(i)
                    logger.info("set to previous used network interface")
                    break

    def save_network_settings(self) -> None:
        """Save network settings to the settings.yml file."""
        selected_interface_ip = self.ip_combobox.currentText().split(": ")
        if len(selected_interface_ip) >= 2:
            interface_name, ip = selected_interface_ip[0], selected_interface_ip[1]
            self.settings['interface'] = interface_name
            self.settings['ip'] = ip

        self.settings['port'] = self.port_spinbox.value()
        self.settings['osc_port'] = self.osc_port_spinbox.value()
        self.settings['language'] = self.language_combo.currentData()
        self.settings['enable_remote'] = self.enable_remote_checkbox.isChecked()
        self.settings['remote_address'] = self.remote_address_edit.text()

        save_settings(self.settings)

    def update_qrcode(self, qrcode_pixmap: QPixmap) -> None:
        """更新二维码并保存原始图像"""
        self.original_qrcode_pixmap = qrcode_pixmap
        self.scale_qrcode()
        logger.info("二维码已更新")

    def scale_qrcode(self) -> None:
        """根据当前标签尺寸缩放二维码"""
        if self.original_qrcode_pixmap and not self.original_qrcode_pixmap.isNull():
            scaled_pixmap = self.original_qrcode_pixmap.scaled(
                self.qrcode_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.qrcode_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """优化窗口缩放处理"""
        # 先执行父类的resize事件处理
        super().resizeEvent(event)
        # 延迟执行二维码缩放以保证尺寸计算准确
        QTimer.singleShot(0, self.scale_qrcode)

    def update_connection_status(self, is_online: bool) -> None:
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

    def start_server_button_clicked(self) -> None:
        """启动/断开按钮被点击后的处理逻辑"""
        if self.server_task is None or self.server_task.done():
            # 启动服务器 - 使用统一接口
            self.ui_interface.set_connection_state(ConnectionState.CONNECTING)

            # 保存网络设置
            self.save_network_settings()
            self.start_server()
        else:
            # 断开服务器
            self.stop_server()

    def start_server(self) -> None:
        """启动 WebSocket 服务器 - 通过服务层管理"""
        # 验证远程地址（如果启用）
        if self.enable_remote_checkbox.isChecked():
            remote_addr_text = self.remote_address_edit.text()
            if remote_addr_text and not self.validate_ip_address(remote_addr_text):
                error_msg = translate("connection_tab.invalid_remote_address")
                logger.error(error_msg)
                QMessageBox.warning(self, translate("common.error"), error_msg)
                return

        selected_ip = self.ip_combobox.currentText().split(": ")[-1]
        selected_port = self.port_spinbox.value()
        osc_port = self.osc_port_spinbox.value()

        logger.info(
            f"正在启动 WebSocket 服务器，监听地址: {selected_ip}:{selected_port} 和 OSC 数据接收端口: {osc_port}")

        try:
            # 获取远程地址（如果启用）
            remote_address: Optional[str] = None
            if self.enable_remote_checkbox.isChecked():
                remote_text = self.remote_address_edit.text()
                remote_address = remote_text if remote_text else None

            # 创建控制器（如果不存在）
            if not self.controller:
                # 初始化服务（不再需要client参数）
                dglab_service: IDGLabService = DGLabWebSocketService(self.ui_interface)
                osc_service: OSCService = OSCService(self.ui_interface)
                chatbox_service: ChatboxService = ChatboxService(self.ui_interface, dglab_service, osc_service)

                # 注册OSC动作
                self._register_osc_actions(dglab_service, chatbox_service)

                # 启动定时任务
                chatbox_service.start_periodic_status_update()

                controller = DGLabController(dglab_service, osc_service, chatbox_service)
                self.ui_interface.set_controller(controller)
                # 在 controller 初始化后调用绑定函数
                self.ui_interface.bind_controller_settings()

            # 使用事件循环来启动服务器，并保存任务引用
            loop = asyncio.get_running_loop()
            self.server_task = loop.create_task(
                self.run_server_with_cleanup(selected_ip, selected_port, osc_port, remote_address))
            logger.info("WebSocket 服务器启动任务已创建")

        except Exception as e:
            error_message = translate("connection_tab.start_server_failed").format(str(e))
            logger.error(error_message)

            # 恢复按钮状态 - 使用统一接口
            self.ui_interface.set_connection_state(ConnectionState.FAILED, error_message)

    def _register_osc_actions(self, dglab_service: IDGLabService, chatbox_service: ChatboxService) -> None:
        """注册OSC动作（内部方法）"""

        # 清除现有动作（避免重复注册）
        self.ui_interface.registries.action_registry.clear_all_actions()

        # 检查DGLab服务是否可用

        # 注册通道控制操作
        self.ui_interface.registries.action_registry.register_action(
            "A通道触碰",
            self._create_async_wrapper(lambda *args: dglab_service.set_float_output(args[0], Channel.A)),
            OSCActionType.CHANNEL_CONTROL, {"channel_a", "touch"}
        )

        self.ui_interface.registries.action_registry.register_action(
            "B通道触碰",
            self._create_async_wrapper(lambda *args: dglab_service.set_float_output(args[0], Channel.B)),
            OSCActionType.CHANNEL_CONTROL, {"channel_b", "touch"}
        )

        self.ui_interface.registries.action_registry.register_action(
            "当前通道触碰",
            self._create_async_wrapper(lambda *args: dglab_service.set_float_output(
                args[0], dglab_service.get_current_channel()
            )),
            OSCActionType.CHANNEL_CONTROL, {"current_channel", "touch"}
        )

        # 注册面板控制操作
        self.ui_interface.registries.action_registry.register_action(
            "面板控制",
            self._create_async_wrapper(lambda *args: dglab_service.set_panel_control(args[0])),
            OSCActionType.PANEL_CONTROL, {"panel"}
        )

        self.ui_interface.registries.action_registry.register_action(
            "数值调节",
            self._create_async_wrapper(lambda *args: dglab_service.set_strength_step(args[0])),
            OSCActionType.PANEL_CONTROL, {"value_adjust"}
        )

        async def set_channel_wrapper(*args: OSCValue) -> None:
            if isinstance(args[0], (int, float)):
                await dglab_service.set_channel(args[0])

        self.ui_interface.registries.action_registry.register_action(
            "通道调节",
            set_channel_wrapper,
            OSCActionType.PANEL_CONTROL, {"channel_adjust"}
        )

        # 注册强度控制操作
        self.ui_interface.registries.action_registry.register_action(
            "设置模式",
            self._create_async_wrapper(lambda *args: dglab_service.set_mode(
                args[0], dglab_service.get_current_channel()
            )),
            OSCActionType.STRENGTH_CONTROL, {"mode"}
        )

        self.ui_interface.registries.action_registry.register_action(
            "重置强度",
            self._create_async_wrapper(lambda *args: dglab_service.reset_strength(
                args[0], dglab_service.get_current_channel()
            )),
            OSCActionType.STRENGTH_CONTROL, {"reset"}
        )

        self.ui_interface.registries.action_registry.register_action(
            "降低强度",
            self._create_async_wrapper(lambda *args: dglab_service.decrease_strength(
                args[0], dglab_service.get_current_channel()
            )),
            OSCActionType.STRENGTH_CONTROL, {"decrease"}
        )

        self.ui_interface.registries.action_registry.register_action(
            "增加强度",
            self._create_async_wrapper(lambda *args: dglab_service.increase_strength(
                args[0], dglab_service.get_current_channel()
            )),
            OSCActionType.STRENGTH_CONTROL, {"increase"}
        )

        self.ui_interface.registries.action_registry.register_action(
            "一键开火",
            self._create_async_wrapper(lambda *args: dglab_service.strength_fire_mode(
                args[0],
                dglab_service.get_current_channel(),
                dglab_service.fire_mode_strength_step,
                dglab_service.get_last_strength()
            )),
            OSCActionType.STRENGTH_CONTROL, {"fire"}
        )

        # 注册ChatBox控制操作
        self.ui_interface.registries.action_registry.register_action(
            "ChatBox状态开关",
            self._create_async_wrapper(lambda *args: chatbox_service.toggle_chatbox(args[0])),
            OSCActionType.CHATBOX_CONTROL, {"toggle"}
        )

        logger.info("OSC动作注册完成")

    def _create_async_wrapper(self, func: Callable[..., Awaitable[None]]) -> Callable[..., Awaitable[None]]:
        """创建异步包装器"""

        async def wrapper(*args: OSCValue) -> None:
            try:
                await func(*args)
            except Exception as e:
                logger.error(f"OSC动作执行失败: {e}")

        return wrapper

    def stop_server(self) -> None:
        """停止 WebSocket 服务器"""
        if self.server_task and not self.server_task.done():
            self.server_task.cancel()
            logger.info("WebSocket 服务器任务已取消")

        # 通过控制器停止服务器 - 创建异步任务但不等待
        if self.controller:
            asyncio.create_task(self._stop_services_and_cleanup())
        else:
            # 如果没有控制器，直接清理UI
            self._cleanup_ui()

    async def _stop_services_and_cleanup(self) -> None:
        """停止服务并清理UI状态"""
        try:
            # 等待服务实际停止
            await self._stop_services()
        finally:
            # 无论成功与否，都要清理UI状态
            self._cleanup_ui()

    def _cleanup_ui(self) -> None:
        """清理UI状态"""
        # 重置UI状态 - 使用统一接口
        self.ui_interface.set_connection_state(ConnectionState.DISCONNECTED)

        # 更新连接状态
        self.update_connection_status(False)

        # 清空二维码
        self.qrcode_label.clear()

        # 通过UI回调清空控制器引用
        self.ui_interface.set_controller(None)

    async def _stop_services(self) -> None:
        """停止所有服务"""
        if self.controller:
            try:
                # 停止WebSocket服务器
                await self.controller.dglab_service.stop_server()
                # 停止OSC服务器
                await self.controller.osc_service.stop_server()
                logger.info("所有服务已停止")
            except Exception as e:
                logger.error(f"停止服务时发生异常: {e}")

    async def run_server_with_cleanup(self, ip: str, port: int, osc_port: int,
                                      remote_address: Optional[str] = None) -> None:
        """运行服务器并处理清理工作 - 重构版本"""
        try:
            if not self.controller:
                logger.error("控制器未初始化")
                return

            # 启动WebSocket服务器
            success = await self.controller.dglab_service.start_server(ip, port, remote_address)
            if not success:
                error_msg = translate("connection_tab.start_server_failed").format("WebSocket服务器启动失败")
                logger.error(error_msg)
                self.ui_interface.set_connection_state(ConnectionState.FAILED, error_msg)
                return

            # 启动OSC服务器
            osc_started = await self.controller.osc_service.start_server(osc_port)
            if not osc_started:
                logger.error("OSC服务器启动失败")
                await self.controller.dglab_service.stop_server()
                self.ui_interface.set_connection_state(ConnectionState.FAILED, "OSC服务器启动失败")
                return

            logger.info("所有服务启动成功")

            # 等待服务器停止事件（完全消除轮询）
            await self.controller.dglab_service.wait_for_server_stop()

        except asyncio.CancelledError:
            logger.info("服务器任务被取消")
            raise
        except Exception as e:
            error_msg = translate("connection_tab.server_error").format(str(e))
            logger.error(error_msg)
            # 服务器异常后重置UI状态 - 使用统一接口
            self.ui_interface.set_connection_state(ConnectionState.FAILED, error_msg)
            self.update_connection_status(False)
            raise
        finally:
            # 服务器结束后清理状态
            self.server_task = None

    def get_public_ip(self) -> None:
        """获取公网IP地址"""
        try:
            response = requests.get('http://myip.ipip.net', timeout=5)
            # 解析返回的文本,通常格式为: "当前 IP：xxx.xxx.xxx.xxx 来自于：xxx"
            public_ip = response.text.split('：')[1].split(' ')[0]
            self.remote_address_edit.setText(public_ip)
            logger.info(f"获取到公网IP: {public_ip}")
            # 保存设置
            self.save_network_settings()
        except Exception as e:
            error_msg = translate("connection_tab.get_public_ip_failed").format(str(e))
            logger.error(error_msg)
            # 显示错误提示框
            QMessageBox.warning(self, translate("common.error"), error_msg)

    def validate_ip_address(self, ip: str) -> bool:
        """验证IP地址格式是否正确"""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                if not part.isdigit():
                    return False
                num = int(part)
                if num < 0 or num > 255:
                    return False
            return True
        except (AttributeError, TypeError):
            return False

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

        # 保存设置
        self.save_network_settings()

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
                # 保存设置
                self.save_network_settings()
        else:
            # 未启用远程连接或地址为空时恢复正常状态
            self.remote_address_edit.setStyleSheet("")
            self.ui_interface.set_connection_state(ConnectionState.DISCONNECTED)

    def on_language_changed(self) -> None:
        """处理语言选择变更，直接生效"""
        selected_language: Optional[str] = self.language_combo.currentData()
        if selected_language:
            # 设置语言
            success: bool = set_language(selected_language)
            if success:
                # 保存语言设置到配置文件
                self.settings['language'] = selected_language
                save_settings(self.settings)
                logger.info(
                    f"Language changed to {LANGUAGES.get(selected_language, selected_language)} ({selected_language})")

    def _set_button_disabled(self) -> None:
        """禁用按钮状态（用于地址验证失败等情况）"""
        self.start_button.setEnabled(False)
        self.start_button.setStyleSheet("background-color: grey; color: white;")

    def update_ui_texts(self) -> None:
        """更新UI上的文本为当前语言"""
        self.network_config_group.setTitle(translate("connection_tab.title"))
        self.language_label.setText(translate("main.settings.language_label"))
        # start_button的文本现在通过统一接口管理，这里不需要直接设置
        # 保持当前连接状态的显示文本
        current_state = self.ui_interface.get_connection_state()
        if current_state == ConnectionState.CONNECTED:
            self.start_button.setText(translate("connection_tab.disconnect"))
        else:
            self.start_button.setText(translate("connection_tab.connect"))

        # 更新表单标签 - 使用直接引用而不是文本匹配
        self.interface_label.setText(translate("connection_tab.interface_label"))
        self.websocket_port_label.setText(translate("connection_tab.websocket_port_label"))
        self.osc_port_label.setText(translate("connection_tab.osc_port_label"))
        self.status_label.setText(translate("connection_tab.status_label"))
        self.remote_address_label.setText(translate("connection_tab.remote_address_label"))

        # 更新连接状态标签 - 保持当前状态但更新语言
        if self.controller:
            if self.controller.app_status_online:
                self.connection_status_label.setText(translate("connection_tab.online"))
            else:
                self.connection_status_label.setText(translate("connection_tab.offline"))
        else:
            # 没有控制器时，显示默认离线状态
            self.connection_status_label.setText(translate("connection_tab.offline"))
        # 更新其他UI文本
        self.enable_remote_checkbox.setText(translate("connection_tab.enable_remote"))
        self.remote_address_edit.setPlaceholderText(translate("connection_tab.please_enter_valid_ip"))
        self.get_public_ip_button.setText(translate("connection_tab.get_public_ip"))
