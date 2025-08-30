"""
服务接口协议定义

定义了所有服务的通用异步接口，确保服务生命周期管理的一致性。
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class IService(Protocol):
    """通用异步服务接口协议
    
    所有服务都应实现此接口以确保统一的异步生命周期管理。
    """
    
    async def start_service(self) -> bool:
        """启动服务
        
        Returns:
            bool: 启动是否成功
        """
        ...
    
    async def stop_service(self) -> None:
        """停止服务并清理资源"""
        ...
    
    def is_service_running(self) -> bool:
        """检查服务运行状态"""
        ...