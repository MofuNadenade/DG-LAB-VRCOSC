"""
DG-LAB 蓝牙直连服务实现

基于pydglab库实现的蓝牙直连设备服务，实现IDGLabDeviceService接口。
只负责设备连接和基础硬件操作，不包含任何业务逻辑。
"""

import asyncio
import logging
from typing import Optional, List, Dict, TypedDict

from pydglab import model_v3, dglab_v3, bthandler_v3

from core.dglab_pulse import Pulse
from models import Channel, StrengthData, StrengthOperationType, PulseOperation
from services.dglab_service_interface import IDGLabDeviceService

logger = logging.getLogger(__name__)


class DGLabDevice(TypedDict):
    """设备信息类型定义"""
    address: str
    rssi: int


class DGLabBluetoothService(IDGLabDeviceService):
    """DG-LAB蓝牙直连服务
    
    纯粹的蓝牙设备硬件通信实现，只负责：
    1. 蓝牙设备连接管理
    2. 基础强度操作
    3. 波形数据传输
    4. 设备状态查询
    
    不包含任何业务逻辑，所有业务逻辑由OSCActionService处理。
    """

    def __init__(self) -> None:
        """初始化蓝牙服务"""
        super().__init__()
        
        # 蓝牙连接管理
        self._dglab_instance: Optional[dglab_v3] = None
        self._is_connected: bool = False
        
        # 服务状态
        self._server_running: bool = False
        self._stop_event: asyncio.Event = asyncio.Event()
        
        # 强度数据缓存
        self._last_strength: Optional[StrengthData] = None
        self._current_strengths: Dict[Channel, int] = {Channel.A: 0, Channel.B: 0}
        
        # 设备参数
        self._strength_limit: int = 200
        self._strength_coefficient: int = 100
        self._frequency_coefficient: int = 100
        
        logger.info("蓝牙服务已初始化")

    # ============ 连接管理 ============

    async def start_service(self) -> bool:
        """启动设备连接服务"""
        try:
            logger.info("开始启动蓝牙服务...")
            self._server_running = True
            self._stop_event.clear()
            
            # 蓝牙服务启动成功
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
        if not self._is_connected or not self._dglab_instance:
            logger.warning("设备未连接，无法设置浮点输出强度")
            return
        
        try:
            # 将浮点值转换为强度值（0-强度上限范围）
            strength = int(value * self._strength_limit)
            strength = max(0, min(self._strength_limit, strength))
            
            await self._set_channel_strength(channel, strength)
            logger.debug(f"蓝牙浮点输出: 通道{channel}强度设置为{strength}")
            
        except Exception as e:
            logger.error(f"设置浮点输出强度失败: {e}")

    async def adjust_strength(self, operation_type: StrengthOperationType, value: int, channel: Channel) -> None:
        """调整通道强度（原始设备操作）"""
        if not self._is_connected or not self._dglab_instance:
            logger.warning("设备未连接，无法调整强度")
            return
        
        try:
            current_strength = self._current_strengths[channel]
            target_strength: int
            
            if operation_type == StrengthOperationType.SET_TO:
                target_strength = value
            elif operation_type == StrengthOperationType.INCREASE:
                target_strength = current_strength + value
            elif operation_type == StrengthOperationType.DECREASE:
                target_strength = current_strength - value
            
            # 限制强度范围
            target_strength = max(0, min(self._strength_limit, target_strength))
            
            await self._set_channel_strength(channel, target_strength)
            logger.debug(f"蓝牙调整强度: 通道{channel} {operation_type} {value} -> {target_strength}")
            
        except Exception as e:
            logger.error(f"调整通道强度失败: {e}")

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
        if not self._is_connected or not self._dglab_instance:
            logger.warning("设备未连接，无法设置波形数据")
            return
        if pulse:
            await self._send_pulse_data(channel, pulse.data)

    # ============ 数据访问 ============

    def get_last_strength(self) -> Optional[StrengthData]:
        """获取最后的强度数据"""
        return self._last_strength

    def update_strength_data(self, strength_data: StrengthData) -> None:
        """更新强度数据（通常由连接层调用）"""
        self._last_strength = strength_data
        self._current_strengths[Channel.A] = strength_data['strength'][Channel.A]
        self._current_strengths[Channel.B] = strength_data['strength'][Channel.B]

    # ============ 公共设备管理方法 ============

    async def scan_devices(self) -> List[DGLabDevice]:
        """
        扫描可用的DG-LAB v3.0设备
        
        Returns:
            List[DGLabDevice]: 设备信息列表，包含address和rssi字段
        """
        try:
            logger.info("开始扫描可用的DG-LAB v3.0设备...")
            
            # 使用pydglab的扫描API
            devices = await bthandler_v3.scan()
            
            # 转换为DeviceInfo格式
            device_list: List[DGLabDevice] = []
            for address, rssi in devices:
                device_info: DGLabDevice = {
                    "address": address,
                    "rssi": rssi
                }
                device_list.append(device_info)
            
            logger.info(f"扫描完成，发现 {len(device_list)} 个设备")
            return device_list
            
        except Exception as e:
            logger.error(f"扫描设备失败: {e}")
            return []

    async def connect_device(self, device: Optional[DGLabDevice] = None) -> bool:
        """
        连接到DG-LAB设备
        
        Args:
            device (DeviceInfo, optional): 指定设备信息，如果为None则扫描并连接第一个可用设备
            
        Returns:
            bool: 连接是否成功
        """
        try:
            if device:
                logger.info(f"尝试连接到指定设备: {device['address']}")
                # 断开现有连接
                if self._is_connected:
                    await self._disconnect_device()
                # 使用指定地址创建dglab_v3实例
                self._dglab_instance = await dglab_v3.from_address(device['address'])
            else:
                logger.info("开始扫描DG-LAB蓝牙设备...")
                # 扫描设备
                await bthandler_v3.scan()
                # 创建dglab_v3实例
                self._dglab_instance = dglab_v3()
            
            # 尝试连接设备
            try:
                await self._dglab_instance.create()
            except TimeoutError:
                logger.warning("连接超时，重试中...")
                await self._dglab_instance.create()
            
            self._is_connected = True
            
            # 初始化设备设置
            await self._initialize_device()
            
            if device:
                logger.info(f"成功连接到设备: {device['address']}")
            else:
                logger.info("蓝牙设备连接成功")
            return True
            
        except Exception as e:
            if device:
                logger.error(f"连接到指定设备失败 {device['address']}: {e}")
            else:
                logger.error(f"蓝牙设备连接失败: {e}")
            await self._cleanup_connection()
            return False

    async def disconnect_device(self) -> bool:
        """断开设备连接"""
        return await self._disconnect_device()

    def is_device_connected(self) -> bool:
        """检查设备是否已连接"""
        return self._is_connected and self._dglab_instance is not None

    # ============ 内部实现方法 ============

    async def _disconnect_device(self) -> bool:
        """内部断开设备连接方法"""
        try:
            if self._dglab_instance:
                await self._dglab_instance.close()
            
            await self._cleanup_connection()
            logger.info("蓝牙设备已断开连接")
            return True
            
        except Exception as e:
            logger.error(f"断开蓝牙设备失败: {e}")
            return False

    async def _cleanup_connection(self) -> None:
        """清理连接资源"""
        self._dglab_instance = None
        self._is_connected = False
        self._current_strengths = {Channel.A: 0, Channel.B: 0}
        self._last_strength = None

    async def _initialize_device(self) -> None:
        """初始化设备设置"""
        if not self._dglab_instance:
            return
        
        try:
            # 设置系数 (强度上限, 强度系数, 频率系数)
            await self._dglab_instance.set_coefficient(
                self._strength_limit, 
                self._strength_coefficient, 
                self._frequency_coefficient, 
                model_v3.ChannelA  # type: ignore
            )
            await self._dglab_instance.set_coefficient(
                self._strength_limit, 
                self._strength_coefficient, 
                self._frequency_coefficient, 
                model_v3.ChannelB  # type: ignore
            )
            
            # 获取当前强度
            strength_a, strength_b = await self._dglab_instance.get_strength()
            self._current_strengths[Channel.A] = strength_a
            self._current_strengths[Channel.B] = strength_b
            
            # 更新强度数据
            self._last_strength = {
                "strength": {Channel.A: strength_a, Channel.B: strength_b},
                "strength_limit": {Channel.A: self._strength_limit, Channel.B: self._strength_limit}
            }
            
            # 初始化波形为静止状态
            await self._dglab_instance.set_wave_sync(0, 0, 0, 0, 0, 0)
            
            logger.info(f"设备初始化完成 - 当前强度 A:{strength_a}, B:{strength_b}")
            
        except Exception as e:
            logger.error(f"初始化设备设置失败: {e}")

    async def _set_channel_strength(self, channel: Channel, strength: int) -> None:
        """设置指定通道的强度"""
        if not self._dglab_instance:
            return
        
        try:
            # 更新内部状态
            self._current_strengths[channel] = strength
            
            # 同步设置两个通道的强度
            await self._dglab_instance.set_strength_sync(
                self._current_strengths[Channel.A], 
                self._current_strengths[Channel.B]
            )
            
            # 更新强度数据
            self._last_strength = {
                "strength": {Channel.A: self._current_strengths[Channel.A], Channel.B: self._current_strengths[Channel.B]},
                "strength_limit": {Channel.A: self._strength_limit, Channel.B: self._strength_limit}
            }
            
        except Exception as e:
            logger.error(f"设置通道强度失败: {e}")

    async def _send_pulse_data(self, channel: Channel, data: List[PulseOperation]) -> None:
        """发送波形数据到设备"""
        if not self._dglab_instance:
            return
        
        try:
            # 将PulseOperation转换为pydglab的波形格式
            wave_set = self._convert_pulse_operations_to_wave_set(data)
            
            # 根据通道设置波形
            if channel == Channel.A:
                await self._dglab_instance.set_wave_set(wave_set, model_v3.ChannelA)  # type: ignore 
            else:
                await self._dglab_instance.set_wave_set(wave_set, model_v3.ChannelB)  # type: ignore
            
            logger.debug(f"蓝牙发送波形数据到通道{channel}: {len(data)}个操作")
            
        except Exception as e:
            logger.error(f"蓝牙发送波形数据失败: {e}")

    def _convert_pulse_operations_to_wave_set(self, operations: List[PulseOperation]) -> List[tuple[int, int, int]]:
        """将PulseOperation转换为pydglab的波形集合格式"""
        wave_set: List[tuple[int, int, int]] = []
        
        for op in operations:
            # 从PulseOperation中提取参数
            # PulseOperation是(freq_op, strength_op)的元组
            freq_op, strength_op = op
            
            # 提取频率和强度值（取第一个值作为代表）
            frequency = freq_op[0] if freq_op else 10
            strength = strength_op[0] if strength_op else 0
            
            # 转换为pydglab的波形格式 (waveX, waveY, waveZ)
            # waveX: 连续发出X个脉冲，每个脉冲持续1ms
            # waveY: 发出脉冲后停止Y个周期，每个周期持续1ms  
            # waveZ: 每个脉冲的宽度为Z*5us
            wave_x = min(max(1, frequency), 100)
            wave_y = min(max(1, 100), 1000)  # 固定持续时间
            wave_z = min(max(1, strength // 5), 200)
            
            wave_set.append((wave_x, wave_y, wave_z))
        
        # 如果没有有效的波形数据，返回静止波形
        if not wave_set:
            wave_set = [(0, 0, 0)]
        
        return wave_set