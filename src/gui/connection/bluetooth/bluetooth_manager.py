import asyncio
import logging
from typing import Optional, Dict, List

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
    """蓝牙连接组件的信号类"""
    # 设备发现相关信号
    devices_found = Signal(list)
    discovery_started = Signal()
    discovery_finished = Signal()
    discovery_error = Signal(str)
    
    # 连接状态信号
    connection_state_changed = Signal(ConnectionState, str)
    device_connected = Signal(object)  # DGLabDevice
    device_disconnected = Signal()
    
    # 设备状态信号
    battery_level_changed = Signal(int)


class BluetoothConnectionManager:
    """
    蓝牙连接管理器
    处理蓝牙连接相关的业务逻辑
    """

    def __init__(self, ui_interface: UIInterface):
        super().__init__()
        self.ui_interface = ui_interface
        self.settings: SettingsDict = ui_interface.settings
        self.server_task: Optional[asyncio.Task[None]] = None

        # 信号组件 - 使用组合模式
        self.signals: BluetoothConnectionSignals = BluetoothConnectionSignals()
        
        # 当前选中的设备
        self.selected_device: Optional[DGLabDevice] = None
        
        # 发现的设备列表
        self.discovered_devices: List[DGLabDevice] = []
    
    @property
    def service_controller(self) -> Optional[ServiceController]:
        """获取当前服务控制器"""
        return self.ui_interface.service_controller
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.server_task is not None and not self.server_task.done()
    
    def set_selected_device(self, device: Optional[DGLabDevice]) -> None:
        """设置选中的设备"""
        self.selected_device = device
        if device:
            logger.info(f"选择设备: {device['name']} ({device['address']})")
    
    async def start_device_discovery(self, scan_time: float = 5.0) -> None:
        """开始设备发现"""
        try:
            self.discovered_devices.clear()
            self.signals.discovery_started.emit()
            logger.info("开始蓝牙设备发现")

            await self._device_discovery_task(scan_time)
            
        except Exception as e:
            error_msg = f"启动设备发现失败: {e}"
            logger.error(error_msg)
            self.signals.discovery_error.emit(error_msg)
    
    async def _device_discovery_task(self, scan_time: float) -> None:
        """设备发现任务"""
        try:
            # 创建临时蓝牙服务进行设备扫描
            bluetooth_service = DGLabBluetoothService(self.ui_interface)
            devices = await bluetooth_service.scan_devices(scan_time)
            
            # 更新设备列表
            self.discovered_devices = devices
            self.signals.devices_found.emit(devices)
            
            logger.info(f"设备发现完成，找到 {len(devices)} 个设备")
            
        except Exception as e:
            error_msg = f"设备发现失败: {e}"
            logger.error(error_msg)
            self.signals.discovery_error.emit(error_msg)
        finally:
            self.signals.discovery_finished.emit()
    
    def start_connection(self, device: Optional[DGLabDevice], osc_port: int) -> None:
        """启动蓝牙连接"""
        target_device = device or self.selected_device
        if not target_device:
            self.signals.discovery_error.emit("没有选择要连接的设备")
            return

        logger.info(f"正在启动蓝牙连接: {target_device['name']} ({target_device['address']}), OSC端口: {osc_port}")

        # 设置连接状态
        self.ui_interface.set_connection_state(ConnectionState.CONNECTING)

        # 启动服务器
        self.server_task = asyncio.create_task(
            self._run_server(target_device, osc_port)
        )

    def stop_connection(self) -> None:
        """停止蓝牙连接"""
        logger.info("正在停止蓝牙连接")
        if self.server_task and not self.server_task.done():
            self.server_task.cancel()

    async def _run_server(self, device: DGLabDevice, osc_port: int) -> None:
        """运行蓝牙服务器 - 内部方法"""
        try:
            # 创建服务控制器(如果不存在)
            if not self.service_controller:
                dglab_service = DGLabBluetoothService(self.ui_interface)

                osc_service = OSCService(self.ui_interface, osc_port)
                osc_action_service = OSCActionService(dglab_service, self.ui_interface)
                chatbox_service = ChatboxService(self.ui_interface, osc_service, osc_action_service)

                controller = ServiceController(dglab_service, osc_service, osc_action_service, chatbox_service)
                self.ui_interface.set_service_controller(controller)

            # 启动所有服务
            if self.service_controller:
                success = await self.service_controller.start_all_services()
                if success:
                    logger.info("所有蓝牙服务启动成功")
                    self.ui_interface.set_connection_state(ConnectionState.WAITING)
                    
                    # 连接到指定设备
                    bluetooth_service = self.service_controller.dglab_device_service
                    if isinstance(bluetooth_service, DGLabBluetoothService):
                        device_connected = await bluetooth_service.connect_device(device)
                        if device_connected:
                            self.signals.device_connected.emit(device)
                    else:
                        logger.warning("当前设备服务不支持蓝牙设备连接")

                    # 保持服务运行
                    while self.server_task and not self.server_task.cancelled():
                        await asyncio.sleep(1)
                else:
                    logger.error("蓝牙服务启动失败")
                    self.ui_interface.set_connection_state(ConnectionState.FAILED, "蓝牙服务启动失败")
            else:
                logger.error("服务控制器未初始化")
                self.ui_interface.set_connection_state(ConnectionState.FAILED, "服务控制器未初始化")

        except asyncio.CancelledError:
            logger.info("蓝牙连接任务被取消")
            # 停止所有服务
            if self.service_controller:
                await self.service_controller.stop_all_services()
            self.ui_interface.set_connection_state(ConnectionState.DISCONNECTED)
            raise

        except Exception as e:
            logger.error(f"蓝牙连接运行异常: {str(e)}")
            self.ui_interface.set_connection_state(ConnectionState.FAILED, str(e))

        finally:
            self.server_task = None
    
    def save_settings(self, strength_limit_a: int = 200, strength_limit_b: int = 200,
                     freq_balance_a: int = 160, freq_balance_b: int = 160,
                     strength_balance_a: int = 0, strength_balance_b: int = 0) -> None:
        """保存蓝牙设置"""
        try:
            # 确保设置结构存在
            if 'connection' not in self.settings:
                self.settings['connection'] = {}
            if 'bluetooth' not in self.settings['connection']:
                self.settings['connection']['bluetooth'] = {}
            
            # 保存蓝牙参数
            bluetooth_settings = self.settings['connection']['bluetooth']
            bluetooth_settings['strength_limit_a'] = strength_limit_a
            bluetooth_settings['strength_limit_b'] = strength_limit_b
            bluetooth_settings['freq_balance_a'] = freq_balance_a
            bluetooth_settings['freq_balance_b'] = freq_balance_b
            bluetooth_settings['strength_balance_a'] = strength_balance_a
            bluetooth_settings['strength_balance_b'] = strength_balance_b
            
            save_settings(self.settings)
            logger.info("蓝牙设置已保存")
            
        except Exception as e:
            logger.error(f"保存蓝牙设置失败: {e}")
    
    def load_default_settings(self) -> Dict[str, int]:
        """加载默认设置"""
        bluetooth_settings = self.settings.get('connection', {}).get('bluetooth', {})
        
        return {
            'strength_limit_a': bluetooth_settings.get('strength_limit_a', 200),
            'strength_limit_b': bluetooth_settings.get('strength_limit_b', 200),
            'freq_balance_a': bluetooth_settings.get('freq_balance_a', 160),
            'freq_balance_b': bluetooth_settings.get('freq_balance_b', 160),
            'strength_balance_a': bluetooth_settings.get('strength_balance_a', 0),
            'strength_balance_b': bluetooth_settings.get('strength_balance_b', 0)
        }
    
    async def cleanup(self) -> None:
        """清理资源"""
        try:
            # 停止连接任务
            if self.server_task and not self.server_task.done():
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass
            
            # 停止所有服务
            if self.service_controller:
                await self.service_controller.stop_all_services()
            
            logger.info("蓝牙管理器资源已清理")
            
        except Exception as e:
            logger.error(f"清理蓝牙管理器资源失败: {e}")
    
