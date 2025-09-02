"""
DG-LAB 蓝牙直连服务实现

基于自实现的V3协议层，替代pydglab库的蓝牙直连设备服务，实现IDGLabDeviceService接口。
只负责设备连接和基础硬件操作，不包含任何业务逻辑。
"""

import asyncio
import logging
from typing import Optional, List, Dict, TypedDict

from PySide6.QtCore import QObject, Signal

from core import bluetooth
from core.core_interface import CoreInterface
from core.dglab_pulse import Pulse
from models import Channel, ConnectionState, StrengthData, StrengthOperationType, PulseOperation
from services.dglab_service_interface import IDGLabDeviceService

logger = logging.getLogger(__name__)


class BluetoothSignals(QObject):
    """蓝牙信号"""
    battery_level_updated = Signal(int)  # 电量更新信号


class DGLabDevice(TypedDict):
    """设备信息类型定义"""
    address: str
    rssi: int
    name: str


class DGLabBluetoothService(IDGLabDeviceService):
    """DG-LAB蓝牙直连服务
    
    基于自实现的V3协议层的蓝牙设备硬件通信实现，只负责：
    1. 蓝牙设备连接管理
    2. 基础强度操作
    3. 波形数据传输
    4. 设备状态查询
    
    不包含任何业务逻辑，所有业务逻辑由OSCActionService处理。
    """

    def __init__(self, core_interface: CoreInterface) -> None:
        """初始化蓝牙服务"""
        super().__init__()
        
        # 核心接口
        self._core_interface: CoreInterface = core_interface
        
        # 信号组件 - 使用组合模式
        self.signals: BluetoothSignals = BluetoothSignals()
        
        # 蓝牙控制器（新架构只需要Controller）
        self._bluetooth_controller: bluetooth.BluetoothController = bluetooth.BluetoothController()
        
        # 连接状态
        self._is_connected: bool = False
        
        # 服务状态
        self._server_running: bool = False
        self._stop_event: asyncio.Event = asyncio.Event()
        
        # 强度数据缓存
        self._last_strength: Optional[StrengthData] = None
        self._current_strengths: Dict[Channel, int] = {Channel.A: 0, Channel.B: 0}
        
        # 设备参数
        self._strength_limits: Dict[Channel, int] = {Channel.A: 200, Channel.B: 200}
        self._freq_balances: Dict[Channel, int] = {Channel.A: 160, Channel.B: 160}
        self._strength_balances: Dict[Channel, int] = {Channel.A: 0, Channel.B: 0}
        
        # 设置回调
        self._setup_callbacks()
        
        logger.info("蓝牙服务已初始化")

    def _setup_callbacks(self) -> None:
        """设置回调函数"""
        self._bluetooth_controller.set_connection_callback(self._on_connection_changed)
        self._bluetooth_controller.set_strength_changed_callback(self._on_strength_changed)
        self._bluetooth_controller.set_battery_callback(self._on_battery_changed)

    async def _on_connection_changed(self, connected: bool) -> None:
        """处理连接状态变化"""
        logger.info(f"蓝牙连接状态变化: {'已连接' if connected else '已断开'}")
        
        self._is_connected = connected
        
        if connected:
            # 连接成功后初始化设备
            await self._initialize_device()
            # 通知核心接口连接成功
            self._core_interface.on_client_connected()
        else:
            # 尝试重连
            logger.info("开始尝试重连设备")
            asyncio.create_task(self._attempt_reconnect())

    async def _on_strength_changed(self, strengths: Dict[bluetooth.Channel, int]) -> None:
        """处理强度变化"""
        try:
            # 转换蓝牙通道到模型通道
            model_strengths: Dict[Channel, int] = {
                Channel.A: strengths[bluetooth.Channel.A],
                Channel.B: strengths[bluetooth.Channel.B]
            }
            
            # 更新缓存
            self._current_strengths = model_strengths
            self._last_strength = {
                "strength": model_strengths,
                "strength_limit": self._strength_limits.copy()
            }
            
            logger.debug(f"强度变化: A={model_strengths[Channel.A]}, B={model_strengths[Channel.B]}")
            
            # 通知核心接口强度数据更新
            self._core_interface.on_strength_data_updated(self._last_strength)
            
        except Exception as e:
            logger.error(f"处理强度变化失败: {e}")

    async def _on_battery_changed(self, battery_level: int) -> None:
        """处理电量变化"""
        logger.debug(f"电量变化: {battery_level}%")
        
        # 通过信号发送电量更新
        self.signals.battery_level_updated.emit(battery_level)

    # ============ 连接管理 ============

    async def start_service(self) -> bool:
        """启动设备连接服务"""
        try:
            logger.info("开始启动蓝牙服务...")
            self._server_running = True
            self._stop_event.clear()
            
            logger.info("蓝牙服务启动成功")
            return True
            
        except Exception as e:
            logger.error(f"启动蓝牙服务失败: {e}")
            self._server_running = False
            return False

    async def stop_service(self) -> None:
        """停止设备连接服务"""
        try:
            logger.info("正在停止蓝牙服务...")
            self._server_running = False
            self._stop_event.set()
            
            # 断开蓝牙连接
            if self._is_connected:
                await self._disconnect_device()
            
            logger.info("蓝牙服务已停止")
            
        except Exception as e:
            logger.error(f"停止蓝牙服务失败: {e}")

    def is_service_running(self) -> bool:
        """检查设备连接服务运行状态"""
        return self._server_running

    def get_connection_type(self) -> str:
        """获取连接类型标识"""
        return "bluetooth"

    async def wait_for_server_stop(self) -> None:
        """等待服务停止事件（用于替代轮询）"""
        await self._stop_event.wait()

    # ============ 基础强度操作 ============

    async def set_float_output(self, value: float, channel: Channel) -> None:
        """设置浮点输出强度（原始设备操作）"""
        # 转换通道类型
        await self._bluetooth_controller.set_strength_absolute(
            self._convert_channel(channel),
            int(value)
        )

    async def adjust_strength(self, operation_type: StrengthOperationType, value: int, channel: Channel) -> None:
        """调整通道强度（原始设备操作）"""
        if operation_type == StrengthOperationType.SET_TO:
            await self._bluetooth_controller.set_strength_absolute(
                self._convert_channel(channel),
                value
            )
        elif operation_type == StrengthOperationType.INCREASE:
            await self._bluetooth_controller.set_strength_relative(
                self._convert_channel(channel),
                value
            )
        elif operation_type == StrengthOperationType.DECREASE:
            await self._bluetooth_controller.set_strength_relative(
                self._convert_channel(channel),
                -value
            )

    async def reset_strength(self, value: bool, channel: Channel) -> None:
        """重置通道强度为0（原始设备操作）"""
        if value:
            await self.adjust_strength(StrengthOperationType.SET_TO, 0, channel)

    async def increase_strength(self, value: bool, channel: Channel) -> None:
        """增加通道强度（原始设备操作）"""
        if value:
            await self.adjust_strength(StrengthOperationType.INCREASE, 1, channel)

    async def decrease_strength(self, value: bool, channel: Channel) -> None:
        """减少通道强度（原始设备操作）"""
        if value:
            await self.adjust_strength(StrengthOperationType.DECREASE, 1, channel)

    # ============ 波形数据操作 ============

    async def set_pulse_data(self, channel: Channel, pulse: Optional[Pulse]) -> None:
        """设置指定通道的波形数据"""
        if pulse:
            await self._bluetooth_controller.set_pulse_data(
                self._convert_channel(channel),
                self._convert_pulse_operations(pulse.data)
            )
        else:
            await self._bluetooth_controller.clear_pulse_data(
                self._convert_channel(channel)
            )

    # ============ 数据访问 ============

    def get_last_strength(self) -> Optional[StrengthData]:
        """获取最后的强度数据"""
        return self._last_strength

    def update_strength_data(self, strength_data: StrengthData) -> None:
        """更新强度数据（通常由连接层调用）"""
        self._last_strength = strength_data
        self._current_strengths[Channel.A] = strength_data['strength'][Channel.A]
        self._current_strengths[Channel.B] = strength_data['strength'][Channel.B]

    # ============ 设备参数管理 ============

    def get_strength_limit(self, channel: Channel) -> int:
        """获取指定通道的强度上限"""
        return self._strength_limits[channel]

    def set_strength_limit(self, channel: Channel, limit: int) -> None:
        """设置指定通道的强度上限
        
        Args:
            channel: 目标通道
            limit: 强度上限值 (0-200)
        """
        if not (0 <= limit <= 200):
            logger.warning(f"强度上限必须在0-200范围内，当前值: {limit}")
            return
        self._strength_limits[channel] = limit
        
        # 如果设备已连接，立即更新到设备
        if self._is_connected:
            asyncio.create_task(self._update_device_params())
        
        logger.debug(f"设置通道{channel}强度上限: {limit}")

    def get_freq_balance(self, channel: Channel) -> int:
        """获取指定通道的频率平衡参数"""
        return self._freq_balances[channel]

    def set_freq_balance(self, channel: Channel, balance: int) -> None:
        """设置指定通道的频率平衡参数
        
        Args:
            channel: 目标通道
            balance: 频率平衡参数 (0-255)
        """
        if not (0 <= balance <= 255):
            logger.warning(f"频率平衡参数必须在0-255范围内，当前值: {balance}")
            return

        self._freq_balances[channel] = balance
        
        # 如果设备已连接，立即更新到设备
        if self._is_connected:
            asyncio.create_task(self._update_device_params())
        
        logger.debug(f"设置通道{channel}频率平衡: {balance}")

    def get_strength_balance(self, channel: Channel) -> int:
        """获取指定通道的强度平衡参数"""
        return self._strength_balances[channel]

    def set_strength_balance(self, channel: Channel, balance: int) -> None:
        """设置指定通道的强度平衡参数
        
        Args:
            channel: 目标通道
            balance: 强度平衡参数 (0-255)
        """
        if not (0 <= balance <= 255):
            logger.warning(f"强度平衡参数必须在0-255范围内，当前值: {balance}")
            return
        self._strength_balances[channel] = balance
        
        # 如果设备已连接，立即更新到设备
        if self._is_connected:
            asyncio.create_task(self._update_device_params())
        
        logger.debug(f"设置通道{channel}强度平衡: {balance}")

    # ============ 公共设备管理方法 ============

    async def scan_devices(self, scan_time: float = 5.0) -> List[DGLabDevice]:
        """
        扫描可用的DG-LAB v3.0设备
        
        Args:
            scan_time: 扫描时间，单位为秒，默认5.0秒
        
        Returns:
            List[DGLabDevice]: 设备信息列表，包含address、rssi和name字段
        """
        try:
            logger.info(f"开始扫描可用的DG-LAB v3.0设备，扫描时间: {scan_time}秒...")
            
            # 使用蓝牙控制器扫描设备
            devices: List[bluetooth.DeviceInfo] = await self._bluetooth_controller.scan_devices(scan_time)
            
            # 转换为DGLabDevice格式
            device_list: List[DGLabDevice] = []
            for device_info in devices:
                device: DGLabDevice = {
                    "address": device_info['address'],
                    "rssi": device_info['rssi'],
                    "name": device_info['name']
                }
                device_list.append(device)
            
            logger.info(f"扫描完成，发现 {len(device_list)} 个设备")
            return device_list
            
        except Exception as e:
            logger.error(f"扫描设备失败: {e}")
            return []

    async def connect_device(self, device: Optional[DGLabDevice] = None) -> bool:
        """
        连接到DG-LAB设备
        
        Args:
            device (DGLabDevice, optional): 指定设备信息，如果为None则扫描并连接第一个可用设备
            
        Returns:
            bool: 连接是否成功
        """
        try:
            # 设置等待连接状态
            self._core_interface.set_connection_state(ConnectionState.WAITING)
            
            success: bool = False
            
            if device:
                logger.info(f"尝试连接到指定设备: {device['address']}")
                # 断开现有连接
                if self._is_connected:
                    await self._disconnect_device()
                
                # 创建设备信息并连接
                device_info: bluetooth.DeviceInfo = {
                    'address': device['address'],
                    'rssi': device['rssi'],
                    'name': device['name']
                }
                success = await self._bluetooth_controller.connect_device(device_info)
            else:
                logger.info("开始扫描并连接DG-LAB蓝牙设备...")
                # 自动扫描并连接
                success = await self._bluetooth_controller.connect_device(None)
            
            if success:
                logger.info("蓝牙设备连接成功")
                return True
            else:
                logger.error("蓝牙设备连接失败")
                return False
            
        except Exception as e:
            logger.error(f"连接设备失败: {e}")
            return False

    async def disconnect_device(self) -> bool:
        """断开设备连接"""
        return await self._disconnect_device()

    def is_device_connected(self) -> bool:
        """检查设备是否已连接"""
        return self._is_connected and self._bluetooth_controller.is_connected

    # ============ 内部实现方法 ============

    async def _disconnect_device(self) -> bool:
        """内部断开设备连接方法"""
        try:
            success: bool = await self._bluetooth_controller.disconnect_device()
            
            if success:
                logger.info("蓝牙设备已断开连接")
                return True
            else:
                logger.error("断开蓝牙设备失败")
                return False
            
        except Exception as e:
            logger.error(f"断开蓝牙设备失败: {e}")
            return False

    async def _attempt_reconnect(self) -> None:
        """无限尝试重连设备（不等待）"""
        attempt = 1
        while True:
            try:
                logger.info(f"重连尝试 {attempt}")
                # 立即尝试重连到上次连接的设备
                success = await self._bluetooth_controller.connect_device(None)
                if success:
                    logger.info("重连成功")
                    return
                else:
                    logger.warning(f"重连尝试 {attempt} 失败")
            except Exception as e:
                logger.error(f"重连尝试 {attempt} 异常: {e}")
            attempt += 1

    async def _initialize_device(self) -> None:
        """初始化设备设置"""
        try:
            logger.info("正在初始化设备...")
            
            # 发送BF指令设置设备参数
            success: bool = await self._update_device_params()

            if success:
                # 获取设备状态
                device_state: bluetooth.DeviceState = self._bluetooth_controller.get_device_state()
                self._current_strengths[Channel.A] = device_state['channel_a']['strength']
                self._current_strengths[Channel.B] = device_state['channel_b']['strength']
                
                # 更新强度数据
                self._last_strength = {
                    "strength": self._current_strengths.copy(),
                    "strength_limit": self._strength_limits.copy()
                }
                
                # 通知UI更新强度上限和当前强度
                self._core_interface.on_strength_data_updated(self._last_strength)
                
                # 查询电量
                await self._bluetooth_controller.query_battery_level()
                
                logger.info(f"设备初始化完成")
            else:
                logger.error("设备初始化失败")
            
        except Exception as e:
            logger.error(f"初始化设备失败: {e}")

    async def _update_device_params(self) -> bool:
        """更新设备参数到硬件"""
        try:
            if not self._is_connected:
                logger.warning("设备未连接，无法更新设备参数")
                return False
            
            logger.debug("正在更新设备参数...")
            
            # 发送BF指令更新设备参数
            success: bool = await self._bluetooth_controller.set_device_params(
                strength_limit_a=self._strength_limits[Channel.A],
                strength_limit_b=self._strength_limits[Channel.B],
                freq_balance_a=self._freq_balances[Channel.A],
                freq_balance_b=self._freq_balances[Channel.B],
                strength_balance_a=self._strength_balances[Channel.A],
                strength_balance_b=self._strength_balances[Channel.B]
            )
            
            if success:
                logger.debug("设备参数更新成功")
            else:
                logger.warning("设备参数更新失败")
            
            return success
        except Exception as e:
            logger.error(f"更新设备参数失败: {e}")
            return False

    def _convert_channel(self, channel: Channel) -> bluetooth.Channel:
        """转换模型通道到蓝牙通道"""
        if channel == Channel.A:
            return bluetooth.Channel.A
        else:
            return bluetooth.Channel.B

    def _convert_pulse_operations(self, operations: List[PulseOperation]) -> List[bluetooth.PulseOperation]:
        """将PulseOperation转换为频率和强度数组"""
        return operations