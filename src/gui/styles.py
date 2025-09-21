"""
GUI通用样式定义
提供统一的按钮配色方案和样式
"""


class CommonColors:
    """通用按钮配色方案"""
    
    # 主要按钮 (保存、确认、开始等重要操作)
    BUTTON_PRIMARY_NORMAL = "#4CAF50"     # 绿色 - 正常状态
    BUTTON_PRIMARY_HOVER = "#45a049"      # 绿色 - 悬停状态
    BUTTON_PRIMARY_PRESSED = "#3d8b40"    # 绿色 - 按下状态
    BUTTON_PRIMARY_DISABLED = "#cccccc"   # 灰色 - 禁用状态
    
    # 次要按钮 (刷新、获取等一般操作)
    BUTTON_SECONDARY_NORMAL = "#2196F3"   # 蓝色 - 正常状态
    BUTTON_SECONDARY_HOVER = "#1976D2"    # 蓝色 - 悬停状态
    BUTTON_SECONDARY_PRESSED = "#1565C0"  # 蓝色 - 按下状态
    BUTTON_SECONDARY_DISABLED = "#cccccc" # 灰色 - 禁用状态
    
    # 警告按钮 (删除、断开连接等危险操作)
    BUTTON_WARNING_NORMAL = "#f44336"     # 红色 - 正常状态
    BUTTON_WARNING_HOVER = "#d32f2f"      # 红色 - 悬停状态
    BUTTON_WARNING_PRESSED = "#b71c1c"    # 红色 - 按下状态
    BUTTON_WARNING_DISABLED = "#cccccc"   # 灰色 - 禁用状态
    
    # 特殊按钮 (更新、应用等特殊操作)
    BUTTON_SPECIAL_NORMAL = "#FF9800"     # 橙色 - 正常状态
    BUTTON_SPECIAL_HOVER = "#F57C00"      # 橙色 - 悬停状态
    BUTTON_SPECIAL_PRESSED = "#E65100"    # 橙色 - 按下状态
    BUTTON_SPECIAL_DISABLED = "#cccccc"   # 灰色 - 禁用状态
    
    # 按钮文字颜色
    BUTTON_TEXT_NORMAL = "#FFFFFF"        # 正常状态文字
    BUTTON_TEXT_DISABLED = "#666666"      # 禁用状态文字
    
    @classmethod
    def get_primary_button_style(cls) -> str:
        """获取主要按钮样式"""
        return f"""
            QPushButton {{
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:enabled {{
                background-color: {cls.BUTTON_PRIMARY_NORMAL};
                color: {cls.BUTTON_TEXT_NORMAL};
            }}
            QPushButton:hover:enabled {{
                background-color: {cls.BUTTON_PRIMARY_HOVER};
                color: {cls.BUTTON_TEXT_NORMAL};
            }}
            QPushButton:pressed:enabled {{
                background-color: {cls.BUTTON_PRIMARY_PRESSED};
                color: {cls.BUTTON_TEXT_NORMAL};
            }}
            QPushButton:disabled {{
                background-color: {cls.BUTTON_PRIMARY_DISABLED};
                color: {cls.BUTTON_TEXT_DISABLED};
            }}
        """
    
    @classmethod
    def get_secondary_button_style(cls) -> str:
        """获取次要按钮样式"""
        return f"""
            QPushButton {{
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:enabled {{
                background-color: {cls.BUTTON_SECONDARY_NORMAL};
                color: {cls.BUTTON_TEXT_NORMAL};
            }}
            QPushButton:hover:enabled {{
                background-color: {cls.BUTTON_SECONDARY_HOVER};
                color: {cls.BUTTON_TEXT_NORMAL};
            }}
            QPushButton:pressed:enabled {{
                background-color: {cls.BUTTON_SECONDARY_PRESSED};
                color: {cls.BUTTON_TEXT_NORMAL};
            }}
            QPushButton:disabled {{
                background-color: {cls.BUTTON_SECONDARY_DISABLED};
                color: {cls.BUTTON_TEXT_DISABLED};
            }}
        """
    
    @classmethod
    def get_warning_button_style(cls) -> str:
        """获取警告按钮样式"""
        return f"""
            QPushButton {{
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:enabled {{
                background-color: {cls.BUTTON_WARNING_NORMAL};
                color: {cls.BUTTON_TEXT_NORMAL};
            }}
            QPushButton:hover:enabled {{
                background-color: {cls.BUTTON_WARNING_HOVER};
                color: {cls.BUTTON_TEXT_NORMAL};
            }}
            QPushButton:pressed:enabled {{
                background-color: {cls.BUTTON_WARNING_PRESSED};
                color: {cls.BUTTON_TEXT_NORMAL};
            }}
            QPushButton:disabled {{
                background-color: {cls.BUTTON_WARNING_DISABLED};
                color: {cls.BUTTON_TEXT_DISABLED};
            }}
        """
    
    @classmethod
    def get_special_button_style(cls) -> str:
        """获取特殊按钮样式"""
        return f"""
            QPushButton {{
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:enabled {{
                background-color: {cls.BUTTON_SPECIAL_NORMAL};
                color: {cls.BUTTON_TEXT_NORMAL};
            }}
            QPushButton:hover:enabled {{
                background-color: {cls.BUTTON_SPECIAL_HOVER};
                color: {cls.BUTTON_TEXT_NORMAL};
            }}
            QPushButton:pressed:enabled {{
                background-color: {cls.BUTTON_SPECIAL_PRESSED};
                color: {cls.BUTTON_TEXT_NORMAL};
            }}
            QPushButton:disabled {{
                background-color: {cls.BUTTON_SPECIAL_DISABLED};
                color: {cls.BUTTON_TEXT_DISABLED};
            }}
        """
