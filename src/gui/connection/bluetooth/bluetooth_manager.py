import logging
from typing import Optional, List, Dict

from PySide6.QtCore import QObject, Signal

from core.bluetooth.bluetooth_controller import BluetoothController
from core.bluetooth.bluetooth_models import DeviceInfo, Channel
from gui.ui_interface import UIInterface
from models import SettingsDict, ConnectionState
from config import save_settings

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
    device_connected = Signal(DeviceInfo)
    device_disconnected = Signal()
    
    # 设备状态信号
    battery_level_changed = Signal(int)


class BluetoothConnectionManager:
    """
    蓝牙连接管理器
    处理蓝牙连接相关的业务逻辑，与UI解耦
    """

    def __init__(self, ui_interface: UIInterface):
        super().__init__()
        self.ui_interface = ui_interface
        self.settings: SettingsDict = ui_interface.settings

        # 信号组件 - 使用组合模式
        self.signals: BluetoothConnectionSignals = BluetoothConnectionSignals()
        
        # 蓝牙控制器
        self.bluetooth_controller = BluetoothController()
        
        # 当前选中的设备
        self.selected_device: Optional[DeviceInfo] = None
        
        # 发现的设备列表
        self.discovered_devices: List[DeviceInfo] = []
        
        
        # 设置蓝牙控制器回调
        self._setup_controller_callbacks()
    
    def _setup_controller_callbacks(self) -> None:
        """设置蓝牙控制器回调"""
        self.bluetooth_controller.set_connection_callback(self._on_connection_changed)
        self.bluetooth_controller.set_strength_changed_callback(self._on_strength_changed)
        self.bluetooth_controller.set_battery_callback(self._on_battery_changed)
    
    async def _on_connection_changed(self, connected: bool) -> None:
        """连接状态变化回调"""
        try:
            if connected:
                device = self.bluetooth_controller.current_device
                if device:
                    self.signals.device_connected.emit(device)
                    self.signals.connection_state_changed.emit(ConnectionState.CONNECTED.value, "")
                    logger.info(f"蓝牙设备连接成功: {device['name']}")
            else:
                self.signals.device_disconnected.emit()
                self.signals.connection_state_changed.emit(ConnectionState.DISCONNECTED.value, "")
                logger.info("蓝牙设备连接已断开")
        except Exception as e:
            logger.error(f"处理连接状态变化异常: {e}")
    
    async def _on_strength_changed(self, strength_dict: Dict[Channel, int]) -> None:
        """强度变化回调"""
        try:
            logger.debug(f"设备强度更新: {strength_dict}")
        except Exception as e:
            logger.error(f"处理强度变化异常: {e}")
    
    async def _on_battery_changed(self, battery_level: int) -> None:
        """电量变化回调"""
        try:
            self.signals.battery_level_changed.emit(battery_level)
            logger.debug(f"电量更新: {battery_level}%")
        except Exception as e:
            logger.error(f"处理电量变化异常: {e}")
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.bluetooth_controller.is_connected
    
    def set_selected_device(self, device: Optional[DeviceInfo]) -> None:
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
            # 执行设备扫描
            devices = await self.bluetooth_controller.scan_devices(scan_time)
            
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
    
    async def connect_to_device(self, device: Optional[DeviceInfo] = None) -> None:
        """连接到设备"""
        try:
            target_device = device or self.selected_device
            if not target_device:
                error_msg = "没有选择要连接的设备"
                logger.error(error_msg)
                self.signals.connection_state_changed.emit(ConnectionState.FAILED.value, error_msg)
                return
            
            self.signals.connection_state_changed.emit(ConnectionState.CONNECTING.value, "")
            logger.info(f"开始连接设备: {target_device['name']}")
            
            # 执行连接
            success = await self.bluetooth_controller.connect_device(target_device, 20.0)
            
            if success:
                self.signals.connection_state_changed.emit(ConnectionState.CONNECTED.value, "")
                
                # 自动应用默认参数
                await self._apply_default_parameters()
            else:
                error_msg = "设备连接失败"
                self.signals.connection_state_changed.emit(ConnectionState.FAILED.value, error_msg)
                
        except Exception as e:
            error_msg = f"连接设备异常: {e}"
            logger.error(error_msg)
            self.signals.connection_state_changed.emit(ConnectionState.ERROR.value, error_msg)
    
    async def disconnect_from_device(self) -> None:
        """断开设备连接"""
        try:
            logger.info("开始断开设备连接")
            await self.bluetooth_controller.disconnect_device()
            self.signals.connection_state_changed.emit(ConnectionState.DISCONNECTED.value, "")
            
        except Exception as e:
            error_msg = f"断开设备异常: {e}"
            logger.error(error_msg)
            self.signals.connection_state_changed.emit(ConnectionState.ERROR.value, error_msg)
    
    async def apply_device_parameters(self, strength_limit_a: int = 200, strength_limit_b: int = 200,
                                    freq_balance_a: int = 100, freq_balance_b: int = 100,
                                    strength_balance_a: int = 100, strength_balance_b: int = 100) -> None:
        """应用设备参数"""
        try:
            if not self.bluetooth_controller.is_connected:
                error_msg = "设备未连接"
                return
            
            success = await self.bluetooth_controller.set_device_params(
                strength_limit_a=strength_limit_a,
                strength_limit_b=strength_limit_b,
                freq_balance_a=freq_balance_a,
                freq_balance_b=freq_balance_b,
                strength_balance_a=strength_balance_a,
                strength_balance_b=strength_balance_b
            )
            
            if success:
                logger.info("设备参数应用成功")
            else:
                logger.error("设备参数应用失败")
                
        except Exception as e:
            error_msg = f"应用设备参数异常: {e}"
            logger.error(error_msg)
    
    async def _apply_default_parameters(self) -> None:
        """应用默认参数"""
        bluetooth_settings = self.settings.get('connection', {}).get('bluetooth', {})
        
        await self.apply_device_parameters(
            strength_limit_a=bluetooth_settings.get('strength_limit_a', 200),
            strength_limit_b=bluetooth_settings.get('strength_limit_b', 200),
            freq_balance_a=bluetooth_settings.get('freq_balance_a', 160),
            freq_balance_b=bluetooth_settings.get('freq_balance_b', 160),
            strength_balance_a=bluetooth_settings.get('strength_balance_a', 0),
            strength_balance_b=bluetooth_settings.get('strength_balance_b', 0)
        )
    
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
            # 断开连接
            if self.bluetooth_controller.is_connected:
                await self.bluetooth_controller.disconnect_device()
            
            # 清理控制器
            await self.bluetooth_controller.cleanup()
            
            logger.info("蓝牙管理器资源已清理")
            
        except Exception as e:
            logger.error(f"清理蓝牙管理器资源失败: {e}")
    
