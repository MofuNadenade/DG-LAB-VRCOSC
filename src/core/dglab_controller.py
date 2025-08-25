from services.chatbox_service import ChatboxService
from services.dglab_service_interface import IDGLabService
from services.osc_service import OSCService


class DGLabController:
    """
    DGLab 控制器 - 服务容器
    
    职责：
    - 初始化和管理服务实例
    - 维护应用状态
    
    服务：
    - dglab_service: 设备控制接口
    - osc_service: OSC 消息处理  
    - chatbox_service: VRChat ChatBox 管理
    """
    
    def __init__(self, dglab_service: IDGLabService, osc_service: OSCService, chatbox_service: ChatboxService) -> None:
        """
        初始化 DGLabController 实例
        """
        super().__init__()

        self.dglab_service: IDGLabService = dglab_service
        self.osc_service: OSCService = osc_service
        self.chatbox_service: ChatboxService = chatbox_service

        self.app_status_online: bool = False
