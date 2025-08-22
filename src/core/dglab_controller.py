import asyncio
from typing import Optional, Any, List

from pydglab_ws import StrengthData, FeedbackButton, Channel, RetCode, DGLabWSServer, DGLabLocalClient
from pythonosc import dispatcher, osc_server, udp_client
from PySide6.QtGui import QPixmap

from gui.ui_interface import UIInterface, ConnectionState
from util import generate_qrcode

# 导入新的服务类
from services.dglab_service import DGLabService
from services.osc_service import OSCService
from services.chatbox_service import ChatboxService

import logging
logger = logging.getLogger(__name__)


class DGLabController:
    """
    DGLab 控制器 - 纯服务容器
    
    这是一个极简的服务容器，不包含任何业务逻辑：
    
    唯一职责：
    1. 初始化和持有服务实例
    2. 提供只读数据访问属性
    3. 维护应用状态（app_status_online）
    
    所有功能都通过服务访问：
    - dglab_service: 完整的 DGLab 硬件控制
    - osc_service: OSC 消息处理  
    - chatbox_service: VRChat ChatBox 管理
    
    使用方式：
    - 读取数据: controller.last_strength
    - 硬件控制: controller.dglab_service.method()
    - OSC 通信: controller.osc_service.method()  
    - ChatBox: controller.chatbox_service.method()
    
    注意：此类不再包含任何方法，纯粹是数据容器。
    """
    
    def __init__(self, client: DGLabLocalClient, osc_client: udp_client.SimpleUDPClient, ui_callback: UIInterface) -> None:
        """
        初始化 DGLabController 实例
        
        Args:
            client: DGLab WebSocket 客户端
            osc_client: OSC UDP 客户端
            ui_callback: UI 回调接口
        """
        self.client: DGLabLocalClient = client
        self.osc_client: udp_client.SimpleUDPClient = osc_client
        self.ui_callback: UIInterface = ui_callback
        ui_callback.controller = self
        
        # 初始化服务
        self.dglab_service: DGLabService = DGLabService(client, ui_callback)
        self.osc_service: OSCService = OSCService(osc_client, ui_callback)
        self.chatbox_service: ChatboxService = ChatboxService(self.osc_service, ui_callback)
        # 设置服务间依赖
        self.chatbox_service.dglab_service = self.dglab_service
        
        # 应用状态
        self.app_status_online: bool = False
        
        # 启动定时任务
        self.chatbox_service.start_periodic_status_update()

    @property
    def last_strength(self) -> Optional[StrengthData]:
        """获取最后的强度数据"""
        return self.dglab_service.get_last_strength()

    @property
    def current_select_channel(self) -> Channel:
        """获取当前选中的通道"""
        return self.dglab_service.get_current_channel()

    @property
    def is_dynamic_bone_mode_a(self) -> bool:
        """获取A通道动骨模式状态"""
        return self.dglab_service.is_dynamic_bone_enabled(Channel.A)

    @property
    def is_dynamic_bone_mode_b(self) -> bool:
        """获取B通道动骨模式状态"""
        return self.dglab_service.is_dynamic_bone_enabled(Channel.B)

    @property
    def pulse_mode_a(self) -> int:
        """获取A通道波形模式"""
        return self.dglab_service.get_pulse_mode(Channel.A)

    @property
    def pulse_mode_b(self) -> int:
        """获取B通道波形模式"""
        return self.dglab_service.get_pulse_mode(Channel.B)

    @property
    def fire_mode_strength_step(self) -> int:
        """获取开火模式强度步进"""
        return self.dglab_service.fire_mode_strength_step



def handle_osc_message_task(address: str, list_object: List[DGLabController], *args: Any) -> None:
    """处理 OSC 消息任务"""
    asyncio.create_task(list_object[0].osc_service.handle_osc_message(address, *args))


