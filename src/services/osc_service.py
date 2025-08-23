"""
OSC服务 - 完全封装OSC功能
包括OSC服务器管理、消息处理、动作注册等所有OSC相关功能
"""

import asyncio
import logging
from typing import Any, Optional, Callable, Awaitable, TYPE_CHECKING
from pythonosc import dispatcher, osc_server, udp_client

if TYPE_CHECKING:
    from gui.ui_interface import UIInterface
    from services.dglab_service_interface import IDGLabService

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
    
    def __init__(self, ui_interface: 'UIInterface') -> None:
        """
        初始化OSC服务
        
        Args:
            ui_interface: UI接口，用于访问地址和绑定注册表
        """
        self._ui_interface: 'UIInterface' = ui_interface
        self._osc_client: Optional[udp_client.SimpleUDPClient] = None
        self._osc_server_instance: Optional[osc_server.AsyncIOOSCUDPServer] = None
        self._osc_transport: Optional[Any] = None
        self._dglab_service: Optional['IDGLabService'] = None
        self._chatbox_service: Optional[Any] = None  # 避免循环导入
        self._is_running: bool = False
        
        # OSC服务器配置
        self._osc_port: int = 9001
        self._vrchat_port: int = 9000
    
    def set_dglab_service(self, dglab_service: 'IDGLabService') -> None:
        """设置DGLab服务引用（用于OSC动作回调）"""
        self._dglab_service = dglab_service
        # 重新注册OSC动作
        if self._dglab_service:
            self._register_osc_actions()
    
    def set_chatbox_service(self, chatbox_service: Any) -> None:
        """设置ChatBox服务引用"""
        self._chatbox_service = chatbox_service
    
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
            disp.map("*", self._handle_osc_message_internal)
            
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
                from gui.ui_interface import ConnectionState
                self._ui_interface.set_connection_state(ConnectionState.ERROR, "OSC端口被占用")
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
    
    def _handle_osc_message_internal(self, address: str, *args: Any) -> None:
        """OSC消息内部处理方法（同步）"""
        # 创建异步任务处理消息
        asyncio.create_task(self.handle_osc_message(address, *args))
    
    async def handle_osc_message(self, address: str, *args: Any) -> None:
        """
        处理OSC消息
        
        Args:
            address: OSC地址
            *args: OSC参数
        """
        logger.debug(f"收到OSC消息: {address} 参数: {args}")
        
        # 通过UI接口的绑定注册表处理消息
        address_obj = self._ui_interface.address_registry.get_address_by_code(address)
        if address_obj:
            await self._ui_interface.binding_registry.handle(address_obj, *args)
        else:
            logger.debug(f"未找到OSC地址绑定: {address}")
    
    def _register_osc_actions(self) -> None:
        """注册OSC动作（内部方法）"""
        if not self._dglab_service:
            logger.warning("DGLab服务未设置，无法注册OSC动作")
            return
        
        from core.osc_common import OSCActionType
        from models import Channel
        
        # 清除现有动作（避免重复注册）
        self._ui_interface.action_registry.clear_all_actions()
        
        # 检查DGLab服务是否可用
        if not self._dglab_service:
            logger.error("DGLab服务未设置，无法注册OSC动作")
            return
        
        dglab = self._dglab_service  # 简化引用
        
        # 注册通道控制操作
        self._ui_interface.action_registry.register_action(
            "A通道触碰",
            self._create_async_wrapper(lambda *args: dglab.set_float_output(args[0], Channel.A)),
            OSCActionType.CHANNEL_CONTROL, {"channel_a", "touch"}
        )
        
        self._ui_interface.action_registry.register_action(
            "B通道触碰", 
            self._create_async_wrapper(lambda *args: dglab.set_float_output(args[0], Channel.B)),
            OSCActionType.CHANNEL_CONTROL, {"channel_b", "touch"}
        )
        
        self._ui_interface.action_registry.register_action(
            "当前通道触碰",
            self._create_async_wrapper(lambda *args: dglab.set_float_output(
                args[0], dglab.get_current_channel()
            )),
            OSCActionType.CHANNEL_CONTROL, {"current_channel", "touch"}
        )
        
        # 注册面板控制操作
        self._ui_interface.action_registry.register_action(
            "面板控制",
            self._create_async_wrapper(lambda *args: dglab.set_panel_control(args[0])),
            OSCActionType.PANEL_CONTROL, {"panel"}
        )
        
        self._ui_interface.action_registry.register_action(
            "数值调节",
            self._create_async_wrapper(lambda *args: dglab.set_strength_step(args[0])),
            OSCActionType.PANEL_CONTROL, {"value_adjust"}
        )
        
        self._ui_interface.action_registry.register_action(
            "通道调节",
            self._create_async_wrapper(lambda *args: dglab.set_channel(args[0])),
            OSCActionType.PANEL_CONTROL, {"channel_adjust"}
        )
        
        # 注册强度控制操作
        self._ui_interface.action_registry.register_action(
            "设置模式",
            self._create_async_wrapper(lambda *args: dglab.set_mode(
                args[0], dglab.get_current_channel()
            )),
            OSCActionType.STRENGTH_CONTROL, {"mode"}
        )
        
        self._ui_interface.action_registry.register_action(
            "重置强度",
            self._create_async_wrapper(lambda *args: dglab.reset_strength(
                args[0], dglab.get_current_channel()
            )),
            OSCActionType.STRENGTH_CONTROL, {"reset"}
        )
        
        self._ui_interface.action_registry.register_action(
            "降低强度",
            self._create_async_wrapper(lambda *args: dglab.decrease_strength(
                args[0], dglab.get_current_channel()
            )),
            OSCActionType.STRENGTH_CONTROL, {"decrease"}
        )
        
        self._ui_interface.action_registry.register_action(
            "增加强度",
            self._create_async_wrapper(lambda *args: dglab.increase_strength(
                args[0], dglab.get_current_channel()
            )),
            OSCActionType.STRENGTH_CONTROL, {"increase"}
        )
        
        self._ui_interface.action_registry.register_action(
            "一键开火",
            self._create_async_wrapper(lambda *args: dglab.strength_fire_mode(
                args[0], 
                dglab.get_current_channel(), 
                dglab.fire_mode_strength_step, 
                dglab.get_last_strength()
            )),
            OSCActionType.STRENGTH_CONTROL, {"fire"}
        )
        
        # 注册ChatBox控制操作
        if self._chatbox_service:
            chatbox = self._chatbox_service  # 简化引用
            self._ui_interface.action_registry.register_action(
                "ChatBox状态开关",
                self._create_async_wrapper(lambda *args: chatbox.toggle_chatbox(args[0])),
                OSCActionType.CHATBOX_CONTROL, {"toggle"}
            )
        
        logger.info("OSC动作注册完成")
    
    def _create_async_wrapper(self, func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[None]]:
        """创建异步包装器"""
        async def wrapper(*args: Any) -> None:
            try:
                await func(*args)
            except Exception as e:
                logger.error(f"OSC动作执行失败: {e}")
        return wrapper
    
    # ============ VRChat通信方法 ============
    
    def send_message_to_vrchat_chatbox(self, message: str) -> None:
        """
        发送消息到VRChat聊天框
        
        Args:
            message: 要发送的消息
        """
        if not self._osc_client:
            logger.warning("OSC客户端未初始化，无法发送消息")
            return
        
        try:
            self._osc_client.send_message("/chatbox/input", [message, True, False])
            logger.debug(f"已发送ChatBox消息: {message}")
        except Exception as e:
            logger.error(f"发送ChatBox消息失败: {e}")
    
    def send_value_to_vrchat(self, path: str, value: Any) -> None:
        """
        发送值到VRChat
        
        Args:
            path: OSC路径
            value: 要发送的值
        """
        if not self._osc_client:
            logger.warning("OSC客户端未初始化，无法发送值")
            return
        
        try:
            self._osc_client.send_message(path, value)
            logger.debug(f"已发送OSC值: {path} = {value}")
        except Exception as e:
            logger.error(f"发送OSC值失败: {e}")
    
    # ============ 生命周期管理 ============
    
    async def cleanup(self) -> None:
        """清理资源"""
        await self.stop_server()
        self._dglab_service = None
        self._chatbox_service = None
        self._osc_client = None
        logger.info("OSC服务已清理")