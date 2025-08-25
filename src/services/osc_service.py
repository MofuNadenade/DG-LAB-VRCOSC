"""
OSC服务 - 完全封装OSC功能
包括OSC服务器管理、消息处理、动作注册等所有OSC相关功能
"""

import asyncio
import logging
from typing import Optional
from pythonosc import dispatcher, osc_server, udp_client

from core.core_interface import CoreInterface
from models import ConnectionState, OSCValue

logger = logging.getLogger(__name__)


class OSCService:
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
    
    def __init__(self, core_interface: CoreInterface) -> None:
        """
        初始化OSC服务
        
        Args:
            ui_interface: UI接口，用于访问地址和绑定注册表
        """
        super().__init__()

        self._core_interface = core_interface
        self._osc_client: Optional[udp_client.SimpleUDPClient] = None
        self._osc_server_instance: Optional[osc_server.AsyncIOOSCUDPServer] = None
        self._osc_transport: Optional[asyncio.BaseTransport] = None
        self._is_running: bool = False
        
        # OSC服务器配置
        self._osc_port: int = 9001
        self._vrchat_port: int = 9000
    
    async def start_server(self, osc_port: int) -> bool:
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
        
        self._osc_port = osc_port
        
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
                ("0.0.0.0", osc_port), disp, event_loop
            )
            self._osc_transport, _ = await self._osc_server_instance.create_serve_endpoint()
            
            self._is_running = True
            logger.info(f"OSC服务器已启动，监听端口: {osc_port}")
            return True
            
        except OSError as e:
            if e.errno == 10048:  # Port already in use
                error_message = f"OSC端口 {osc_port} 已被占用，请尝试使用其他端口或关闭占用该端口的程序"
                logger.error(error_message)
                # 通过UI接口报告错误
                self._core_interface.set_connection_state(ConnectionState.ERROR, "OSC端口被占用")
                return False
            else:
                logger.error(f"OSC服务器启动失败: {e}")
                raise
        except Exception as e:
            logger.error(f"OSC服务器启动异常: {e}")
            return False
    
    async def stop_server(self) -> None:
        """停止OSC服务器"""
        if not self._is_running:
            return
        
        if self._osc_transport:
            self._osc_transport.close()
            logger.info("OSC服务器已停止")
        
        self._osc_transport = None
        self._osc_server_instance = None
        self._is_running = False
    
    def is_running(self) -> bool:
        """检查OSC服务器运行状态"""
        return self._is_running
    
    def _handle_osc_message_internal(self, address: str, *args: OSCValue) -> None:
        """OSC消息内部处理方法（同步）"""
        # 创建异步任务处理消息
        asyncio.create_task(self.handle_osc_message(address, *args))
    
    async def handle_osc_message(self, address: str, *args: OSCValue) -> None:
        """
        处理OSC消息
        
        Args:
            address: OSC地址
            *args: OSC参数
        """
        
        # 通过UI接口的绑定注册表处理消息
        address_obj = self._core_interface.registries.address_registry.get_address_by_code(address)
        if address_obj:
            logger.debug(f"收到OSC消息: {address} 参数: {args}")
            await self._core_interface.registries.binding_registry.handle(address_obj, *args)
    
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
    
    # ============ 生命周期管理 ============
    
    async def cleanup(self) -> None:
        """清理资源"""
        await self.stop_server()
        self._osc_client = None
        logger.info("OSC服务已清理")