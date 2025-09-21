"""
OSC服务 - 完全封装OSC功能
包括OSC服务器管理、消息处理、动作注册等所有OSC相关功能
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Set, TypedDict

from pythonosc import dispatcher, osc_server, udp_client

from core.core_interface import CoreInterface
from core.osc_common import OSCAddress, OSCBinding
from models import ConnectionState, OSCPrimitive, OSCValue, OSCValueType, get_osc_value
from i18n import translate
from .service_interface import IService
from gui.address.osc_debug_display import OSCDebugDisplayManager
from gui.address.osc_debug_filter import OSCDebugFilter

# 移除对UI组件的直接导入，通过CoreInterface访问

logger = logging.getLogger(__name__)


class OSCAddressInfo(TypedDict):
    address: str
    types: Set[OSCValueType]
    last_value: List[OSCValue]
    last_update_time: float


class OSCBindingInfo(TypedDict):
    binding: OSCBinding
    last_address: Optional[OSCAddress]
    last_value: List[OSCValue]
    last_update_time: float


class OSCService(IService):
    """
    OSC服务 - 完全封装的OSC功能模块
    
    职责：
    1. OSC服务器的启动和管理
    2. OSC消息的接收和处理
    3. 与DGLab服务的通信接口
    4. VRChat消息发送
    
    特点：
    - 完全独立，不依赖外部控制器
    - 通过回调接口与DGLab服务通信
    - 自管理服务器生命周期
    """

    def __init__(self, core_interface: CoreInterface, osc_port: int = 9001, vrchat_port: int = 9000) -> None:
        """
        初始化OSC服务
        """
        super().__init__()

        self._core_interface = core_interface
        self._osc_client: Optional[udp_client.SimpleUDPClient] = None
        self._osc_server_instance: Optional[osc_server.AsyncIOOSCUDPServer] = None
        self._osc_transport: Optional[asyncio.BaseTransport] = None
        self._is_running: bool = False

        # OSC服务器配置
        self._osc_port: int = osc_port
        self._vrchat_port: int = vrchat_port
        
        self._address_infos: Dict[str, OSCAddressInfo] = {}
        self._binding_infos: Dict[OSCBinding, OSCBindingInfo] = {}
        
        # OSC调试显示配置
        self._debug_display_enabled: bool = False
        self._debug_display_duration: float = 5.0  # 显示5秒
        self._debug_fadeout_duration: float = 1.0  # 淡出1秒
        
        # OSC调试显示管理器
        self._debug_display_manager: OSCDebugDisplayManager = OSCDebugDisplayManager()

    async def start_service(self) -> bool:
        """
        启动OSC服务器
        
        Args:
            osc_port: OSC监听端口
            
        Returns:
            bool: 启动是否成功
        """
        if self._is_running:
            logger.warning("OSC服务器已在运行")
            return True

        try:
            # 初始化OSC客户端（用于发送消息到VRChat）
            self._osc_client = udp_client.SimpleUDPClient("127.0.0.1", self._vrchat_port)
            logger.info(f"OSC客户端已初始化，目标端口: {self._vrchat_port}")

            # 设置OSC服务器
            disp = dispatcher.Dispatcher()
            # 所有OSC消息都路由到内部处理方法
            disp.map("*", self._handle_osc_message_internal)  # type: ignore

            event_loop = asyncio.get_event_loop()
            if not isinstance(event_loop, asyncio.BaseEventLoop):
                raise RuntimeError("无法获取事件循环")

            # 创建OSC服务器
            self._osc_server_instance = osc_server.AsyncIOOSCUDPServer(
                ("0.0.0.0", self._osc_port), disp, event_loop
            )
            self._osc_transport, _ = await self._osc_server_instance.create_serve_endpoint()

            self._is_running = True
            logger.info(f"OSC服务器已启动，监听端口: {self._osc_port}")
            return True

        except OSError as e:
            if e.errno == 10048:  # Port already in use
                error_message = translate("tabs.connection.osc_port_in_use_detail").format(self._osc_port)
                logger.error(error_message)
                # 通过UI接口报告错误
                self._core_interface.set_connection_state(ConnectionState.ERROR, translate("tabs.connection.osc_port_in_use"))
                return False
            else:
                logger.error(f"OSC服务器启动失败: {e}")
                raise
        except Exception as e:
            logger.error(f"OSC服务器启动异常: {e}")
            return False

    async def stop_service(self) -> None:
        """停止OSC服务器"""
        if not self._is_running:
            return

        if self._osc_transport:
            self._osc_transport.close()
            logger.info("OSC服务器已停止")

        self._osc_transport = None
        self._osc_server_instance = None
        self._is_running = False

    def is_service_running(self) -> bool:
        """检查OSC服务器运行状态"""
        return self._is_running

    def _handle_osc_message_internal(self, address: str, *args: OSCPrimitive) -> None:
        """OSC消息内部处理方法（同步）"""
        arguments: List[OSCValue] = []
        for arg in args:
            arguments.append(get_osc_value(arg))
        # 创建异步任务处理消息
        asyncio.create_task(self.handle_osc_message(address, *arguments))

    async def handle_osc_message(self, address: str, *args: OSCValue) -> None:
        """
        处理OSC消息
        
        Args:
            address: OSC地址
            *args: OSC参数
        """

        # 更新地址信息
        address_info = self.get_address_info(address)
        for arg in args:
            value_type: OSCValueType = arg.value_type()
            address_info["types"].add(value_type)
        address_info["last_value"] = list(args)
        address_info["last_update_time"] = time.time()

        # 注册到地址代码注册表
        if not self._core_interface.registries.code_registry.has_code(address):
            self._core_interface.registries.code_registry.register_code(address)

        # OSC调试显示
        if self._debug_display_enabled:
            self._debug_display_manager.set_display_duration(self._debug_display_duration)
            self._debug_display_manager.set_fadeout_duration(self._debug_fadeout_duration)
            self._debug_display_manager.set_enabled(True)
            self._debug_display_manager.add_or_update_debug_item(address, list(args))

        # 通过UI接口的绑定注册表处理消息
        address_obj = self._core_interface.registries.address_registry.get_address_by_code(address)
        if address_obj:
            await self._handle_osc_message(address_obj, *args)

    async def _handle_osc_message(self, address: OSCAddress, *args: OSCValue) -> None:
        """处理OSC消息"""
        bindings = self._core_interface.registries.binding_registry.get_bindings_by_address(address)
        for binding in bindings:
            binding_info = self.get_binding_info(binding)
            binding_info["last_address"] = address
            binding_info["last_value"] = list(args)
            binding_info["last_update_time"] = time.time()

            success = await binding.action.handle(*args)
            if not success:
                args_types = [arg.value_type() for arg in args]
                action_types = [t.value_type() for t in binding.action.types]
                logger.warning(f"绑定（{binding.action.name}）处理OSC消息失败，地址（{address.name}）类型不匹配，参数的类型有（{args_types}），支持的类型有（{action_types}）")

    def get_address_info(self, address: str) -> OSCAddressInfo:
        """
        获取OSC地址信息
        """
        address_info: OSCAddressInfo
        if address in self._address_infos:
            address_info = self._address_infos[address]
        else:
            address_info = {
                "address": address,
                "types": set(),
                "last_value": list(),
                "last_update_time": time.time()
            }
            self._address_infos[address] = address_info
        return address_info

    def get_binding_info(self, binding: OSCBinding) -> OSCBindingInfo:
        """
        获取OSC绑定信息
        """
        binding_info: OSCBindingInfo
        if binding in self._binding_infos:
            binding_info = self._binding_infos[binding]
        else:
            binding_info = {
                "binding": binding,
                "last_address": None,
                "last_value": list(),
                "last_update_time": time.time()
            }
            self._binding_infos[binding] = binding_info
        return binding_info

    def get_address_infos(self) -> Dict[str, OSCAddressInfo]:
        """
        获取检测到的OSC地址信息
        """
        return self._address_infos

    def get_binding_infos(self) -> Dict[OSCBinding, OSCBindingInfo]:
        """
        获取检测到的OSC绑定信息
        """
        return self._binding_infos

    # ============ VRChat通信方法 ============

    def send_message_to_vrchat_chatbox(self, message: str) -> None:
        """
        发送消息到VRChat聊天框
        
        Args:
            message: 要发送的消息
        """
        if not self._osc_client:
            logger.debug("OSC客户端未初始化，跳过消息发送")
            return

        try:
            self._osc_client.send_message("/chatbox/input", [message, True, False])  # type: ignore
            logger.debug(f"已发送ChatBox消息: {message}")
        except Exception as e:
            logger.error(f"发送ChatBox消息失败: {e}")

    def send_value_to_vrchat(self, path: str, value: OSCValue) -> None:
        """
        发送值到VRChat
        
        Args:
            path: OSC路径
            value: 要发送的值
        """
        if not self._osc_client:
            logger.debug("OSC客户端未初始化，跳过值发送")
            return

        try:
            self._osc_client.send_message(path, value)  # type: ignore
            logger.debug(f"已发送OSC值: {path} = {value!r}")
        except Exception as e:
            logger.error(f"发送OSC值失败: {e}")

    # ============ OSC调试显示配置 ============
    
    def set_debug_display_enabled(self, enabled: bool) -> None:
        """设置OSC调试显示开关"""
        self._debug_display_enabled = enabled
        
        # 如果禁用调试显示，清理调试管理器
        if not enabled:
            self._debug_display_manager.set_enabled(False)
        
    def is_debug_display_enabled(self) -> bool:
        """获取OSC调试显示开关状态"""
        return self._debug_display_enabled
        
    def set_debug_display_duration(self, duration: float) -> None:
        """设置OSC调试显示时间（秒）"""
        self._debug_display_duration = max(0.1, duration)
        self._debug_display_manager.set_display_duration(self._debug_display_duration)
        
    def get_debug_display_duration(self) -> float:
        """获取OSC调试显示时间（秒）"""
        return self._debug_display_duration
        
    def set_debug_fadeout_duration(self, duration: float) -> None:
        """设置OSC调试显示淡出时间（秒）"""
        self._debug_fadeout_duration = max(0.1, duration)
        self._debug_display_manager.set_fadeout_duration(self._debug_fadeout_duration)
        
    def get_debug_fadeout_duration(self) -> float:
        """获取OSC调试显示淡出时间（秒）"""
        return self._debug_fadeout_duration
    
    def set_debug_filter(self, debug_filter: Optional[OSCDebugFilter]) -> None:
        """设置调试过滤器"""
        self._debug_display_manager.set_debug_filter(debug_filter)
    
    def get_debug_display_manager(self) -> OSCDebugDisplayManager:
        """获取调试显示管理器"""
        return self._debug_display_manager
        
    # ============ 生命周期管理 ============

    async def cleanup(self) -> None:
        """清理资源"""
        await self.stop_service()
        self._osc_client = None
        
        # 清理调试显示
        if self._debug_display_enabled:
            self._debug_display_manager.set_enabled(False)
                
        logger.info("OSC服务已清理")