async def run_server(ui_callback: UIInterface, ip: str, port: int, osc_port: int, remote_address: Optional[str] = None) -> None:
    """运行服务器并启动OSC服务器"""
    osc_transport: Optional[Any] = None
    try:
        async with DGLabWSServer(ip, port, 60) as server:
            client: DGLabLocalClient = server.new_local_client()
            logger.info("WebSocket 客户端已初始化")

            # 生成二维码
            url: Optional[str]
            if remote_address:
                url = client.get_qrcode(f"ws://{remote_address}:{port}")
                logger.info(f"使用远程地址生成二维码: ws://{remote_address}:{port}")
            else:
                url = client.get_qrcode(f"ws://{ip}:{port}")
                logger.info(f"使用本地地址生成二维码: ws://{ip}:{port}")
            
            if (not url):
                raise RuntimeError("无法生成二维码")
            qrcode_image: QPixmap = generate_qrcode(url)
            ui_callback.update_qrcode(qrcode_image)

            osc_client: udp_client.SimpleUDPClient = udp_client.SimpleUDPClient("127.0.0.1", 9000)
            # 初始化控制器
            controller: DGLabController = DGLabController(client, osc_client, ui_callback)
            logger.info("DGLabController 已初始化")
            # 将控制器设置到UI回调中
            ui_callback.set_controller(controller)
            # 在 controller 初始化后调用绑定函数
            ui_callback.bind_controller_settings()

            # 设置OSC服务器
            disp: dispatcher.Dispatcher = dispatcher.Dispatcher()
            # 面板控制对应的 OSC 地址
            disp.map("*", handle_osc_message_task, controller)

            event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
            if (not isinstance(event_loop, asyncio.BaseEventLoop)):
                raise RuntimeError("无法获取事件循环")
            
            try:
                osc_server_instance: osc_server.AsyncIOOSCUDPServer = osc_server.AsyncIOOSCUDPServer(("0.0.0.0", osc_port), disp, event_loop)
                osc_transport, _ = await osc_server_instance.create_serve_endpoint()
                logger.info(f"OSC Server Listening on port {osc_port}")
                # 服务器启动成功，设置等待设备连接状态
                ui_callback.set_connection_state(ConnectionState.WAITING)
            except OSError as osc_error:
                if osc_error.errno == 10048:  # Port already in use
                    error_message = f"OSC端口 {osc_port} 已被占用，请尝试使用其他端口或关闭占用该端口的程序"
                    logger.error(error_message)
                    ui_callback.set_connection_state(ConnectionState.ERROR, "OSC端口被占用")
                    return
                else:
                    raise  # Re-raise other OSErrors

            try:
                # 等待与 DG-Lab App 的绑定
                logger.info("等待 DG-Lab App 扫码绑定...")
                await client.bind()
                logger.info(f"已与 App {client.target_id} 成功绑定")
                
                # 开始处理数据流
                async for data in client.data_generator():
                    if isinstance(data, StrengthData):
                        # 首次接收数据时更新波形数据
                        if controller.last_strength is None:
                            asyncio.create_task(controller.dglab_service.update_pulse_data())
                        controller.dglab_service.update_strength_data(data)
                        logger.info(f"接收到数据包 - A通道: {data.a}, B通道: {data.b}")
                        
                        # 更新应用状态
                        controller.app_status_online = True
                        ui_callback.update_status(data)
                    # 接收 App 反馈按钮
                    elif isinstance(data, FeedbackButton):
                        logger.info(f"App 触发了反馈按钮：{data.name}")
                    # 接收 心跳 / App 断开通知
                    elif data == RetCode.CLIENT_DISCONNECTED:
                        logger.info("App 已断开连接，你可以尝试重新扫码进行连接绑定")
                        controller.app_status_online = False
                        ui_callback.on_client_disconnected()
                        
                        await client.rebind()
                        logger.info("重新绑定成功")
                        controller.app_status_online = True
                        ui_callback.on_client_reconnected()
            finally:
                # 确保OSC传输被正确关闭
                if osc_transport:
                    osc_transport.close()
                    logger.info("OSC传输已关闭")

    except asyncio.CancelledError:
        logger.info("服务器任务被取消")
        if osc_transport:
            osc_transport.close()
            logger.info("OSC传输已关闭（任务取消）")
        raise
    except Exception as e:
        # Handle specific errors and log them
        error_message = f"WebSocket 服务器启动失败: {str(e)}"
        logger.exception(error_message)

        # 启动过程中发生异常，恢复按钮状态为可点击的红色
        ui_callback.set_connection_state(ConnectionState.FAILED, error_message)
    finally:
        # 最终清理，确保传输被关闭
        if osc_transport:
            osc_transport.close()
            logger.info("OSC传输已关闭（最终清理）")