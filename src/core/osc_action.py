"""
OSC动作管理模块

提供OSC动作的定义和注册管理功能。
"""

from typing import Set, Optional, List, Dict

from .osc_common import OSCAction, OSCActionCallback, OSCActionType, OSCRegistryObserver


class OSCActionRegistry:
    """OSC动作注册表"""

    def __init__(self) -> None:
        super().__init__()
        self._actions: List[OSCAction] = []
        self._actions_by_name: Dict[str, OSCAction] = {}
        self._actions_by_type: Dict[OSCActionType, List[OSCAction]] = {}
        self._observers: List[OSCRegistryObserver] = []

        # 初始化类型字典
        for action_type in OSCActionType:
            self._actions_by_type[action_type] = []

    @property
    def actions(self) -> List[OSCAction]:
        """获取所有动作列表（只读）"""
        return self._actions.copy()

    @property
    def actions_by_name(self) -> Dict[str, OSCAction]:
        """获取按名称索引的动作字典（只读）"""
        return self._actions_by_name.copy()

    @property
    def actions_by_type(self) -> Dict[OSCActionType, List[OSCAction]]:
        """获取按类型索引的动作字典（只读）"""
        return {k: v.copy() for k, v in self._actions_by_type.items()}

    def get_action_by_name(self, name: str) -> Optional[OSCAction]:
        """根据名称获取动作"""
        return self._actions_by_name.get(name)

    def has_action_name(self, name: str) -> bool:
        """检查是否存在指定名称的动作"""
        return name in self._actions_by_name

    def get_action_count(self) -> int:
        """获取动作总数"""
        return len(self._actions)

    def clear_all_actions(self) -> None:
        """清除所有动作（用于重新注册）"""
        self._actions.clear()
        self._actions_by_name.clear()
        self._actions_by_type.clear()

        for action_type in OSCActionType:
            self._actions_by_type[action_type] = []

    def add_observer(self, observer: OSCRegistryObserver) -> None:
        """添加观察者"""
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: OSCRegistryObserver) -> None:
        """移除观察者"""
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_action_added(self, action: OSCAction) -> None:
        """通知观察者动作已添加"""
        for observer in self._observers:
            observer.on_action_added(action)

    def notify_action_removed(self, action: OSCAction) -> None:
        """通知观察者动作已移除"""
        for observer in self._observers:
            observer.on_action_removed(action)

    def register_action(self, name: str, callback: OSCActionCallback,
                        action_type: OSCActionType = OSCActionType.CUSTOM,
                        tags: Optional[Set[str]] = None) -> OSCAction:
        """注册动作（增强版本）"""
        action = OSCAction(name, callback, action_type, tags)
        self._actions.append(action)
        self._actions_by_name[name] = action
        self._actions_by_type[action_type].append(action)

        # 通知观察者
        self.notify_action_added(action)

        return action

    def unregister_action(self, action: OSCAction) -> None:
        """移除动作"""
        if action in self._actions:
            self._actions.remove(action)
            if action.name in self._actions_by_name:
                del self._actions_by_name[action.name]
            if action in self._actions_by_type[action.action_type]:
                self._actions_by_type[action.action_type].remove(action)

            # 通知观察者
            self.notify_action_removed(action)

    def get_actions_by_type(self, action_type: OSCActionType) -> List[OSCAction]:
        """按类型获取动作"""
        return self._actions_by_type[action_type].copy()

    def get_categorized_actions(self) -> Dict[OSCActionType, List[OSCAction]]:
        """获取分类后的动作"""
        return {k: v.copy() for k, v in self._actions_by_type.items() if v}

    def get_actions_by_tags(self, tags: Set[str]) -> List[OSCAction]:
        """根据标签获取动作"""
        matching_actions: List[OSCAction] = []
        for action in self._actions:
            if action.tags.intersection(tags):
                matching_actions.append(action)
        return matching_actions
