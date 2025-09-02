"""
蓝牙连接管理器

简化版本，参考WebSocket管理器的设计：
- 移除复杂的信号机制
- 统一使用UIInterface管理状态
- 简化方法调用链
- 严格类型检查
"""

import asyncio
import logging
from typing import List, Optional, Dict

from PySide6.QtCore import QObject, Signal

from config import save_settings
from core import ServiceController
from gui.ui_interface import UIInterface
from models import SettingsDict, ConnectionState
from services.chatbox_service import ChatboxService
from services.dglab_bluetooth_service import DGLabBluetoothService, DGLabDevice
from services.osc_action_service import OSCActionService
from services.osc_service import OSCService

logger = logging.getLogger(__name__)


class BluetoothConnectionSignals(QObject):
    """蓝牙连接信号"""
    battery_level_updated = Signal(int)  # 电量更新信号


class BluetoothConnectionManager:
    """
    蓝牙连接管理器
    简化版本，参考WebSocket管理器的设计模式
    """

    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.settings: SettingsDict = ui_interface.settings
        self.server_task: Optional[asyncio.Task[None]] = None
        
        # 信号系统
        self.signals: BluetoothConnectionSignals = BluetoothConnectionSignals()
        
        # 设备管理
        self.discovered_devices: List[DGLabDevice] = []
        self.selected_device: Optional[DGLabDevice] = None
        
        # 当前连接的设备信息
        self.connected_device: Optional[DGLabDevice] = None

    @property
    def service_controller(self) -> Optional[ServiceController]:
        """获取当前服务控制器"""
        return self.ui_interface.service_controller

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.server_task is not None and not self.server_task.done()

    def get_connected_device(self) -> Optional[DGLabDevice]:
        """获取当前连接的设备"""
        return self.connected_device

    def get_discovered_devices(self) -> List[DGLabDevice]:
        """获取已发现的设备列表"""
        return self.discovered_devices.copy()

    def set_selected_device(self, device: Optional[DGLabDevice]) -> None:
        """设置选中的设备"""
        self.selected_device = device

    def get_selected_device(self) -> Optional[DGLabDevice]:
        """获取选中的设备"""
        return self.selected_device

    async def discover_devices(self, timeout: float = 5.0) -> List[DGLabDevice]:
        """
        发现蓝牙设备
        
        Args:
            timeout: 扫描超时时间
            
        Returns:
            发现的设备列表
        """
        logger.info(f"开始扫描蓝牙设备，超时: {timeout}秒")
        
        try:
            # 创建临时蓝牙服务用于设备扫描
            temp_service = DGLabBluetoothService(self.ui_interface)
            devices = await temp_service.scan_devices(timeout)
            
            self.discovered_devices = devices
            logger.info(f"扫描完成，发现 {len(devices)} 个设备")
            return devices
            
        except Exception as e:
            logger.error(f"扫描设备失败: {e}")
            self.discovered_devices = []
            return []

    def start_connection(self, device: DGLabDevice, osc_port: int) -> None:
        """启动蓝牙连接"""
        logger.info(f"正在启动蓝牙连接: {device['name']} ({device['address']}), OSC端口: {osc_port}")
        
        # 设置连接状态
        self.ui_interface.set_connection_state(ConnectionState.CONNECTING)
        self.selected_device = device

        # 启动服务器
        self.server_task = asyncio.create_task(
            self._run_server(device, osc_port)
        )

    def stop_connection(self) -> None:
        """停止蓝牙连接"""
        logger.info("正在停止蓝牙连接")
        if self.server_task and not self.server_task.done():
            self.server_task.cancel()

    async def _run_server(self, device: DGLabDevice, osc_port: int) -> None:
        """运行蓝牙服务器 - 内部方法"""
        try:
            # 创建服务控制器（如果不存在）
            if not self.service_controller:
                dglab_device_service = DGLabBluetoothService(self.ui_interface)
                # 连接蓝牙服务的信号到管理器信号
                dglab_device_service.signals.battery_level_updated.connect(self.signals.battery_level_updated.emit)

                osc_service = OSCService(self.ui_interface, osc_port)
                osc_action_service = OSCActionService(dglab_device_service, self.ui_interface)
                chatbox_service = ChatboxService(self.ui_interface, osc_service, osc_action_service)

                service_controller = ServiceController(dglab_device_service, osc_service, osc_action_service, chatbox_service)
                self.ui_interface.set_service_controller(service_controller)

                # 启动所有服务
                success = await service_controller.start_all_services()
                if not success:
                    logger.error("蓝牙服务启动失败")
                    self.ui_interface.set_connection_state(ConnectionState.FAILED, "蓝牙服务启动失败")
                    return
                    
                logger.info("所有蓝牙服务启动成功")
                self.ui_interface.set_connection_state(ConnectionState.WAITING, "服务启动完成")

                # 连接到指定设备
                logger.info(f"正在连接设备: {device['name']}")
                self.ui_interface.set_connection_state(ConnectionState.CONNECTING, "正在连接设备...")
                
                # 在连接前设置设备信息，确保UI回调时能获取到设备信息
                self.connected_device = device
                
                device_connected = await dglab_device_service.connect_device(device)
                if device_connected:
                    logger.info("设备连接成功")
                    self.ui_interface.set_connection_state(ConnectionState.CONNECTED, "设备连接成功")
                else:
                    logger.error(f"蓝牙设备连接失败: {device['name']}")
                    self.ui_interface.set_connection_state(ConnectionState.FAILED, "设备连接失败")
                    self.connected_device = None  # 连接失败时清除设备信息
                    await service_controller.stop_all_services()
                    return

                # 保持服务运行
                while self.server_task and not self.server_task.cancelled():
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("蓝牙连接任务被取消")
            # 停止所有服务
            if self.service_controller:
                await self.service_controller.stop_all_services()
            self.ui_interface.set_connection_state(ConnectionState.DISCONNECTED)
            self.connected_device = None
            raise

        except Exception as e:
            logger.error(f"蓝牙连接运行异常: {str(e)}")
            self.ui_interface.set_connection_state(ConnectionState.FAILED, str(e))
            self.connected_device = None

        finally:
            self.server_task = None
            self.connected_device = None
            self.ui_interface.set_service_controller(None)

    def save_settings(self, **bluetooth_params: int) -> None:
        """保存蓝牙设置"""
        try:
            # 确保设置结构存在
            if 'connection' not in self.settings:
                self.settings['connection'] = {}
            if 'bluetooth' not in self.settings['connection']:
                self.settings['connection']['bluetooth'] = {}

            # 更新蓝牙参数
            bluetooth_settings = self.settings['connection']['bluetooth']
            for key, value in bluetooth_params.items():
                bluetooth_settings[key] = value

            save_settings(self.settings)
            logger.info("蓝牙设置已保存")
            
        except Exception as e:
            logger.error(f"保存蓝牙设置失败: {e}")
            raise

    def load_default_settings(self) -> Dict[str, int]:
        """加载默认蓝牙设置"""
        default_settings = {
            'strength_limit_a': 200,
            'strength_limit_b': 200,
            'freq_balance_a': 160,
            'freq_balance_b': 160,
            'strength_balance_a': 0,
            'strength_balance_b': 0
        }
        
        # 从配置中加载已保存的设置
        bluetooth_config = self.settings.get('connection', {}).get('bluetooth', {})
        for key in default_settings:
            if key in bluetooth_config:
                default_settings[key] = bluetooth_config[key]
                
        return default_settings
