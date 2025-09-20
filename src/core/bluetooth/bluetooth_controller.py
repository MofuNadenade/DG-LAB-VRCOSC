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

from core.recording.recording_models import ChannelSnapshot, RecordingSnapshot

from .bluetooth_models import (
    DeviceInfo, Channel, DeviceState, BluetoothUUIDs, PulseOperation, StrengthParsingMethod,
    WaveformFrequencyOperation, WaveformStrengthOperation, PlaybackMode, FramesEventType,
    ConnectionStateCallback, DataSyncCallback, ProgressChangedCallback, FramesEventCallback,
    PlaybackModeChangedCallback
)
from .bluetooth_protocol import BluetoothProtocol
from .bluetooth_channel_state_handler import BluetoothChannelStateHandler

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
        self._is_connecting = False
        self._is_disconnecting = False
        self._current_device: Optional[DeviceInfo] = None
        
        # GATT特性对象缓存
        self._write_characteristic: Optional[BleakGATTCharacteristic] = None
        self._notify_characteristic: Optional[BleakGATTCharacteristic] = None
        self._battery_characteristic: Optional[BleakGATTCharacteristic] = None
        
        # 设备状态
        self._device_state: DeviceState = self._create_device_state()
        
        # 通道状态处理器（统一管理AB通道）
        self._channel_handler = BluetoothChannelStateHandler()
        
        # 定时任务
        self._data_send_task: Optional[asyncio.Task[None]] = None
        self._battery_polling_task: Optional[asyncio.Task[None]] = None
        self._is_running = False
        self._battery_polling_interval = 5.0
        self._pulse_buffer_count = 0
        self._pulse_buffer_min = 1
        self._pulse_buffer_max = 5
        
        # 暂停状态
        self._is_paused: bool = False
        
        # 播放模式相关状态
        self._current_playback_mode: PlaybackMode = PlaybackMode.ONCE
        self._last_frame_finished: bool = False
        
        # 连接状态事件信号
        self._connected_event = asyncio.Event()
        
        # 序列号和强度变更状态
        self._sequence_no: int = 0
        self._input_allowed: bool = True
        self._accumulated_changes: Dict[Channel, int] = {Channel.A: 0, Channel.B: 0}
        self._pending_sequence_no: int = 0
        self._request_time: float = 0.0

        # 回调函数 - 使用Protocol类型
        self._on_notification: Optional[Callable[[bytes], Awaitable[None]]] = None
        self._on_connecting: Optional[ConnectionStateCallback] = None
        self._on_connected: Optional[ConnectionStateCallback] = None
        self._on_disconnected: Optional[ConnectionStateCallback] = None
        self._on_connection_lost: Optional[ConnectionStateCallback] = None
        self._on_strength_changed: Optional[Callable[[Dict[Channel, int]], Awaitable[None]]] = None
        self._on_battery_changed: Optional[Callable[[int], Awaitable[None]]] = None
        self._on_data_sync: Optional[DataSyncCallback] = None
        self._on_progress_changed: Optional[ProgressChangedCallback] = None
        
        # 播放模式相关回调
        self._on_frames_event: Optional[FramesEventCallback] = None
        self._on_playback_mode_changed: Optional[PlaybackModeChangedCallback] = None
        
        logger.info("V3蓝牙控制器已初始化")

    def _next_sequence_no(self) -> int:
        """获取下一个序列号"""
        self._sequence_no = (self._sequence_no + 1) % 16
        if self._sequence_no == 0:
            self._sequence_no = 1
        return self._sequence_no
    
    def _check_timeout(self) -> None:
        """检查强度变更请求超时"""
        if not self._input_allowed and time.time() - self._request_time > 1.0:
            logger.warning("强度变更请求超时，重置状态")
            self._input_allowed = True
            self._pending_sequence_no = 0

    # ============ 回调设置 ============
    
    def set_notification_callback(self, callback: Callable[[bytes], Awaitable[None]]) -> None:
        """设置通知回调"""
        self._on_notification = callback
    
    def set_connecting_callback(self, callback: Optional[ConnectionStateCallback]) -> None:
        """设置连接中状态回调"""
        self._on_connecting = callback
    
    def set_connected_callback(self, callback: Optional[ConnectionStateCallback]) -> None:
        """设置连接成功回调"""
        self._on_connected = callback
    
    def set_disconnected_callback(self, callback: Optional[ConnectionStateCallback]) -> None:
        """设置断开连接回调"""
        self._on_disconnected = callback
    
    def set_connection_lost_callback(self, callback: Optional[ConnectionStateCallback]) -> None:
        """设置连接丢失回调"""
        self._on_connection_lost = callback
    
    def set_strength_changed_callback(self, callback: Callable[[Dict[Channel, int]], Awaitable[None]]) -> None:
        """设置强度变化回调"""
        self._on_strength_changed = callback
    
    def set_battery_callback(self, callback: Callable[[int], Awaitable[None]]) -> None:
        """设置电量变化回调"""
        self._on_battery_changed = callback
    
    def set_data_sync_callback(self, callback: Optional[DataSyncCallback]) -> None:
        """设置数据同步回调"""
        self._on_data_sync = callback

    def set_progress_changed_callback(self, callback: Optional[ProgressChangedCallback]) -> None:
        """设置进度回调"""
        self._on_progress_changed = callback

    def set_frames_event_callback(self, callback: Optional[FramesEventCallback]) -> None:
        """设置帧事件回调"""
        self._on_frames_event = callback

    def set_playback_mode_changed_callback(self, callback: Optional[PlaybackModeChangedCallback]) -> None:
        """设置播放模式变更回调"""
        self._on_playback_mode_changed = callback

    # ============ 播放模式接口 ============

    def set_playback_mode(self, mode: PlaybackMode) -> None:
        """设置播放模式"""
        old_mode = self._current_playback_mode
        self._current_playback_mode = mode
        self._channel_handler.set_playback_mode(mode)
        
        # 通知播放模式变更
        self._notify_playback_mode_changed(old_mode, mode)

    def get_playback_mode(self) -> PlaybackMode:
        """获取当前播放模式"""
        return self._current_playback_mode

    # ============ 公共接口 ============
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._is_connected
    
    @property
    def is_connecting(self) -> bool:
        """检查是否正在连接"""
        return self._is_connecting

    @property
    def is_disconnecting(self) -> bool:
        """检查是否正在断开"""
        return self._is_disconnecting
    
    @property
    def current_device(self) -> Optional[DeviceInfo]:
        """获取当前连接的设备信息"""
        return self._current_device
    
    def get_device_state(self) -> DeviceState:
        """获取设备状态"""
        return self._device_state
    
    def get_battery_level(self) -> int:
        """获取当前电量
        
        Returns:
            电量百分比 (0-100)
        """
        return self._device_state['battery_level']
    
    async def scan_devices(self, scan_time: float = 5.0) -> List[DeviceInfo]:
        """扫描可用的DG-LAB V3设备"""
        try:
            logger.info(f"开始扫描DG-LAB V3设备，扫描时间: {scan_time}秒")
            
            # 执行蓝牙扫描
            devices = await BleakScanner.discover(timeout=scan_time, return_adv=True)
            
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
            # 判断是否正在连接
            if self.is_connecting:
                return False

            # 断开现有连接
            if self.is_connected:
                await self.disconnect_device()
            
            # 设置连接中状态
            self._is_connecting = True
            
            # 触发连接中状态回调
            if self._on_connecting:
                await self._on_connecting()
            
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
            self._client = BleakClient(target_device['address'], timeout=timeout, disconnected_callback=self._on_disconnect_callback)
            await self._client.connect()
            
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
            if self._on_connected:
                await self._on_connected()
            
            # 触发连接状态事件信号
            self._connected_event.set()
            
            logger.info(f"成功连接到设备: {target_device['name']} ({target_device['address']})")
            return True
            
        except Exception as e:
            logger.error(f"连接设备失败: {e}")
            await self._cleanup_connection()
            return False
        
        finally:
            self._is_connecting = False
    
    async def disconnect_device(self) -> bool:
        """断开设备连接"""
        try:
            # 判断是否正在断开
            if self._is_disconnecting:
                return False

            # 判断是否已连接
            if not self._is_connected:
                return True
            
            logger.info("正在断开设备连接...")

            self._is_disconnecting = True
            
            # 停止服务
            await self._stop_services()
            
            # 断开蓝牙连接
            if self._client and self._client.is_connected:
                await self._client.disconnect()
            
            # 触发连接状态回调
            if self._on_disconnected:
                await self._on_disconnected()
            
            logger.info("设备连接已断开")
            return True
            
        except Exception as e:
            logger.error(f"断开连接失败: {e}")
            await self._cleanup_connection()
            return False
        
        finally:
            self._is_disconnecting = False
    
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
    
    async def set_strength_absolute(self, channel: Channel, strength: int) -> bool:
        """设置绝对强度值"""
        if not self.is_connected:
            logger.warning("设备未连接，无法设置强度")
            return False
        
        if not self._protocol.validate_strength(strength):
            logger.error(f"强度值超出范围: {strength}")
            return False
        
        # 检查超时
        self._check_timeout()
        
        # 累积强度变更
        current_strength: int = self._get_current_strength(channel)
        if self._input_allowed:
            self._accumulated_changes[channel] = strength - current_strength
        else:
            # 等待确认期间继续累积
            additional_change: int = strength - current_strength
            self._accumulated_changes[channel] += additional_change
        
        return True
    
    async def set_strength_relative(self, channel: Channel, delta: int) -> bool:
        """相对调整强度"""
        if not self.is_connected:
            logger.warning("设备未连接，无法调整强度")
            return False
        
        # 检查超时
        self._check_timeout()
        
        # 直接累积相对变化
        self._accumulated_changes[channel] += delta
        
        # 验证累积后的强度值范围
        current_strength: int = self._get_current_strength(channel)
        new_strength: int = current_strength + self._accumulated_changes[channel]
        
        if not self._protocol.validate_strength(new_strength):
            logger.error(f"累积后强度值超出范围: {new_strength}")
            self._accumulated_changes[channel] -= delta  # 回退
            return False
        
        return True
    
    async def reset_strength(self, channel: Channel) -> bool:
        """重置通道强度为0"""
        return await self.set_strength_absolute(channel, 0)
    
    async def query_battery_level(self) -> Optional[int]:
        """手动查询电量
        
        Returns:
            电量百分比 (0-100)，如果查询失败返回None
        """
        try:
            if not self.is_connected:
                logger.warning("设备未连接，无法查询电量")
                return None
            
            if not self._battery_characteristic:
                logger.warning("电量特性不可用，无法查询电量")
                return None
            
            # 读取电量特性值
            if self._client:
                battery_data = await self._client.read_gatt_char(self._battery_characteristic)
                
                if not battery_data:
                    logger.warning("读取电量数据为空")
                    return None
                
                battery_level = int.from_bytes(battery_data, byteorder='little')
                
                # 验证电量值范围
                if not (0 <= battery_level <= 100):
                    logger.warning(f"读取到异常电量值: {battery_level}%")
                    return None
                
                # 更新设备状态
                self._device_state['battery_level'] = battery_level
                
                # 触发电量变化回调
                if self._on_battery_changed:
                    await self._on_battery_changed(battery_level)
                
                return battery_level
            
            return None
            
        except Exception as e:
            logger.error(f"手动查询电量失败: {e}")
            return None
    
    async def set_pulse_data(self, channel: Channel, pulses: List[PulseOperation]) -> None:
        """设置通道波形数据"""
        if not self.is_connected:
            logger.warning("设备未连接，无法设置波形数据")
            return

        # 限制波形频率和强度在有效范围内
        clamped_pulses: List[PulseOperation] = []
        for pulse in pulses:
            freq: WaveformFrequencyOperation = (
                self._protocol.clamp_pulse_frequency(pulse[0][0]),
                self._protocol.clamp_pulse_frequency(pulse[0][1]),
                self._protocol.clamp_pulse_frequency(pulse[0][2]),
                self._protocol.clamp_pulse_frequency(pulse[0][3])
            )
            strength: WaveformStrengthOperation = (
                self._protocol.clamp_pulse_strength(pulse[1][0]),
                self._protocol.clamp_pulse_strength(pulse[1][1]),
                self._protocol.clamp_pulse_strength(pulse[1][2]),
                self._protocol.clamp_pulse_strength(pulse[1][3])
            )
            clamped_pulse: PulseOperation = (freq, strength)
            clamped_pulses.append(clamped_pulse)
        
        self._channel_handler.set_pulse_data(channel, clamped_pulses)
        # 重置播放状态，确保新数据可以正常播放
        self._is_paused = False
        self._last_frame_finished = False
    
    async def clear_frame_data(self, channel: Channel) -> None:
        """清除通道波形数据（设置为静止状态）"""
        self._channel_handler.clear_frame_data(channel)

    def clear_frames(self) -> None:
        """清除所有通道的波形数据"""
        self._channel_handler.clear_all_frames()

    def set_snapshot_data(self, channel: Channel, snapshots: List[ChannelSnapshot]) -> None:
        """设置通道快照数据（新接口）"""
        # 限制波形频率和强度在有效范围内
        clamped_snapshots: List[ChannelSnapshot] = []
        for snapshot in snapshots:
            # 获取原始波形操作数据
            freq, strength = snapshot.pulse_operation
            
            # 限制频率范围
            clamped_freq: WaveformFrequencyOperation = (
                self._protocol.clamp_pulse_frequency(freq[0]),
                self._protocol.clamp_pulse_frequency(freq[1]),
                self._protocol.clamp_pulse_frequency(freq[2]),
                self._protocol.clamp_pulse_frequency(freq[3])
            )
            
            # 限制强度范围
            clamped_strength: WaveformStrengthOperation = (
                self._protocol.clamp_pulse_strength(strength[0]),
                self._protocol.clamp_pulse_strength(strength[1]),
                self._protocol.clamp_pulse_strength(strength[2]),
                self._protocol.clamp_pulse_strength(strength[3])
            )
            
            # 创建限制后的快照
            clamped_pulse_operation: PulseOperation = (clamped_freq, clamped_strength)
            clamped_snapshot = ChannelSnapshot(
                pulse_operation=clamped_pulse_operation,
                current_strength=min(max(snapshot.current_strength, 0), 200)  # 限制实时强度范围 [0-200]
            )
            clamped_snapshots.append(clamped_snapshot)
        
        self._channel_handler.set_snapshot_data(channel, clamped_snapshots)

    def set_snapshots(self, snapshots: List[RecordingSnapshot]) -> None:
        """设置录制快照列表"""
        self._channel_handler.set_snapshots(snapshots)
        # 重置播放状态，确保新数据可以正常播放
        self._is_paused = False
        self._last_frame_finished = False
        logger.info("开始播放快照序列")

    def pause_frames(self) -> None:
        """暂停波形数据"""
        self._is_paused = True

    def resume_frames(self) -> None:
        """继续波形数据"""
        self._is_paused = False
    
    def get_frames_position(self) -> int:
        """获取帧播放位置"""
        return self._channel_handler.get_frame_position()

    def set_frames_position(self, position: int) -> None:
        """设置帧播放位置"""
        self._channel_handler.set_frame_position(position)
        
        # 通知进度变化
        if self._on_progress_changed:
            self._on_progress_changed()
    
    def get_current_pulse_data(self, channel: Channel) -> Optional[PulseOperation]:
        """获取指定通道当前播放的脉冲操作数据（用于录制）"""
        return self._channel_handler.get_current_pulse_data(channel)
    
    def get_current_strength(self, channel: Channel) -> int:
        """获取指定通道当前的强度值（用于录制）"""
        return self._get_current_strength(channel)
    
    @property
    def channel_handler(self) -> BluetoothChannelStateHandler:
        """获取通道状态处理器"""
        return self._channel_handler
    
    def has_any_frame_data(self) -> bool:
        """检查是否有任何通道有波形数据"""
        return self._channel_handler.has_any_frame_data()
    
    def prepare_bluetooth_data(self) -> Tuple[Optional[PulseOperation], Optional[PulseOperation]]:
        """准备蓝牙发送数据"""
        return self._channel_handler.prepare_bluetooth_command_data()

    # ============ 内部实现 ============

    def _create_device_state(self) -> DeviceState:
        """创建设备状态"""
        return {
            'channel_a': {
                'strength': 0,
                'strength_limit': 200,
                'frequency_balance': 100,
                'strength_balance': 100,
            },
            'channel_b': {
                'strength': 0,
                'strength_limit': 200,
                'frequency_balance': 100,
                'strength_balance': 100,
            },
            'is_connected': False,
            'battery_level': 0
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
                await self._client.start_notify(self._notify_characteristic, self._on_notification_received)
            logger.debug("已启动通知")
            
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
    
    async def _handle_b1_response(self, data: bytes) -> None:
        """处理B1回应消息"""
        try:
            response = self._protocol.parse_b1_response(data)
            if not response:
                return
            
            self._device_state['channel_a']['strength'] = response['strength_a']
            self._device_state['channel_b']['strength'] = response['strength_b']
            
            logger.debug(f"收到B1回应: 序列号={response['sequence_no']}, 强度A={response['strength_a']}, B={response['strength_b']}")
            
            # 处理序列号确认
            if response['sequence_no'] > 0 and response['sequence_no'] == self._pending_sequence_no:
                # 强度变更确认成功
                self._input_allowed = True
                self._pending_sequence_no = 0
            elif response['sequence_no'] > 0:
                logger.warning(f"B1序列号不匹配: 期望={self._pending_sequence_no}, 实际={response['sequence_no']}")
            
            # 触发强度变化回调
            if self._on_strength_changed:
                strength_dict: Dict[Channel, int] = {Channel.A: response['strength_a'], Channel.B: response['strength_b']}
                await self._on_strength_changed(strength_dict)
                
        except Exception as e:
            logger.error(f"处理B1回应失败: {e}")
    
    async def _start_services(self) -> None:
        """启动服务"""
        if self._is_running:
            return
        
        self._is_running = True

        # 启动数据发送任务
        self._data_send_task = asyncio.create_task(self._data_send_loop())
        
        # 启动电量轮询任务
        self._battery_polling_task = asyncio.create_task(self._battery_polling_loop())
        
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
        
        # 停止电量轮询任务
        if self._battery_polling_task:
            self._battery_polling_task.cancel()
            try:
                await self._battery_polling_task
            except asyncio.CancelledError:
                pass
            self._battery_polling_task = None
        
        logger.debug("控制器服务已停止")
    
    async def _data_send_loop(self) -> None:
        """数据发送循环"""
        try:
            next_time = time.time()
            while self._is_running:
                if not self.is_connected:
                    await self._connected_event.wait()
                    self._pulse_buffer_count = 0
                    next_time = time.time()
                    continue

                # 检查是否暂停
                if not self._is_paused:
                    # 未暂停时正常发送数据
                    if self._pulse_buffer_count < self._pulse_buffer_min:
                        for _ in range(self._pulse_buffer_max - self._pulse_buffer_count):
                            await self._process_and_send_b0_command()
                            self._pulse_buffer_count += 1

                    if self._pulse_buffer_count > 0:
                        self._pulse_buffer_count -= 1

                    self._channel_handler.advance_logical_frame()
                    
                    # 检测播放状态变化并触发回调
                    current_finished = self._channel_handler.is_frame_sequence_finished()
                    
                    if not self._last_frame_finished and current_finished:
                        # 帧序列刚刚完成
                        if self._current_playback_mode == PlaybackMode.ONCE:
                            logger.info("帧序列播放已完成（单次模式）")
                            self._notify_frames_event(FramesEventType.COMPLETED)
                            # 清空快照数据，让后续循环发送空数据
                            self._channel_handler.clear_all_frames()
                        elif self._current_playback_mode == PlaybackMode.LOOP:
                            logger.info("帧序列播放完成，开始新循环")
                            self._notify_frames_event(FramesEventType.LOOPED)
                            # 重置帧位置开始新循环
                            self._channel_handler.reset_frame_progress()
                    
                    self._last_frame_finished = current_finished
                    
                    # 通知进度变化
                    if self._on_progress_changed:
                        self._on_progress_changed()
                else:
                    # 暂停时保持连接但不发送新数据，也不推进播放位置
                    pass
                
                self._notify_data_sync()

                next_time += (0.1 - 0.001)  # 时间补偿，减少累积误差
                sleep_time = max(0, next_time - time.time())
                await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.debug("波形发送任务被取消")
        except Exception as e:
            logger.error(f"数据发送循环错误: {e}")

    def _next_pulse_and_strength_data(self, channel: Channel) -> Tuple[WaveformFrequencyOperation, WaveformStrengthOperation, Optional[int]]:
        """获取当前波形和强度数据"""
        frame_data = self._channel_handler.advance_buffer_for_send()
        frame = frame_data[channel]
        return frame.pulse_operation[0], frame.pulse_operation[1], frame.target_strength

    async def _process_and_send_b0_command(self) -> None:
        """处理并发送B0指令 - 强度变更逻辑"""
        try:
            # 检查强度变更超时
            self._check_timeout()
            
            # 获取当前脉冲和强度数据
            pulse_freq_a, pulse_strength_a, target_strength_a = self._next_pulse_and_strength_data(Channel.A)
            pulse_freq_b, pulse_strength_b, target_strength_b = self._next_pulse_and_strength_data(Channel.B)
            
            # 检查是否有累积的强度变更需要发送
            has_strength_changes: bool = any(self._accumulated_changes.values())
            
            if has_strength_changes and self._input_allowed:
                # 发送强度变更B0指令
                sequence_no = self._next_sequence_no()
                self._pending_sequence_no = sequence_no
                self._input_allowed = False
                self._request_time = time.time()
                
                # 构建强度解读方式
                method_a: StrengthParsingMethod = (
                    StrengthParsingMethod.INCREASE if self._accumulated_changes[Channel.A] > 0 else
                    StrengthParsingMethod.DECREASE if self._accumulated_changes[Channel.A] < 0 else
                    StrengthParsingMethod.NO_CHANGE
                )
                method_b: StrengthParsingMethod = (
                    StrengthParsingMethod.INCREASE if self._accumulated_changes[Channel.B] > 0 else
                    StrengthParsingMethod.DECREASE if self._accumulated_changes[Channel.B] < 0 else
                    StrengthParsingMethod.NO_CHANGE
                )
                strength_parsing_method = self._protocol.build_strength_parsing_method(method_a, method_b)
                
                # 强度设定值：使用累积变更的绝对值
                strength_a = abs(self._accumulated_changes[Channel.A])
                strength_b = abs(self._accumulated_changes[Channel.B])
                
                # 清空累积变更
                self._accumulated_changes = {Channel.A: 0, Channel.B: 0}
                
            elif not self._input_allowed:
                # 正在等待强度变更确认，发送序列号为0的B0指令
                sequence_no = 0
                strength_parsing_method = self._protocol.build_strength_parsing_method(
                    StrengthParsingMethod.NO_CHANGE, StrengthParsingMethod.NO_CHANGE
                )
                # 等待期间强度设定值为0
                strength_a = 0
                strength_b = 0
            else:
                # 常规波形数据发送
                sequence_no = 0
                strength_parsing_method = self._protocol.build_strength_parsing_method(
                    StrengthParsingMethod.ABSOLUTE, StrengthParsingMethod.ABSOLUTE
                )
                
                # 使用当前设备状态或快照强度
                strength_a = target_strength_a if target_strength_a is not None else self._device_state['channel_a']['strength']
                strength_b = target_strength_b if target_strength_b is not None else self._device_state['channel_b']['strength']
                
                # 更新设备状态（快照强度变化）
                if target_strength_a is not None:
                    self._device_state['channel_a']['strength'] = target_strength_a
                if target_strength_b is not None:
                    self._device_state['channel_b']['strength'] = target_strength_b
            
            # 构建并发送B0指令
            b0_data: Optional[bytes] = self._protocol.build_b0_command(
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
                await self._send_data(b0_data)
            else:
                logger.error("B0指令参数验证失败，跳过发送")
                
        except Exception as e:
            logger.error(f"处理B0指令失败: {e}")
    
    def _notify_data_sync(self) -> None:
        """通知数据同步"""
        if self._on_data_sync:
            self._on_data_sync()

    def _notify_frames_event(self, event_type: FramesEventType) -> None:
        """通知帧事件"""
        if self._on_frames_event:
            try:
                self._on_frames_event(event_type)
            except Exception as e:
                logger.error(f"Frames event callback failed: {e}")

    def _notify_playback_mode_changed(self, old_mode: PlaybackMode, new_mode: PlaybackMode) -> None:
        """通知播放模式变更"""
        if self._on_playback_mode_changed:
            try:
                self._on_playback_mode_changed(old_mode, new_mode)
            except Exception as e:
                logger.error(f"Playback mode changed callback failed: {e}")
    
    async def _battery_polling_loop(self) -> None:
        """电量轮询循环"""
        while self._is_running:
            try:
                # 等待连接状态变化信号
                if not self.is_connected:
                    # 清除事件状态，等待连接成功
                    await self._connected_event.wait()
                    continue
                
                # 执行电量查询
                await self.query_battery_level()

                # 等待轮询间隔
                await asyncio.sleep(self._battery_polling_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"电量轮询错误: {e}")
                await asyncio.sleep(5.0)  # 出错时等待5秒再重试
    
    async def _cleanup_connection(self) -> None:
        """清理连接状态"""
        self._is_connected = False
        self._is_connecting = False
        self._current_device = None
        self._device_state['is_connected'] = False
        self._write_characteristic = None
        self._notify_characteristic = None
        self._battery_characteristic = None
        
        # 清理强度变更状态
        self._input_allowed = True
        self._accumulated_changes = {Channel.A: 0, Channel.B: 0}
        self._pending_sequence_no = 0
        self._request_time = 0.0
        self._sequence_no = 0
        
        # 清除连接状态事件信号
        self._connected_event.clear()
        
        self._client = None
    
    def _on_disconnect_callback(self, client: BleakClient) -> None:
        """断开连接回调"""
        asyncio.create_task(self._on_disconnected_async())

    async def _on_disconnected_async(self) -> None:
        """断开连接回调"""
        logger.info("设备连接已断开")
        await self._cleanup_connection()
        
        if not self._is_disconnecting:
            # 触发连接状态回调
            if self._on_connection_lost:
                await self._on_connection_lost()
