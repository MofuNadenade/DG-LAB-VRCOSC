"""
OSC动作管理模块

提供OSC动作的定义和注册管理功能。
"""

from typing import Set, Optional, List, Dict

from .osc_common import OSCAction, OSCActionCallback, OSCActionType, ActionCallback


class OSCActionRegistry:
    """OSC动作注册表"""

    def __init__(self) -> None:
        super().__init__()
        self._actions: List[OSCAction] = []
        self._actions_by_name: Dict[str, OSCAction] = {}
        self._actions_by_type: Dict[OSCActionType, List[OSCAction]] = {}
        self._actions_by_id: Dict[int, OSCAction] = {}  # 按ID索引
        self._next_action_id: int = 1  # 下一个可用的动作ID
        self._action_added_callbacks: List[ActionCallback] = []
        self._action_removed_callbacks: List[ActionCallback] = []

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

    @property
    def actions_by_id(self) -> Dict[int, OSCAction]:
        """获取按ID索引的动作字典（只读）"""
        return self._actions_by_id.copy()

    def get_action_by_name(self, name: str) -> Optional[OSCAction]:
        """根据名称获取动作"""
        return self._actions_by_name.get(name)

    def get_action_by_id(self, action_id: int) -> Optional[OSCAction]:
        """根据ID获取动作"""
        return self._actions_by_id.get(action_id)

    def has_action_name(self, name: str) -> bool:
        """检查是否存在指定名称的动作"""
        return name in self._actions_by_name

    def has_action_id(self, action_id: int) -> bool:
        """检查是否存在指定ID的动作"""
        return action_id in self._actions_by_id

    def get_action_count(self) -> int:
        """获取动作总数"""
        return len(self._actions)

    def _get_next_action_id(self) -> int:
        """获取下一个可用的动作ID"""
        current_id = self._next_action_id
        self._next_action_id += 1
        return current_id

    def clear_all_actions(self) -> None:
        """清除所有动作（用于重新注册）"""
        self._actions.clear()
        self._actions_by_name.clear()
        self._actions_by_type.clear()
        self._actions_by_id.clear()

        for action_type in OSCActionType:
            self._actions_by_type[action_type] = []

    def add_action_added_callback(self, callback: ActionCallback) -> None:
        if callback not in self._action_added_callbacks:
            self._action_added_callbacks.append(callback)

    def remove_action_added_callback(self, callback: ActionCallback) -> None:
        if callback in self._action_added_callbacks:
            self._action_added_callbacks.remove(callback)

    def add_action_removed_callback(self, callback: ActionCallback) -> None:
        if callback not in self._action_removed_callbacks:
            self._action_removed_callbacks.append(callback)

    def remove_action_removed_callback(self, callback: ActionCallback) -> None:
        if callback in self._action_removed_callbacks:
            self._action_removed_callbacks.remove(callback)

    def notify_action_added(self, action: OSCAction) -> None:
        for callback in self._action_added_callbacks:
            callback(action)

    def notify_action_removed(self, action: OSCAction) -> None:
        for callback in self._action_removed_callbacks:
            callback(action)

    def register_action(self, name: str, callback: OSCActionCallback,
                        action_type: OSCActionType = OSCActionType.CUSTOM,
                        tags: Optional[Set[str]] = None) -> OSCAction:
        """注册动作（增强版本）"""
        action_id = self._get_next_action_id()
        action = OSCAction(action_id, name, callback, action_type, tags)
        self._actions.append(action)
        self._actions_by_name[name] = action
        self._actions_by_id[action_id] = action
        self._actions_by_type[action_type].append(action)

        # 通知观察者
        self.notify_action_added(action)

        return action

    def unregister_action(self, action_id: int) -> bool:
        """通过ID注销动作
        
        Args:
            action_id: 要注销的动作ID
            
        Returns:
            bool: 注销成功返回True，如果ID不存在返回False
        """
        action = self._actions_by_id.get(action_id)
        if not action:
            return False
            
        # 从所有索引中移除
        self._actions.remove(action)
        self._actions_by_name.pop(action.name, None)
        self._actions_by_id.pop(action_id, None)
        self._actions_by_type[action.action_type].remove(action)
        
        # 通知观察者
        self.notify_action_removed(action)
        
        return True

    def unregister_action_by_instance(self, action: OSCAction) -> bool:
        """通过动作实例来注销动作
        
        Args:
            action: 要注销的动作实例
            
        Returns:
            bool: 注销成功返回True，如果动作不存在返回False
        """
        return self.unregister_action(action.id)

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

    def update_action_name(self, action_id: int, new_name: str) -> bool:
        """通过ID更新动作名称
        
        Args:
            action_id: 要更新的动作ID
            new_name: 新的动作名称
            
        Returns:
            bool: 更新成功返回True，如果ID不存在返回False
        """
        action = self._actions_by_id.get(action_id)
        if not action:
            return False
            
        old_name = action.name
        action.name = new_name.strip()
        
        # 更新名称索引
        self._actions_by_name.pop(old_name, None)
        self._actions_by_name[action.name] = action
        
        return True

    def update_action_callback(self, action_id: int, new_callback: OSCActionCallback) -> bool:
        """通过ID更新动作回调函数
        
        Args:
            action_id: 要更新的动作ID
            new_callback: 新的回调函数
            
        Returns:
            bool: 更新成功返回True，如果ID不存在返回False
        """
        action = self._actions_by_id.get(action_id)
        if not action:
            return False
            
        action.callback = new_callback
        return True

    def update_action_type(self, action_id: int, new_type: OSCActionType) -> bool:
        """通过ID更新动作类型
        
        Args:
            action_id: 要更新的动作ID
            new_type: 新的动作类型
            
        Returns:
            bool: 更新成功返回True，如果ID不存在返回False
        """
        action = self._actions_by_id.get(action_id)
        if not action:
            return False
            
        old_type = action.action_type
        action.action_type = new_type
        
        # 更新类型索引
        self._actions_by_type[old_type].remove(action)
        self._actions_by_type[new_type].append(action)
        
        return True

    def update_action_tags(self, action_id: int, new_tags: Set[str]) -> bool:
        """通过ID更新动作标签
        
        Args:
            action_id: 要更新的动作ID
            new_tags: 新的标签集合
            
        Returns:
            bool: 更新成功返回True，如果ID不存在返回False
        """
        action = self._actions_by_id.get(action_id)
        if not action:
            return False
            
        action.tags = new_tags or set()
        return True
