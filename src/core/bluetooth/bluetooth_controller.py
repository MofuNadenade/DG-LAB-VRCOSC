"""
DG-LAB V3蓝牙控制器

业务控制层，封装Protocol和蓝牙通信，负责：
1. 设备连接管理
2. 业务逻辑处理
3. 状态管理
4. 序列号管理
5. 定时数据发送
6. 回调处理
"""

import asyncio
import logging
import time
from typing import Optional, Callable, Awaitable, Dict, List, Tuple
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

from .bluetooth_models import (
    DeviceInfo, Channel, DeviceState, BluetoothUUIDs, PulseOperation, StrengthParsingMethod,
    SequenceState 
)
from .bluetooth_protocol import BluetoothProtocol

logger = logging.getLogger(__name__)


class BluetoothController:
    """DG-LAB V3蓝牙控制器
    
    业务控制层，负责：
    1. 设备连接和管理
    2. 业务逻辑处理
    3. 状态管理和同步
    4. 定时数据发送
    5. 序列号管理
    6. 回调处理
    """
    
    def __init__(self) -> None:
        """初始化蓝牙控制器"""
        super().__init__()
        # 协议处理器
        self._protocol = BluetoothProtocol()
        
        # 蓝牙连接
        self._client: Optional[BleakClient] = None
        self._is_connected = False
        self._current_device: Optional[DeviceInfo] = None
        
        # GATT特性对象缓存
        self._write_characteristic: Optional[BleakGATTCharacteristic] = None
        self._notify_characteristic: Optional[BleakGATTCharacteristic] = None
        self._battery_characteristic: Optional[BleakGATTCharacteristic] = None
        
        # 设备状态
        self._device_state: DeviceState = self._create_device_state()
        self._sequence_state: SequenceState = self._create_sequence_state()
        
        # 波形数据管理 - 强类型标记
        self._pulse_data_a: List[PulseOperation] = []
        self._pulse_data_b: List[PulseOperation] = []
        self._pulse_index_a: int = 0
        self._pulse_index_b: int = 0
        
        # 定时任务
        self._data_send_task: Optional[asyncio.Task[None]] = None
        self._connection_monitor_task: Optional[asyncio.Task[None]] = None
        self._is_running = False
        self._monitor_interval = 5.0
        
        # 回调函数
        self._on_notification: Optional[Callable[[bytes], Awaitable[None]]] = None
        self._on_connection_changed: Optional[Callable[[bool], Awaitable[None]]] = None
        self._on_strength_changed: Optional[Callable[[Dict[Channel, int]], Awaitable[None]]] = None
        self._on_battery_changed: Optional[Callable[[int], Awaitable[None]]] = None
        
        logger.info("V3蓝牙控制器已初始化")
    
    # ============ 公共接口 ============
    
    def set_notification_callback(self, callback: Callable[[bytes], Awaitable[None]]) -> None:
        """设置通知回调"""
        self._on_notification = callback
    
    def set_connection_callback(self, callback: Callable[[bool], Awaitable[None]]) -> None:
        """设置连接状态变化回调"""
        self._on_connection_changed = callback
    
    def set_strength_changed_callback(self, callback: Callable[[Dict[Channel, int]], Awaitable[None]]) -> None:
        """设置强度变化回调"""
        self._on_strength_changed = callback
    
    def set_battery_callback(self, callback: Callable[[int], Awaitable[None]]) -> None:
        """设置电量变化回调"""
        self._on_battery_changed = callback
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._is_connected and self._client is not None and self._client.is_connected
    
    @property
    def current_device(self) -> Optional[DeviceInfo]:
        """获取当前连接的设备信息"""
        return self._current_device
    
    def get_device_state(self) -> DeviceState:
        """获取设备状态"""
        return self._device_state
    
    # ============ 设备管理 ============
    
    async def scan_devices(self, scan_time: float = 5.0) -> List[DeviceInfo]:
        """扫描可用的DG-LAB V3设备"""
        try:
            logger.info(f"开始扫描DG-LAB V3设备，扫描时间: {scan_time}秒")
            
            # 执行蓝牙扫描
            devices = await BleakScanner.discover(timeout=scan_time, return_adv=True) # type: ignore
            
            # 筛选DG-LAB V3设备
            dglab_devices: List[DeviceInfo] = []
            for device_and_adv in devices.values():
                device, adv_data = device_and_adv
                
                # 检查设备名称
                if (adv_data.local_name == BluetoothUUIDs.DEVICE_NAME or 
                    adv_data.local_name == BluetoothUUIDs.WIRELESS_SENSOR_NAME):
                    
                    device_info = self._create_device_info(
                        address=device.address,
                        rssi=adv_data.rssi,
                        name=adv_data.local_name or "Unknown"
                    )
                    dglab_devices.append(device_info)
                    logger.info(f"发现DG-LAB V3设备: {device_info['name']} ({device_info['address']}), RSSI: {device_info['rssi']}")
            
            if not dglab_devices:
                logger.warning("未发现任何DG-LAB V3设备")
            else:
                logger.info(f"扫描完成，共发现 {len(dglab_devices)} 个设备")
            
            # 按RSSI排序（信号强度从强到弱）
            dglab_devices.sort(key=lambda d: d['rssi'], reverse=True)
            return dglab_devices
            
        except Exception as e:
            logger.error(f"扫描设备失败: {e}")
            return []
    
    async def connect_device(self, device: Optional[DeviceInfo] = None, timeout: float = 20.0) -> bool:
        """连接到DG-LAB V3设备"""
        try:
            # 断开现有连接
            if self.is_connected:
                await self.disconnect_device()
            
            # 获取目标设备
            target_device = device
            if target_device is None:
                logger.info("未指定设备，开始自动扫描...")
                devices = await self.scan_devices()
                if not devices:
                    logger.error("未找到可连接的DG-LAB V3设备")
                    return False
                target_device = devices[0]
            
            logger.info(f"尝试连接设备: {target_device['name']} ({target_device['address']})")
            
            # 创建BleakClient并连接
            self._client = BleakClient(target_device['address'], timeout=timeout)
            await self._client.connect() # type: ignore
            
            # 等待服务发现完成
            await asyncio.sleep(1.0)
            
            # 验证设备服务
            if not await self._validate_device_services():
                logger.error("设备服务验证失败")
                await self._cleanup_connection()
                return False
            
            # 缓存GATT特性
            if not await self._cache_characteristics():
                logger.error("缓存GATT特性失败")
                await self._cleanup_connection()
                return False
            
            # 设置通知
            if not await self._setup_notifications():
                logger.error("设置通知失败")
                await self._cleanup_connection()
                return False
            
            # 更新连接状态
            self._is_connected = True
            self._current_device = target_device
            self._device_state['is_connected'] = True
            
            # 启动服务
            await self._start_services()
            
            # 触发连接状态回调
            if self._on_connection_changed:
                await self._on_connection_changed(True)
            
            logger.info(f"成功连接到设备: {target_device['name']} ({target_device['address']})")
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error(f"连接设备失败: {e}")
            await self._cleanup_connection()
            return False
    
    async def disconnect_device(self) -> bool:
        """断开设备连接"""
        try:
            if not self._is_connected:
                return True
            
            logger.info("正在断开设备连接...")
            
            # 停止服务
            await self._stop_services()
            
            # 断开蓝牙连接
            if self._client and self._client.is_connected:
                await self._client.disconnect()
            
            # 清理连接状态
            await self._cleanup_connection()
            
            # 触发连接状态回调
            if self._on_connection_changed:
                await self._on_connection_changed(False)
            
            logger.info("设备连接已断开")
            return True
            
        except Exception as e:
            logger.error(f"断开连接失败: {e}")
            await self._cleanup_connection()
            return False
    
    # ============ 设备参数控制 ============
    
    async def set_device_params(self, strength_limit_a: int = 200, strength_limit_b: int = 200,
                                       freq_balance_a: int = 100, freq_balance_b: int = 100,
                                       strength_balance_a: int = 100, strength_balance_b: int = 100) -> bool:
        """设置设备参数（每次重连后必须调用）"""
        try:
            if not self.is_connected:
                logger.error("设备未连接，无法设置设备参数")
                return False
            
            # 构建BF指令
            bf_data = self._protocol.build_bf_command(
                strength_limit_a, strength_limit_b,
                freq_balance_a, freq_balance_b,
                strength_balance_a, strength_balance_b
            )
            
            if bf_data is None:
                logger.error("BF指令参数验证失败")
                return False
            
            # 发送BF指令
            success = await self._send_data(bf_data)
            if success:
                # 更新设备状态
                self._device_state['channel_a']['strength_limit'] = strength_limit_a
                self._device_state['channel_b']['strength_limit'] = strength_limit_b
                self._device_state['channel_a']['frequency_balance'] = freq_balance_a
                self._device_state['channel_b']['frequency_balance'] = freq_balance_b
                self._device_state['channel_a']['strength_balance'] = strength_balance_a
                self._device_state['channel_b']['strength_balance'] = strength_balance_b
                
                logger.info(f"设备参数初始化成功: A上限={strength_limit_a}, B上限={strength_limit_b}, A频率平衡={freq_balance_a}, B频率平衡={freq_balance_b}, A强度平衡={strength_balance_a}, B强度平衡={strength_balance_b}")
                return True
            else:
                logger.error("发送BF指令失败")
                return False
            
        except Exception as e:
            logger.error(f"设备参数设置失败: {e}")
            return False
    
    # ============ 强度控制 ============
    
    async def set_strength_absolute(self, channel: Channel, strength: int) -> bool:
        """设置绝对强度值"""
        try:
            if not self.is_connected:
                logger.warning("设备未连接，无法设置强度")
                return False
            
            if not self._protocol.validate_strength(strength):
                logger.error(f"强度值超出范围: {strength}")
                return False
            
            # 检查是否允许输入
            if not self._sequence_state['is_input_allowed']:
                logger.warning("当前不允许强度输入，等待设备回应")
                return False
            
            # 计算强度变化
            current_strength = self._get_current_strength(channel)
            delta = strength - current_strength
            
            # 累积强度变化
            self._sequence_state['accumulated_changes'][channel] = delta
            
            logger.debug(f"设置{channel}通道绝对强度: {current_strength} -> {strength} (变化: {delta})")
            return True
            
        except Exception as e:
            logger.error(f"设置绝对强度失败: {e}")
            return False
    
    async def set_strength_relative(self, channel: Channel, delta: int) -> bool:
        """相对调整强度"""
        try:
            if not self.is_connected:
                logger.warning("设备未连接，无法调整强度")
                return False
            
            # 检查是否允许输入
            if not self._sequence_state['is_input_allowed']:
                logger.warning("当前不允许强度输入，等待设备回应")
                return False
            
            # 累积强度变化
            self._sequence_state['accumulated_changes'][channel] += delta
            
            logger.debug(f"调整{channel}通道相对强度: {delta} (累积: {self._sequence_state['accumulated_changes'][channel]})")
            return True
            
        except Exception as e:
            logger.error(f"相对调整强度失败: {e}")
            return False
    
    async def reset_strength(self, channel: Channel) -> bool:
        """重置通道强度为0"""
        return await self.set_strength_absolute(channel, 0)
    
    # ============ 波形控制 ============
    
    async def set_pulse_data(self, channel: Channel, pulses: List[PulseOperation]) -> bool:
        """设置通道波形数据
        
        Args:
            channel: 目标通道
            pulses: 波形操作数据
        """
        try:
            if not self.is_connected:
                logger.warning("设备未连接，无法设置波形数据")
                return False

            # 验证所有脉冲操作的频率和强度范围
            for pulse in pulses:
                # 验证频率范围
                for freq in pulse[0]:
                    if not self._protocol.validate_pulse_frequency(freq):
                        logger.error(f"波形频率超出范围 (10-240): {freq}")
                        return False
                
                # 验证强度范围  
                for strength in pulse[1]:
                    if not self._protocol.validate_pulse_strength(strength):
                        logger.error(f"波形强度超出范围 (0-100): {strength}")
                        return False
            
            # 存储波形数据到对应通道
            if channel == Channel.A:
                self._pulse_data_a = pulses.copy()
                self._pulse_index_a = 0
                self._device_state['channel_a']['pulses'] = pulses.copy()
            elif channel == Channel.B:
                self._pulse_data_b = pulses.copy()
                self._pulse_index_b = 0
                self._device_state['channel_b']['pulses'] = pulses.copy()
            
            logger.debug(f"设置{channel}通道波形数据，共{len(pulses)}个脉冲操作")
            return True
            
        except Exception as e:
            logger.error(f"设置波形数据失败: {e}")
            return False
    
    async def clear_pulse_data(self, channel: Channel) -> bool:
        """清除通道波形数据（设置为静止状态）"""
        if channel == Channel.A:
            self._pulse_data_a.clear()
            self._pulse_index_a = 0
            self._device_state['channel_a']['pulses'].clear()
        elif channel == Channel.B:
            self._pulse_data_b.clear()
            self._pulse_index_b = 0
            self._device_state['channel_b']['pulses'].clear()
        
        logger.debug(f"清除{channel}通道波形数据")
        return True
    
    # ============ 内部实现 ============

    def _create_device_state(self) -> DeviceState:
        """创建设备状态"""
        return {
            'channel_a': {
                'strength': 0,
                'strength_limit': 200,
                'frequency_balance': 100,
                'strength_balance': 100,
                'pulses': []
            },
            'channel_b': {
                'strength': 0,
                'strength_limit': 200,
                'frequency_balance': 100,
                'strength_balance': 100,
                'pulses': []
            },
            'is_connected': False,
            'battery_level': 0
        }

    def _create_sequence_state(self) -> SequenceState:
        """创建序列号状态"""
        return {
            'current_no': 0,
            'pending_no': None,
            'is_input_allowed': True,
            'accumulated_changes': {Channel.A: 0, Channel.B: 0},
            'response_timeout': 1.0,
            'last_send_time': None
        }

    def _create_device_info(self, address: str, rssi: int, name: str) -> DeviceInfo:
        """创建设备信息"""
        return {
            'address': address,
            'rssi': rssi,
            'name': name
        }
    
    def _get_current_strength(self, channel: Channel) -> int:
        """获取通道当前强度"""
        if channel == Channel.A:
            return self._device_state['channel_a']['strength']
        else:
            return self._device_state['channel_b']['strength']
    
    async def _send_data(self, data: bytes) -> bool:
        """发送数据到设备"""
        try:
            if not self.is_connected or not self._write_characteristic:
                logger.error("设备未连接或写入特性不可用")
                return False
            
            if self._client:
                await self._client.write_gatt_char(self._write_characteristic, data)
            logger.debug(f"发送数据: {data.hex().upper()}")
            return True
            
        except Exception as e:
            logger.error(f"发送数据失败: {e}")
            return False
    
    async def _validate_device_services(self) -> bool:
        """验证设备服务"""
        try:
            if not self._client:
                return False
            services = self._client.services
            service_uuids = [service.uuid for service in services]
            
            # 检查必需的服务
            if (BluetoothUUIDs.SERVICE_WRITE not in service_uuids or
                BluetoothUUIDs.SERVICE_NOTIFY not in service_uuids):
                logger.error("设备缺少必需的服务")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"验证设备服务失败: {e}")
            return False
    
    async def _cache_characteristics(self) -> bool:
        """缓存GATT特性对象"""
        try:
            if not self._client:
                return False
            
            # 查找并缓存特性
            for service in self._client.services:
                for char in service.characteristics:
                    if char.uuid == BluetoothUUIDs.CHARACTERISTIC_WRITE:
                        self._write_characteristic = char
                        logger.debug("已缓存写入特性")
                    elif char.uuid == BluetoothUUIDs.CHARACTERISTIC_NOTIFY:
                        self._notify_characteristic = char
                        logger.debug("已缓存通知特性")
                    elif char.uuid == BluetoothUUIDs.CHARACTERISTIC_BATTERY:
                        self._battery_characteristic = char
                        logger.debug("已缓存电量特性")
            
            # 验证必需特性
            if not self._write_characteristic:
                logger.error("未找到写入特性")
                return False
            
            if not self._notify_characteristic:
                logger.error("未找到通知特性")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"缓存特性失败: {e}")
            return False
    
    async def _setup_notifications(self) -> bool:
        """设置通知"""
        try:
            if not self._notify_characteristic:
                logger.error("通知特性不可用")
                return False
            
            # 启动通知
            if self._client:
                await self._client.start_notify(self._notify_characteristic, self._on_notification_received) # type: ignore
            logger.debug("已启动通知")
            
            # 如果有电量特性，也启动电量通知
            if self._battery_characteristic:
                try:
                    if self._client:
                        await self._client.start_notify(self._battery_characteristic, self._on_battery_notification) # type: ignore
                    logger.debug("已启动电量通知")
                except Exception as e:
                    logger.warning(f"启动电量通知失败: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"设置通知失败: {e}")
            return False
    
    async def _on_notification_received(self, sender: BleakGATTCharacteristic, data: bytearray) -> None:
        """处理接收到的通知"""
        try:
            logger.debug(f"收到通知: {data.hex().upper()}")
            
            # 处理B1回应
            if len(data) >= 4 and data[0] == 0xB1:
                await self._handle_b1_response(bytes(data))
            
            # 触发通知回调
            if self._on_notification:
                await self._on_notification(bytes(data))
                
        except Exception as e:
            logger.error(f"处理通知失败: {e}")
    
    async def _on_battery_notification(self, sender: BleakGATTCharacteristic, data: bytearray) -> None:
        """处理电量通知"""
        try:
            battery_level = int.from_bytes(data, byteorder='little')
            logger.debug(f"电量通知: {battery_level}%")
            
            self._device_state['battery_level'] = battery_level
            
            if self._on_battery_changed:
                await self._on_battery_changed(battery_level)
                
        except Exception as e:
            logger.error(f"处理电量通知失败: {e}")
    
    async def _handle_b1_response(self, data: bytes) -> None:
        """处理B1回应消息"""
        try:
            response = self._protocol.parse_b1_response(data)
            if not response:
                return
            
            # 更新设备强度状态
            self._device_state['channel_a']['strength'] = response['strength_a']
            self._device_state['channel_b']['strength'] = response['strength_b']
            
            # 处理序列号回应
            if response['sequence_no'] == self._sequence_state['pending_no']:
                # 收到期待的回应，允许下次输入
                self._sequence_state['is_input_allowed'] = True
                self._sequence_state['pending_no'] = None
                logger.debug(f"收到B1回应: 序列号={response['sequence_no']}, 强度A={response['strength_a']}, B={response['strength_b']}")
            elif response['sequence_no'] == 0:
                # 设备主动报告强度变化（如通过拨轮调节）
                logger.debug(f"设备主动报告强度变化: A={response['strength_a']}, B={response['strength_b']}")
            else:
                logger.warning(f"收到意外的B1回应序列号: {response['sequence_no']}, 期待: {self._sequence_state['pending_no']}")
            
            # 触发强度变化回调
            if self._on_strength_changed:
                strength_dict = {Channel.A: response['strength_a'], Channel.B: response['strength_b']}
                await self._on_strength_changed(strength_dict)
                
        except Exception as e:
            logger.error(f"处理B1回应失败: {e}")
    
    async def _start_services(self) -> None:
        """启动服务"""
        if self._is_running:
            return
        
        self._is_running = True
        
        # 让出控制权到事件循环，避免在当前任务执行期间创建新任务导致冲突
        await asyncio.sleep(0)
        
        # 启动数据发送任务
        self._data_send_task = asyncio.create_task(self._data_send_loop())
        
        # 启动连接监控任务
        self._connection_monitor_task = asyncio.create_task(self._connection_monitor_loop())
        
        logger.debug("控制器服务已启动")
    
    async def _stop_services(self) -> None:
        """停止服务"""
        if not self._is_running:
            return
        
        self._is_running = False
        
        # 停止数据发送任务
        if self._data_send_task:
            self._data_send_task.cancel()
            try:
                await self._data_send_task
            except asyncio.CancelledError:
                pass
            self._data_send_task = None
        
        # 停止连接监控任务
        if self._connection_monitor_task:
            self._connection_monitor_task.cancel()
            try:
                await self._connection_monitor_task
            except asyncio.CancelledError:
                pass
            self._connection_monitor_task = None
        
        logger.debug("控制器服务已停止")
    
    async def _data_send_loop(self) -> None:
        """数据发送循环（每100ms发送一次B0指令）"""
        while self._is_running:
            try:
                await self._process_and_send_b0_command()
                await asyncio.sleep(0.1)  # 100ms
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"数据发送循环错误: {e}")
                await asyncio.sleep(0.1)

    def _next_pulse_data(self, channel: Channel) -> PulseOperation:
        """获取当前波形数据（循环播放）

        Args:
            channel: 目标通道

        Returns:
            当前波形的频率和强度操作数据
        """
        if channel == Channel.A:
            if not self._pulse_data_a:
                # 返回静止状态的默认波形数据
                return ((10, 10, 10, 10), (0, 0, 0, 0))

            current_pulse = self._pulse_data_a[self._pulse_index_a]
            self._pulse_index_a = (self._pulse_index_a + 1) % len(self._pulse_data_a)
            return current_pulse

        elif channel == Channel.B:
            if not self._pulse_data_b:
                # 返回静止状态的默认波形数据
                return ((10, 10, 10, 10), (0, 0, 0, 0))

            current_pulse = self._pulse_data_b[self._pulse_index_b]
            self._pulse_index_b = (self._pulse_index_b + 1) % len(self._pulse_data_b)
            return current_pulse

        # 默认返回静止状态
        return ((10, 10, 10, 10), (0, 0, 0, 0))

    async def _process_and_send_b0_command(self) -> None:
        """处理并发送B0指令"""
        try:
            # 处理强度数据
            strength_parsing_method, strength_a, strength_b, sequence_no = self._process_strength_data()
            
            # 获取当前脉冲数据（循环播放）
            pulse_freq_a, pulse_strength_a = self._next_pulse_data(Channel.A)
            pulse_freq_b, pulse_strength_b = self._next_pulse_data(Channel.B)
            
            # 构建B0指令
            b0_data = self._protocol.build_b0_command(
                sequence_no=sequence_no,
                strength_parsing_method=strength_parsing_method,
                strength_a=strength_a,
                strength_b=strength_b,
                pulse_freq_a=pulse_freq_a,
                pulse_strength_a=pulse_strength_a,
                pulse_freq_b=pulse_freq_b,
                pulse_strength_b=pulse_strength_b
            )
            
            if b0_data is not None:
                # 发送数据
                await self._send_data(b0_data)
            else:
                logger.error("B0指令参数验证失败，跳过发送")
            
            self._sequence_state['last_send_time'] = time.time()
            
        except Exception as e:
            logger.error(f"处理B0指令失败: {e}")
    
    def _process_strength_data(self) -> Tuple[int, int, int, int]:
        """处理强度数据并返回B0指令参数"""
        if not self._sequence_state['is_input_allowed']:
            # 不允许输入时，发送无变化数据
            return 0b0000, 0, 0, 0
        
        # 检查是否有累积的强度变化
        change_a = self._sequence_state['accumulated_changes'][Channel.A]
        change_b = self._sequence_state['accumulated_changes'][Channel.B]
        
        if change_a == 0 and change_b == 0:
            # 无强度变化
            return 0b0000, 0, 0, 0
        
        # 有强度变化，生成序列号并处理
        self._sequence_state['current_no'] = (self._sequence_state['current_no'] % 15) + 1
        sequence_no = self._sequence_state['current_no']
        self._sequence_state['pending_no'] = sequence_no
        self._sequence_state['is_input_allowed'] = False
        
        # 确定强度解读方式和强度值
        method_a = self._get_strength_parsing_method(change_a)
        method_b = self._get_strength_parsing_method(change_b)
        strength_parsing_method = self._protocol.build_strength_parsing_method(method_a, method_b)
        
        strength_a = abs(change_a)
        strength_b = abs(change_b)
        
        # 清除累积变化
        self._sequence_state['accumulated_changes'][Channel.A] = 0
        self._sequence_state['accumulated_changes'][Channel.B] = 0
        
        logger.debug(f"处理强度数据: 方式={strength_parsing_method:04b}, A={strength_a}, B={strength_b}, 序列号={sequence_no}")
        return strength_parsing_method, strength_a, strength_b, sequence_no
    
    def _get_strength_parsing_method(self, change: int) -> StrengthParsingMethod:
        """根据强度变化值确定解读方式"""
        if change > 0:
            return StrengthParsingMethod.INCREASE
        elif change < 0:
            return StrengthParsingMethod.DECREASE
        else:
            return StrengthParsingMethod.NO_CHANGE
    
    async def _connection_monitor_loop(self) -> None:
        """连接监控循环"""
        while self._is_running:
            try:
                # 检查连接状态
                if not self._client or not self._client.is_connected:
                    logger.warning("检测到连接断开")
                    await self._handle_connection_lost()
                    break
                
                await asyncio.sleep(self._monitor_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"连接监控错误: {e}")
                await asyncio.sleep(self._monitor_interval)
    
    async def _handle_connection_lost(self) -> None:
        """处理连接丢失"""
        logger.warning("连接已丢失")
        
        # 清理状态
        await self._cleanup_connection()
        
        # 触发连接状态回调
        if self._on_connection_changed:
            try:
                await self._on_connection_changed(False)
            except Exception as e:
                logger.error(f"触发连接状态回调失败: {e}")
    
    async def _cleanup_connection(self) -> None:
        """清理连接状态"""
        self._is_connected = False
        self._current_device = None
        self._device_state['is_connected'] = False
        self._write_characteristic = None
        self._notify_characteristic = None
        self._battery_characteristic = None
        
        # 重置序列号状态
        self._sequence_state['current_no'] = 0
        self._sequence_state['pending_no'] = None
        self._sequence_state['is_input_allowed'] = True
        self._sequence_state['accumulated_changes'] = {Channel.A: 0, Channel.B: 0}
        
        if self._client:
            try:
                if self._client.is_connected:
                    await self._client.disconnect()
            except Exception:
                pass
            finally:
                self._client = None
    
    # ============ 资源清理 ============
    
    async def cleanup(self) -> None:
        """清理资源"""
        try:
            await self.disconnect_device()
            logger.info("V3蓝牙控制器资源已清理")
        except Exception as e:
            logger.error(f"清理资源失败: {e}")
