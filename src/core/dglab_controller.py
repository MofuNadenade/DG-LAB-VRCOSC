from services.chatbox_service import ChatboxService
from services.dglab_service_interface import IDGLabDeviceService
from services.osc_service import OSCService
from services.osc_action_service import OSCActionService


class DGLabController:
    """
    DGLab 控制器 - 服务容器
    """

    def __init__(self, dglab_device_service: IDGLabDeviceService, osc_service: OSCService, osc_action_service: OSCActionService, chatbox_service: ChatboxService) -> None:
        """
        初始化 DGLabController 实例
        """
        super().__init__()

        self.dglab_device_service: IDGLabDeviceService = dglab_device_service
        self.osc_service: OSCService = osc_service
        self.osc_action_service: OSCActionService = osc_action_service
        self.chatbox_service: ChatboxService = chatbox_service

