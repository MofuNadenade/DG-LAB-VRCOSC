import asyncio
import logging
from typing import Optional
import requests
from PySide6.QtCore import QObject, Signal

from config import save_settings, validate_ip
from core.service_controller import ServiceController
from gui.ui_interface import UIInterface
from models import ConnectionState, SettingsDict
from services.dglab_websocket_service import DGLabWebSocketService
from services.osc_service import OSCService
from services.osc_action_service import OSCActionService
from services.chatbox_service import ChatboxService

logger = logging.getLogger(__name__)


class ConnectionManager(QObject):
    """
    连接管理器 - ConnectionTab的业务逻辑组件
    使用组合模式，处理所有连接相关的业务逻辑
    """
    
    # 信号定义 - 通知UI状态变更
    public_ip_received = Signal(str)  # 公网IP获取成功
    validation_error = Signal(str)    # 验证错误
    
    def __init__(self, ui_interface: UIInterface):
        super().__init__()
        self.ui_interface = ui_interface
        self.settings: SettingsDict = ui_interface.settings
        self.server_task: Optional[asyncio.Task[None]] = None
    
    @property
    def service_controller(self) -> Optional[ServiceController]:
        """获取当前服务控制器"""
        return self.ui_interface.service_controller
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.server_task is not None and not self.server_task.done()
    
    def validate_remote_address(self, remote_address: str) -> bool:
        """验证远程地址"""
        if not remote_address:
            return True  # 空地址是允许的
        return validate_ip(remote_address)
    
    def save_network_settings(self, interface_name: str, ip: str, websocket_port: int, 
                            osc_port: int, language: str, enable_remote: bool, 
                            remote_address: str) -> None:
        """保存网络设置"""
        if 'websocket' not in self.settings:
            self.settings['websocket'] = {}
            
        self.settings['websocket']['interface'] = interface_name
        self.settings['websocket']['ip'] = ip
        self.settings['websocket']['port'] = websocket_port
        self.settings['websocket']['enable_remote'] = enable_remote
        self.settings['websocket']['remote_address'] = remote_address
        
        self.settings['osc_port'] = osc_port
        self.settings['language'] = language
        
        save_settings(self.settings)
        logger.info("网络设置已保存")
    
    async def get_public_ip(self) -> None:
        """获取公网IP地址"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.get('http://myip.ipip.net', timeout=5)
            )
            # 解析返回的文本: "当前 IP：xxx.xxx.xxx.xxx 来自于：xxx"
            public_ip = response.text.split('：')[1].split(' ')[0]
            logger.info(f"获取到公网IP: {public_ip}")
            
            # 发送信号通知UI
            self.public_ip_received.emit(public_ip)
            
        except Exception as e:
            logger.error(f"获取公网IP失败: {str(e)}")
            self.validation_error.emit(f"获取公网IP失败: {str(e)}")
    
    def start_connection(self, selected_ip: str, websocket_port: int, osc_port: int,
                        enable_remote: bool, remote_address: Optional[str] = None) -> None:
        """启动连接"""
        # 验证远程地址
        if enable_remote and remote_address and not self.validate_remote_address(remote_address):
            self.validation_error.emit("无效的远程IP地址")
            return
        
        logger.info(f"正在启动连接: {selected_ip}:{websocket_port}, OSC端口: {osc_port}")
        
        # 设置连接状态
        self.ui_interface.set_connection_state(ConnectionState.CONNECTING)
        
        # 启动服务器
        self.server_task = asyncio.create_task(
            self._run_server(selected_ip, websocket_port, osc_port, remote_address)
        )
    
    def stop_connection(self) -> None:
        """停止连接"""
        logger.info("正在停止连接")
        if self.server_task and not self.server_task.done():
            self.server_task.cancel()
    
    async def _run_server(self, ip: str, websocket_port: int, osc_port: int, 
                         remote_address: Optional[str]) -> None:
        """运行服务器 - 内部方法"""
        try:
            # 创建服务控制器(如果不存在)
            if not self.service_controller:
                dglab_service = DGLabWebSocketService(self.ui_interface, ip, websocket_port, remote_address)
                osc_service = OSCService(self.ui_interface, osc_port)
                osc_action_service = OSCActionService(dglab_service, self.ui_interface)
                chatbox_service = ChatboxService(self.ui_interface, osc_service, osc_action_service)
                
                controller = ServiceController(dglab_service, osc_service, osc_action_service, chatbox_service)
                self.ui_interface.set_service_controller(controller)
            
            # 启动所有服务
            if self.service_controller:
                success = await self.service_controller.start_all_services()
                if success:
                    logger.info("所有服务启动成功")
                    self.ui_interface.set_connection_state(ConnectionState.WAITING)
                    
                    # 保持服务运行
                    while self.server_task and not self.server_task.cancelled():
                        await asyncio.sleep(1)
                else:
                    logger.error("服务启动失败")
                    self.ui_interface.set_connection_state(ConnectionState.FAILED, "服务启动失败")
            else:
                logger.error("服务控制器未初始化")
                self.ui_interface.set_connection_state(ConnectionState.FAILED, "服务控制器未初始化")
        
        except asyncio.CancelledError:
            logger.info("连接任务被取消")
            # 停止所有服务
            if self.service_controller:
                await self.service_controller.stop_all_services()
            self.ui_interface.set_connection_state(ConnectionState.DISCONNECTED)
            raise
        
        except Exception as e:
            logger.error(f"连接运行异常: {str(e)}")
            self.ui_interface.set_connection_state(ConnectionState.FAILED, str(e))
        
        finally:
            self.server_task = None