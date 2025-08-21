"""
OSC动作管理模块

提供OSC动作的定义和注册管理功能。
"""

from typing import Any, Set, Optional, List, Dict

from .osc_common import OSCActionType, OSCAddressCallback, OSCAddressValidator, OSCRegistryObserver


class OSCAction:
    """OSC动作"""
    
    def __init__(self, index: int, name: str, callback: OSCAddressCallback, 
                 action_type: OSCActionType = OSCActionType.CUSTOM,
                 tags: Optional[Set[str]] = None) -> None:
        # 验证输入
        name_valid, name_error = OSCAddressValidator.validate_action_name(name)
        if not name_valid:
            raise ValueError(f"无效的动作名称: {name_error}")
            
        self.index: int = index
        self.name: str = name.strip()
        self.callback: OSCAddressCallback = callback
        self.action_type: OSCActionType = action_type
        self.tags: Set[str] = tags or set()
    
    async def handle(self, *args: Any) -> None:
        await self.callback(*args)
    
    def __str__(self) -> str:
        return f"OSCAction(name='{self.name}', type='{self.action_type.value}')"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OSCAction):
            return False
        return self.name == other.name and self.action_type == other.action_type
    
    def __hash__(self) -> int:
        return hash((self.name, self.action_type))


class OSCActionRegistry:
    """OSC动作注册表"""
    
    def __init__(self) -> None:
        self.actions: List[OSCAction] = []
        self.actions_by_name: Dict[str, OSCAction] = {}
        self.actions_by_type: Dict[OSCActionType, List[OSCAction]] = {}
        self.observers: List[OSCRegistryObserver] = []
        
        # 初始化类型字典
        for action_type in OSCActionType:
            self.actions_by_type[action_type] = []

    def add_observer(self, observer: OSCRegistryObserver) -> None:
        """添加观察者"""
        if observer not in self.observers:
            self.observers.append(observer)
    
    def remove_observer(self, observer: OSCRegistryObserver) -> None:
        """移除观察者"""
        if observer in self.observers:
            self.observers.remove(observer)
    
    def notify_action_added(self, action: OSCAction) -> None:
        """通知观察者动作已添加"""
        for observer in self.observers:
            observer.on_action_added(action)
    
    def notify_action_removed(self, action: OSCAction) -> None:
        """通知观察者动作已移除"""
        for observer in self.observers:
            observer.on_action_removed(action)

    def register_action(self, name: str, callback: OSCAddressCallback, 
                       action_type: OSCActionType = OSCActionType.CUSTOM,
                       tags: Optional[Set[str]] = None) -> OSCAction:
        """注册动作（增强版本）"""
        action = OSCAction(len(self.actions), name, callback, action_type, tags)
        self.actions.append(action)
        self.actions_by_name[name] = action
        self.actions_by_type[action_type].append(action)
        
        # 通知观察者
        self.notify_action_added(action)
        
        return action
    
    def remove_action(self, action: OSCAction) -> None:
        """移除动作"""
        if action in self.actions:
            self.actions.remove(action)
            if action.name in self.actions_by_name:
                del self.actions_by_name[action.name]
            if action in self.actions_by_type[action.action_type]:
                self.actions_by_type[action.action_type].remove(action)
            
            # 重新索引
            for i, a in enumerate(self.actions):
                a.index = i
            
            # 通知观察者
            self.notify_action_removed(action)
    
    def get_actions_by_type(self, action_type: OSCActionType) -> List[OSCAction]:
        """按类型获取动作"""
        return self.actions_by_type[action_type].copy()
    
    def get_categorized_actions(self) -> Dict[OSCActionType, List[OSCAction]]:
        """获取分类后的动作"""
        return {k: v.copy() for k, v in self.actions_by_type.items() if v}
    
    def get_actions_by_tags(self, tags: Set[str]) -> List[OSCAction]:
        """根据标签获取动作"""
        matching_actions = []
        for action in self.actions:
            if action.tags.intersection(tags):
                matching_actions.append(action)
        return matching_actions
