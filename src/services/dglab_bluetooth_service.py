"""
DG-LAB 蓝牙直连服务实现

基于自实现的V3协议层，替代pydglab库的蓝牙直连设备服务，实现IDGLabDeviceService接口。
只负责设备连接和基础硬件操作，不包含任何业务逻辑。
"""

import asyncio
import logging
from typing import Optional, List, Dict, TypedDict

from core.bluetooth import bluetooth_models

from PySide6.QtCore import QObject, Signal

from core import bluetooth
from core.core_interface import CoreInterface
from core.osc_common import Pulse
from core.recording import IPulseRecordHandler, BaseRecordHandler, IPulsePlaybackHandler, BasePlaybackHandler
from core.recording.recording_models import RecordingSnapshot
from models import Channel, ConnectionState, StrengthData, StrengthOperationType, PulseOperation, PlaybackMode, FramesEventType, FramesEventCallback, PlaybackModeChangedCallback, ProgressChangedCallback
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
        
        # 录制处理器实例
        self._record_handler: DGLabBluetoothService._BluetoothRecordHandler = self._BluetoothRecordHandler(self)
        
        # 回放处理器实例
        self._playback_handler: DGLabBluetoothService._BluetoothPlaybackHandler = self._BluetoothPlaybackHandler(self)
        
        # 外部回调（可选）
        self._progress_changed_callback: Optional[ProgressChangedCallback] = None
        self._frames_event_callback: Optional[FramesEventCallback] = None
        self._playback_mode_changed_callback: Optional[PlaybackModeChangedCallback] = None
        
        # 设置回调
        self._setup_callbacks()
        
        logger.info("蓝牙服务已初始化")

    def _setup_callbacks(self) -> None:
        """设置回调函数"""
        self._bluetooth_controller.set_connected_callback(self._on_connected)
        self._bluetooth_controller.set_disconnected_callback(self._on_disconnected)
        self._bluetooth_controller.set_connection_lost_callback(self._on_connection_lost)
        self._bluetooth_controller.set_strength_changed_callback(self._on_strength_changed)
        self._bluetooth_controller.set_battery_callback(self._on_battery_changed)
        self._bluetooth_controller.set_data_sync_callback(self._on_data_sync)
        self._bluetooth_controller.set_progress_changed_callback(self._on_progress_changed)
        self._bluetooth_controller.set_frames_event_callback(self._on_frames_event)
        self._bluetooth_controller.set_playback_mode_changed_callback(self._on_playback_mode_changed)

    async def _on_connected(self) -> None:
        """处理连接状态变化"""
        logger.info(f"蓝牙连接状态变化: 已连接")
        
        # 连接成功后初始化设备
        await self._initialize_device()
        # 通知核心接口连接成功
        self._core_interface.on_client_connected()

    async def _on_disconnected(self) -> None:
        """处理连接状态变化"""
        logger.info(f"蓝牙连接状态变化: 已断开")

        # 断开连接后清理状态
        self._current_strengths = {Channel.A: 0, Channel.B: 0}
        self._last_strength = None
        # 通知核心接口连接断开
        self._core_interface.on_client_disconnected()

    async def _on_connection_lost(self) -> None:
        """处理连接丢失"""
        logger.info(f"蓝牙连接状态变化: 连接丢失")

        # 尝试重连
        logger.info("开始尝试重连设备")
        await self._attempt_reconnect()

    async def _on_strength_changed(self, strengths: Dict[bluetooth.Channel, int]) -> None:
        """处理强度变化"""
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

    async def _on_battery_changed(self, battery_level: int) -> None:
        """处理电量变化"""
        logger.debug(f"电量变化: {battery_level}%")
        
        # 通过信号发送电量更新
        self.signals.battery_level_updated.emit(battery_level)

    def _on_data_sync(self) -> None:
        """处理数据同步通知（用于录制和播放进度更新）"""
        # 处理录制数据同步
        if self._record_handler:
            self._record_handler.on_data_sync()
        
        # 处理播放进度更新
        # 进度更新通过回调系统处理
    
    def _on_progress_changed(self) -> None:
        if self._playback_handler:
            self._playback_handler.on_progress_changed()
        
        # 触发外部进度回调
        if self._progress_changed_callback:
            self._progress_changed_callback()
    
    def _on_frames_event(self, event_type: bluetooth_models.FramesEventType) -> None:
        """处理帧事件回调"""
        # 转换协议层事件类型到服务层事件类型
        service_event = self._convert_frames_event_type_from_bluetooth(event_type)
        
        # 转发到回放处理器（使用服务层类型）
        if self._playback_handler:
            self._playback_handler.on_frames_event(service_event)
        
        # 触发外部帧事件回调
        if self._frames_event_callback:
            self._frames_event_callback(service_event)
    
    def _on_playback_mode_changed(self, old_mode: bluetooth_models.PlaybackMode, new_mode: bluetooth_models.PlaybackMode) -> None:
        """处理播放模式变更回调"""
        # 转换协议层播放模式到服务层播放模式
        service_old_mode = self._convert_playback_mode_from_bluetooth(old_mode)
        service_new_mode = self._convert_playback_mode_from_bluetooth(new_mode)
        
        # 转发到回放处理器（使用服务层类型）
        if self._playback_handler:
            self._playback_handler.on_playback_mode_changed(service_old_mode, service_new_mode)
        
        # 触发外部播放模式变更回调
        if self._playback_mode_changed_callback:
            self._playback_mode_changed_callback(service_old_mode, service_new_mode)

    # ============ 连接管理 ============

    async def start_service(self) -> bool:
        """启动设备连接服务"""
        logger.info("开始启动蓝牙服务...")
        self._server_running = True
        self._stop_event.clear()
        
        logger.info("蓝牙服务启动成功")
        return True

    async def stop_service(self) -> None:
        """停止设备连接服务"""
        logger.info("正在停止蓝牙服务...")
        self._server_running = False
        self._stop_event.set()
        
        # 断开蓝牙连接
        if self.is_device_connected():
            await self._disconnect_device()
        
        logger.info("蓝牙服务已停止")

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
            self._convert_channel_to_bluetooth(channel),
            int(value)
        )

    async def adjust_strength(self, operation_type: StrengthOperationType, value: int, channel: Channel) -> None:
        """调整通道强度（原始设备操作）"""
        if operation_type == StrengthOperationType.SET_TO:
            await self._bluetooth_controller.set_strength_absolute(
                self._convert_channel_to_bluetooth(channel),
                value
            )
        elif operation_type == StrengthOperationType.INCREASE:
            await self._bluetooth_controller.set_strength_relative(
                self._convert_channel_to_bluetooth(channel),
                value
            )
        elif operation_type == StrengthOperationType.DECREASE:
            await self._bluetooth_controller.set_strength_relative(
                self._convert_channel_to_bluetooth(channel),
                -value
            )

    async def reset_strength(self, channel: Channel) -> None:
        """重置通道强度为0（原始设备操作）"""
        await self.adjust_strength(StrengthOperationType.SET_TO, 0, channel)

    async def increase_strength(self, channel: Channel) -> None:
        """增加通道强度（原始设备操作）"""
        await self.adjust_strength(StrengthOperationType.INCREASE, 1, channel)

    async def decrease_strength(self, channel: Channel) -> None:
        """减少通道强度（原始设备操作）"""
        await self.adjust_strength(StrengthOperationType.DECREASE, 1, channel)

    # ============ 波形数据操作 ============

    async def set_pulse_data(self, channel: Channel, pulse: Optional[Pulse]) -> None:
        """设置指定通道的波形数据"""
        if pulse:
            await self._bluetooth_controller.set_pulse_data(
                self._convert_channel_to_bluetooth(channel),
                self._convert_pulse_operations_to_bluetooth(pulse.data)
            )
        else:
            await self._bluetooth_controller.clear_frame_data(
                self._convert_channel_to_bluetooth(channel)
            )

    async def set_snapshots(self, snapshots: Optional[List[RecordingSnapshot]]) -> None:
        """直接播放录制快照列表"""
        if snapshots:
            self._bluetooth_controller.set_snapshots(snapshots)
        else:
            self._bluetooth_controller.clear_frames()

    async def pause_frames(self) -> None:
        """暂停波形数据"""
        self._bluetooth_controller.pause_frames()

    async def resume_frames(self) -> None:
        """继续波形数据"""
        self._bluetooth_controller.resume_frames()

    def get_frames_position(self) -> int:
        """获取播放位置"""
        return self._bluetooth_controller.get_frames_position()

    async def seek_frames_to_position(self, position: int) -> None:
        """跳转到指定位置"""
        if not self._bluetooth_controller.is_connected:
            raise RuntimeError("设备未连接")
        
        # 设置播放位置
        self._bluetooth_controller.set_frames_position(position)

    def get_current_pulse_data(self, channel: Channel) -> Optional[PulseOperation]:
        """获取指定通道当前的脉冲操作数据"""
        return self._bluetooth_controller.get_current_pulse_data(
            self._convert_channel_to_bluetooth(channel)
        )

    # ============ 播放模式控制（实现IDGLabService接口） ============

    def set_playback_mode(self, mode: PlaybackMode) -> None:
        """设置播放模式（服务层接口）"""
        # 转换服务层播放模式到协议层播放模式
        protocol_mode = self._convert_playback_mode_to_bluetooth(mode)
        self._bluetooth_controller.set_playback_mode(protocol_mode)

    def get_playback_mode(self) -> PlaybackMode:
        """获取当前播放模式（服务层接口）"""
        # 从协议层获取播放模式并转换到服务层
        protocol_mode = self._bluetooth_controller.get_playback_mode()
        return self._convert_playback_mode_from_bluetooth(protocol_mode)

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
        if self.is_device_connected():
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
        if self.is_device_connected():
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
        if self.is_device_connected():
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
        """连接到DG-LAB设备"""
        return await self._connect_device(device)

    async def disconnect_device(self) -> bool:
        """断开设备连接"""
        return await self._disconnect_device()

    def is_device_connected(self) -> bool:
        """检查设备是否已连接"""
        return self._bluetooth_controller.is_connected
    
    def is_device_connecting(self) -> bool:
        """检查设备是否正在连接"""
        return self._bluetooth_controller.is_connecting
    
    def is_device_disconnecting(self) -> bool:
        """检查设备是否正在断开"""
        return self._bluetooth_controller.is_disconnecting

    # ============ 内部实现方法 ============

    async def _connect_device(self, device: Optional[DGLabDevice] = None) -> bool:
        try:
            # 判断是否正在连接
            if self.is_device_connecting():
                return False
            
            # 设置等待连接状态
            self._core_interface.set_connection_state(ConnectionState.WAITING)
            
            success: bool = False
            
            if device:
                logger.info(f"尝试连接到指定设备: {device['address']}")
                # 断开现有连接
                if self.is_device_connected():
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

    async def _disconnect_device(self) -> bool:
        """内部断开设备连接方法"""
        try:
            # 判断是否正在断开
            if self.is_device_disconnecting():
                return False
            
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
        while self._server_running:
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
            if not self.is_device_connected():
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

    def _convert_channel_to_bluetooth(self, channel: Channel) -> bluetooth.Channel:
        """转换模型通道到蓝牙通道"""
        if channel == Channel.A:
            return bluetooth.Channel.A
        else:
            return bluetooth.Channel.B

    def _convert_pulse_operations_to_bluetooth(self, operations: List[PulseOperation]) -> List[bluetooth.PulseOperation]:
        """将PulseOperation转换为频率和强度数组"""
        return operations

    def _convert_playback_mode_to_bluetooth(self, mode: PlaybackMode) -> bluetooth_models.PlaybackMode:
        if mode == PlaybackMode.ONCE:
            return bluetooth_models.PlaybackMode.ONCE
        elif mode == PlaybackMode.LOOP:
            return bluetooth_models.PlaybackMode.LOOP

    def _convert_playback_mode_from_bluetooth(self, bt_mode: bluetooth_models.PlaybackMode) -> PlaybackMode:
        if bt_mode == bluetooth_models.PlaybackMode.ONCE:
            return PlaybackMode.ONCE
        elif bt_mode == bluetooth_models.PlaybackMode.LOOP:
            return PlaybackMode.LOOP
    
    def _convert_frames_event_type_from_bluetooth(self, bt_event: bluetooth_models.FramesEventType) -> FramesEventType:
        """转换协议层帧事件类型到服务层帧事件类型"""
        if bt_event == bluetooth_models.FramesEventType.COMPLETED:
            return FramesEventType.COMPLETED
        elif bt_event == bluetooth_models.FramesEventType.LOOPED:
            return FramesEventType.LOOPED

    # ============ 回调设置方法 ============
    
    def set_progress_changed_callback(self, callback: Optional[ProgressChangedCallback]) -> None:
        """设置播放进度变更回调"""
        self._progress_changed_callback = callback
    
    def set_frames_event_callback(self, callback: Optional[FramesEventCallback]) -> None:
        """设置帧事件回调"""
        self._frames_event_callback = callback
    
    def set_playback_mode_changed_callback(self, callback: Optional[PlaybackModeChangedCallback]) -> None:
        """设置播放模式变更回调"""
        self._playback_mode_changed_callback = callback

    # ============ 录制功能 ============

    def get_record_handler(self) -> IPulseRecordHandler:
        """创建脉冲录制处理器"""
        return self._record_handler
    
    def get_playback_handler(self) -> IPulsePlaybackHandler:
        """创建脉冲回放处理器"""
        return self._playback_handler

    class _BluetoothRecordHandler(BaseRecordHandler):
        """蓝牙录制处理器"""

        def __init__(self, bluetooth_service: 'DGLabBluetoothService') -> None:
            super().__init__()
            self._bluetooth_service = bluetooth_service

        def _get_current_pulse_data(self, channel: Channel) -> PulseOperation:
            """获取指定通道当前的脉冲操作数据"""
            # 使用公共方法获取当前脉冲数据
            return self._bluetooth_service.get_current_pulse_data(channel) or ((10, 10, 10, 10), (0, 0, 0, 0))

        def _get_current_strength(self, channel: Channel) -> int:
            """获取指定通道当前的强度值"""
            # 从蓝牙服务的缓存获取
            current_strength = self._bluetooth_service._current_strengths.get(channel, 0)
            return current_strength


    class _BluetoothPlaybackHandler(BasePlaybackHandler):
        """蓝牙回放处理器"""
        
        def __init__(self, bluetooth_service: 'DGLabBluetoothService') -> None:
            super().__init__()
            self._bluetooth_service = bluetooth_service
        
        async def _start_playback(self, snapshots: List[RecordingSnapshot]) -> None:
            """启动controller的快照播放"""
            await self._bluetooth_service.set_snapshots(snapshots)

        async def _stop_playback(self) -> None:
            """停止controller的播放并清理设备状态"""
            # 重置所有通道强度为0
            await self._bluetooth_service.reset_strength(Channel.A)
            await self._bluetooth_service.reset_strength(Channel.B)
            
            # 清空波形数据
            await self._bluetooth_service.set_snapshots(None)

        async def _pause_playback(self) -> None:
            """暂停controller的播放但保持设备状态"""
            await self._bluetooth_service.pause_frames()

        async def _resume_playback(self) -> None:
            """从暂停状态继续controller的播放"""
            await self._bluetooth_service.resume_frames()

        async def _seek_to_position(self, position: int) -> None:
            """跳转到指定位置"""
            await self._bluetooth_service.seek_frames_to_position(position)

        def get_current_position(self) -> int:
            """获取当前播放位置"""
            return self._bluetooth_service.get_frames_position()
        
        
