"""
OSC动作管理模块

提供OSC动作的定义和注册管理功能。
"""

from typing import Optional, List, Dict, Type

from models import OSCActionTypedCallback, OSCValue

from .osc_common import OSCAction, ActionCallback


class OSCActionRegistry:
    """OSC动作注册表"""

    def __init__(self) -> None:
        super().__init__()
        self._actions: List[OSCAction] = []
        self._actions_by_name: Dict[str, OSCAction] = {}
        self._actions_by_id: Dict[int, OSCAction] = {}  # 按ID索引
        self._next_action_id: int = 1  # 下一个可用的动作ID
        self._action_added_callbacks: List[ActionCallback] = []
        self._action_removed_callbacks: List[ActionCallback] = []

    @property
    def actions(self) -> List[OSCAction]:
        """获取所有动作列表（只读）"""
        return self._actions.copy()

    @property
    def actions_by_name(self) -> Dict[str, OSCAction]:
        """获取按名称索引的动作字典（只读）"""
        return self._actions_by_name.copy()

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
        self._actions_by_id.clear()

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

    def register_action[T: OSCValue](self, name: str, callback: OSCActionTypedCallback[T], *types: Type[T]) -> OSCAction:
        """注册动作（增强版本）"""
        action_id = self._get_next_action_id()
        action = OSCAction(action_id, name, callback, list(types))
        self._actions.append(action)
        self._actions_by_name[name] = action
        self._actions_by_id[action_id] = action

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
