from typing import Optional

from models import StrengthData, Channel
from gui.ui_interface import UIInterface

# 导入服务类
from services.dglab_service_interface import IDGLabService
from services.dglab_websocket_service import DGLabWebSocketService
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
    - dglab_service: 设备控制抽象接口（支持WebSocket/蓝牙等）
    - osc_service: OSC 消息处理  
    - chatbox_service: VRChat ChatBox 管理
    
    使用方式：
    - 读取数据: controller.last_strength
    - 硬件控制: controller.dglab_service.method()
    - OSC 通信: controller.osc_service.method()  
    - ChatBox: controller.chatbox_service.method()
    
    注意：此类不再包含任何方法，纯粹是数据容器。
    """
    
    def __init__(self, ui_interface: UIInterface) -> None:
        """
        初始化 DGLabController 实例
        
        Args:
            ui_interface: UI 回调接口
        """
        self.ui_interface: UIInterface = ui_interface
        ui_interface.controller = self
        
        # 初始化服务（不再需要client参数）
        self.dglab_service: IDGLabService = DGLabWebSocketService(ui_interface)
        self.osc_service: OSCService = OSCService(ui_interface)
        self.chatbox_service: ChatboxService = ChatboxService(self.dglab_service, self.osc_service, ui_interface)
        
        # 设置服务间的引用关系
        self.osc_service.set_dglab_service(self.dglab_service)
        self.osc_service.set_chatbox_service(self.chatbox_service)
        
        # 应用状态
        self.app_status_online: bool = False
        
        # 启动定时任务
        self.chatbox_service.start_periodic_status_update()

    # ============ 向后兼容属性 ============

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
