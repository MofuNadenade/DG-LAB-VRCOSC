from services.chatbox_service import ChatboxService
from services.dglab_service_interface import IDGLabDeviceService
from services.osc_service import OSCService
from services.osc_action_service import OSCActionService
from services.service_interface import IService
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class ServiceController:
    """
    服务控制器
    """

    def __init__(self, dglab_device_service: IDGLabDeviceService, osc_service: OSCService, osc_action_service: OSCActionService, chatbox_service: ChatboxService) -> None:
        """
        初始化 ServiceController 实例
        """
        super().__init__()

        self.dglab_device_service: IDGLabDeviceService = dglab_device_service
        self.osc_service: OSCService = osc_service
        self.osc_action_service: OSCActionService = osc_action_service
        self.chatbox_service: ChatboxService = chatbox_service
        
        # 统一的服务列表，按启动顺序排列
        self._services: List[Tuple[str, IService]] = [
            ("DG-Lab设备服务", self.dglab_device_service),
            ("OSC服务", self.osc_service),
            ("OSC动作服务", self.osc_action_service),
            ("ChatBox服务", self.chatbox_service),
        ]

    async def start_all_services(self) -> bool:
        """
        启动所有服务
        
        Returns:
            bool: 所有服务是否都成功启动
        """
        logger.info("开始启动所有服务...")
        
        started_services: List[Tuple[str, IService]] = []
        
        # 按顺序启动所有服务
        for service_name, service in self._services:
            try:
                logger.info(f"正在启动 {service_name}...")
                if await service.start_service():
                    started_services.append((service_name, service))
                    logger.info(f"{service_name} 启动成功")
                else:
                    logger.error(f"{service_name} 启动失败")
                    # 停止已启动的服务
                    await self._stop_services(started_services)
                    return False
            except Exception as e:
                logger.error(f"启动 {service_name} 时发生异常: {e}")
                # 停止已启动的服务
                await self._stop_services(started_services)
                return False

        logger.info("所有服务启动成功")
        return True

    async def stop_all_services(self) -> None:
        """停止所有服务"""
        logger.info("开始停止所有服务...")
        await self._stop_services(self._services)
        logger.info("所有服务已停止")

    async def _stop_services(self, services: List[Tuple[str, IService]]) -> None:
        """
        停止指定的服务列表
        
        Args:
            services: 要停止的服务列表，按启动顺序排列
        """
        try:
            # 按相反顺序停止服务
            for service_name, service in reversed(services):
                try:
                    logger.info(f"正在停止 {service_name}...")
                    await service.stop_service()
                    logger.info(f"{service_name} 已停止")
                except Exception as e:
                    logger.error(f"停止 {service_name} 时发生异常: {e}")
        except Exception as e:
            logger.error(f"停止服务列表时发生异常: {e}")
