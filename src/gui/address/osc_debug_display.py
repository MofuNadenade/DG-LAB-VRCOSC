"""
OSC调试显示管理器
在屏幕左上角显示OSC消息调试信息，支持渐显渐隐效果
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy, QApplication

from models import OSCValue
from gui.address.osc_debug_filter import OSCDebugFilter

logger = logging.getLogger(__name__)


class OSCDebugItem:
    """OSC调试信息项"""
    
    def __init__(self, address: str, values: List[OSCValue], types: str) -> None:
        super().__init__()
        self.address = address
        self.values = values
        self.types = types
        self.first_seen_time = time.time()
        self.last_update_time = time.time()
        self.display_order = 0  # 显示顺序
        

class OSCDebugOverlay(QWidget):
    """OSC调试信息覆盖窗口"""
    
    def __init__(self) -> None:
        super().__init__()

        self.label_pool: List[QLabel] = []
        self.address_max_widths: Dict[str, int] = {}
        self._item_update_times: Dict[str, float] = {}
        self._current_items_with_opacity: List[Tuple[str, float]] = []
        
        # UI组件类型注解
        self.content_layout: QVBoxLayout
        self.animation_timer: QTimer
        
        self._setup_window()
        self._setup_ui()
        
    def _setup_window(self) -> None:
        """设置窗口属性"""
        # 窗口标志：置顶、无边框、工具窗口、不激活、透明输入
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus |
            Qt.WindowType.WindowTransparentForInput
        )
        
        # 透明背景和输入穿透
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        
        # 根据屏幕大小设置窗口尺寸限制
        self._setup_screen_based_limits()
        self.move(10, 10)  # 距离屏幕左上角10像素
        
        # 设置窗口标题（虽然不显示）
        self.setWindowTitle("OSC Debug Overlay")
        
    def _setup_screen_based_limits(self) -> None:
        """根据屏幕大小设置窗口尺寸限制"""
        # 获取主屏幕信息
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()  # 获取可用屏幕区域（排除任务栏等）
            screen_width = screen_geometry.width()
            
            # 最小宽度：200px或屏幕宽度的15%，取较小值  
            min_width = min(200, int(screen_width * 0.15))
            
        else:
            # 如果无法获取屏幕信息，使用默认值
            min_width = 200
            
        # 不设置Qt的最大尺寸限制，允许窗口根据内容需要扩展
        self.setMinimumWidth(min_width)
        
        
    def _setup_ui(self) -> None:
        """设置用户界面"""
        # 主布局（去除统一容器背景）
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(4)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # 创建高频更新定时器，用于渐变动画
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_timer.setInterval(50)  # 50ms更新一次，实现流畅渐变
        
    def update_debug_items(self, items_with_opacity: List[Tuple[str, float]], update_times: Optional[Dict[str, float]] = None) -> None:
        """更新调试信息显示
        
        Args:
            items_with_opacity: List of (text, opacity) tuples
            update_times: Dict mapping OSC address to last update time
        """
        # 更新内部的更新时间记录
        if update_times:
            self._item_update_times.update(update_times)
            
        # 保存当前显示状态
        self._current_items_with_opacity = items_with_opacity.copy()
            
        # 隐藏所有现有标签
        for label in self.label_pool:
            label.hide()
            
        # 确保有足够的标签
        while len(self.label_pool) < len(items_with_opacity):
            label = self._create_debug_label("")
            self.label_pool.append(label)
            self.content_layout.addWidget(label)
        
        # 更新标签文本、透明度并显示
        for i, (text, opacity) in enumerate(items_with_opacity):
            if i < len(self.label_pool):
                # 从文本中提取OSC地址（第一个空格或等号之前的部分）
                osc_address = text.split(' ')[0].split('=')[0]
                
                # 先重置最小宽度限制，让标签能够自然计算大小
                self.label_pool[i].setMinimumWidth(0)
                self.label_pool[i].setText(text)
                self.label_pool[i].adjustSize()
                current_width = self.label_pool[i].width()
                
                # 更新该OSC地址的历史最大宽度（只增不减）
                if osc_address not in self.address_max_widths:
                    self.address_max_widths[osc_address] = current_width
                elif current_width > self.address_max_widths[osc_address]:
                    self.address_max_widths[osc_address] = current_width
                
                # 设置该标签的最小宽度为这个OSC地址的历史最大宽度
                self.label_pool[i].setMinimumWidth(self.address_max_widths[osc_address])
                self.label_pool[i].setWindowOpacity(opacity)
                
                # 设置独立背景样式，根据透明度调整
                bg_alpha = int(160 * opacity)  # 背景透明度随文字透明度变化
                border_alpha = int(80 * opacity)  # 边框透明度随文字透明度变化
                text_alpha = int(255 * opacity)  # 文字透明度
                
                # 计算绿色到白色渐变（基于更新时间）
                current_time = time.time()
                time_since_update = current_time - getattr(self, '_item_update_times', {}).get(osc_address, current_time)
                
                # 1秒内从绿色渐变到白色
                if time_since_update < 1.0:
                    # 计算渐变进度 (0.0 = 完全绿色, 1.0 = 完全白色)
                    fade_progress = time_since_update
                    
                    # 绿色 (0, 255, 0) 到白色 (255, 255, 255) 的插值
                    red = int(255 * fade_progress)
                    green = 255  # 绿色分量保持不变
                    blue = int(255 * fade_progress)
                    
                    text_color = f"rgba({red}, {green}, {blue}, {text_alpha})"
                else:
                    # 超过1秒后显示白色
                    text_color = f"rgba(255, 255, 255, {text_alpha})"
                
                self.label_pool[i].setStyleSheet(f"""
                    QLabel {{
                        color: {text_color};
                        background-color: rgba(0, 0, 0, {bg_alpha});
                        padding: 6px 10px;
                        border: 1px solid rgba(255, 255, 255, {border_alpha});
                        border-radius: 6px;
                        margin: 2px;
                        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                        font-weight: bold;
                    }}
                """)
                
                self.label_pool[i].show()
        
        # 更新完内容后调整窗口大小
        self.adjust_window_size()
        
        # 启动动画定时器（如果有项目显示）
        if items_with_opacity:
            self.animation_timer.start()
        else:
            self.animation_timer.stop()
    
    def _update_animation(self) -> None:
        """更新渐变动画，只更新颜色而不重新布局"""
        current_time = time.time()
        
        # 检查是否还有需要渐变的项目
        has_active_gradients = False
        
        for i, (text, opacity) in enumerate(self._current_items_with_opacity):
            if i < len(self.label_pool):
                # 从文本中提取OSC地址
                osc_address = text.split(' ')[0].split('=')[0]
                
                # 计算渐变颜色
                time_since_update = current_time - self._item_update_times.get(osc_address, current_time)
                text_alpha = int(255 * opacity)
                
                # 1秒内从绿色渐变到白色
                if time_since_update < 1.0:
                    has_active_gradients = True
                    # 计算渐变进度 (0.0 = 完全绿色, 1.0 = 完全白色)
                    fade_progress = time_since_update
                    
                    # 绿色 (0, 255, 0) 到白色 (255, 255, 255) 的插值
                    red = int(255 * fade_progress)
                    green = 255  # 绿色分量保持不变
                    blue = int(255 * fade_progress)
                    
                    text_color = f"rgba({red}, {green}, {blue}, {text_alpha})"
                else:
                    # 超过1秒后显示白色
                    text_color = f"rgba(255, 255, 255, {text_alpha})"
                
                # 只更新颜色，不改变其他样式
                bg_alpha = int(160 * opacity)
                border_alpha = int(80 * opacity)
                
                self.label_pool[i].setStyleSheet(f"""
                    QLabel {{
                        color: {text_color};
                        background-color: rgba(0, 0, 0, {bg_alpha});
                        padding: 6px 10px;
                        border: 1px solid rgba(255, 255, 255, {border_alpha});
                        border-radius: 6px;
                        margin: 2px;
                        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                        font-weight: bold;
                    }}
                """)
        
        # 如果没有活跃的渐变，停止定时器
        if not has_active_gradients:
            self.animation_timer.stop()

    def reset_label_widths(self) -> None:
        """重置所有标签的宽度记录（在需要重新计算最优宽度时调用）"""
        self.address_max_widths.clear()
        for label in self.label_pool:
            label.setMinimumWidth(0)  # 重置最小宽度限制
            
    def adjust_window_size(self) -> None:
        """根据内容动态调整窗口大小"""
        # 让布局重新计算大小
        self.adjustSize()
        
        # 确保窗口大小合理
        size_hint = self.sizeHint()
        current_size = self.size()
        
        # 宽度：优先使用内容推荐大小，最小宽度保证，但允许超出最大宽度
        new_width = max(self.minimumWidth(), size_hint.width())
        
        # 高度：优先使用内容推荐大小，最小高度保证
        new_height = max(50, size_hint.height())
        
        if new_width != current_size.width() or new_height != current_size.height():
            self.resize(new_width, new_height)
            
    def _create_debug_label(self, text: str) -> QLabel:
        """创建调试信息标签"""
        label = QLabel(text)
        
        # 设置字体
        font = QFont("Consolas", 10, QFont.Weight.Bold)
        label.setFont(font)
        
        # 设置文字对齐
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        # 设置自适应大小策略
        label.setWordWrap(False)  # 不自动换行，保持单行显示
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        label.adjustSize()  # 自适应内容大小
        
        return label
        
    def show_overlay(self) -> None:
        """显示覆盖层"""
        self.show()
        self.raise_()
        # 不调用activateWindow()，避免影响全屏游戏的鼠标状态
        
    def hide_overlay(self) -> None:
        """隐藏覆盖层"""
        self.animation_timer.stop()
        self.hide()
        


class OSCDebugDisplayManager:
    """OSC调试显示管理器"""
    
    def __init__(self) -> None:
        super().__init__()
        self.debug_items: Dict[str, OSCDebugItem] = {}
        self.overlay_window: Optional[OSCDebugOverlay] = None
        self.cleanup_timer: Optional[QTimer] = None
        self.next_display_order = 0
        
        # 显示配置（从OSCService获取）
        self.display_duration = 5.0
        self.fadeout_duration = 1.0
        self.enabled = False
        
        # 新增：调试过滤器
        self.debug_filter: Optional[OSCDebugFilter] = None
        self.filtered_count: int = 0
        
    def set_enabled(self, enabled: bool) -> None:
        """设置调试显示开关"""
        self.enabled = enabled
        if not enabled:
            self.hide_display()
            
    def set_display_duration(self, duration: float) -> None:
        """设置显示时间"""
        self.display_duration = duration
        
    def set_fadeout_duration(self, duration: float) -> None:
        """设置淡出时间"""
        self.fadeout_duration = duration
    
    def set_debug_filter(self, debug_filter: Optional[OSCDebugFilter]) -> None:
        """设置调试过滤器"""
        self.debug_filter = debug_filter
        self.update_filter()
    
    def update_filter(self) -> None:
        """更新过滤器，重新计算显示内容"""
        if self.enabled:
            self._update_display()
    
    def get_filtered_count(self) -> int:
        """获取过滤后的项目数量"""
        return self.filtered_count
        
    def add_or_update_debug_item(self, address: str, values: List[OSCValue]) -> None:
        """添加或更新调试信息项"""
        if not self.enabled:
            return
        
        # 新增：应用过滤器
        if self.debug_filter and not self.debug_filter.matches(address):
            # 如果不匹配过滤条件，从显示列表中移除（如果存在）
            if address in self.debug_items:
                del self.debug_items[address]
                self._update_display()
            return
            
        # 格式化类型信息
        types_text = ", ".join([v.value_type().value for v in values])
        
        if address in self.debug_items:
            # 更新现有项（保持first_seen_time不变）
            item = self.debug_items[address]
            item.values = values
            item.types = types_text
            item.last_update_time = time.time()
        else:
            # 创建新项
            item = OSCDebugItem(address, values, types_text)
            item.display_order = self.next_display_order
            self.next_display_order += 1
            self.debug_items[address] = item
            
        self._update_display()
        self._schedule_cleanup()
        
    def _update_display(self) -> None:
        """更新显示内容"""
        if not self.enabled or not self.debug_items:
            self.hide_display()
            self.filtered_count = 0
            return
        
        # 应用过滤器
        filtered_items = {}
        if self.debug_filter:
            for address, item in self.debug_items.items():
                if self.debug_filter.matches(address):
                    filtered_items[address] = item
        else:
            filtered_items = self.debug_items
        
        self.filtered_count = len(filtered_items)
        
        if not filtered_items:
            self.hide_display()
            return
            
        # 创建覆盖窗口（如果不存在）
        if self.overlay_window is None:
            self.overlay_window = OSCDebugOverlay()
            
        # 按照第一次出现的顺序排序
        sorted_items = sorted(filtered_items.values(), key=lambda x: x.display_order)
        
        # 计算每个项目的文本和透明度
        current_time = time.time()
        items_with_opacity: List[Tuple[str, float]] = []
        update_times: Dict[str, float] = {}
        
        for item in sorted_items:
            # 格式化值
            values_text = ", ".join([str(v.value) for v in item.values])
            
            # 创建显示文本
            text = f"{item.address}"
            if values_text:
                text += f" = {values_text}"
            if item.types:
                text += f" ({item.types})"
            
            # 计算透明度 - 使用最近更新时间而不是首次出现时间
            time_since_last_update = current_time - item.last_update_time
            
            if time_since_last_update <= self.display_duration:
                # 显示阶段：完全不透明（项目仍在活跃更新）
                opacity = 1.0
            elif time_since_last_update <= (self.display_duration + self.fadeout_duration):
                # 淡出阶段：线性淡出（项目停止更新后开始淡出）
                fadeout_progress = (time_since_last_update - self.display_duration) / self.fadeout_duration
                opacity = 1.0 - fadeout_progress
            else:
                # 应该被清理的项目，跳过不显示
                continue
            
            # 只添加有效透明度的项目（>0.01避免浮点误差）
            if opacity > 0.01:
                items_with_opacity.append((text, opacity))
                update_times[item.address] = item.last_update_time
            
        # 更新覆盖窗口内容
        self.overlay_window.update_debug_items(items_with_opacity, update_times)
        
        # 显示窗口
        if not self.overlay_window.isVisible():
            self.overlay_window.show_overlay()
            
    def _schedule_cleanup(self) -> None:
        """安排清理过期项"""
        if self.cleanup_timer is None:
            self.cleanup_timer = QTimer()
            self.cleanup_timer.timeout.connect(self._cleanup_expired_items)
            
        # 每500毫秒检查一次过期项
        self.cleanup_timer.start(500)
        
    def _cleanup_expired_items(self) -> None:
        """清理过期的调试项"""
        if not self.enabled:
            if self.cleanup_timer:
                self.cleanup_timer.stop()
            return
            
        current_time = time.time()
        expired_addresses: List[str] = []
        
        # 找出需要清理的项目（最后更新后 显示时间 + 淡出时间）
        for address, item in self.debug_items.items():
            time_since_last_update = current_time - item.last_update_time
            if time_since_last_update > (self.display_duration + self.fadeout_duration):
                expired_addresses.append(address)
        
        # 移除过期项
        for address in expired_addresses:
            del self.debug_items[address]
            logger.debug(f"清理过期OSC调试项: {address}")
            
        # 更新显示（会自动计算透明度）
        if self.debug_items:
            self._update_display()
        else:
            # 没有项目时隐藏显示
            logger.debug("所有OSC调试项已清理，隐藏显示")
            self.hide_display()
            if self.cleanup_timer:
                self.cleanup_timer.stop()
                
            
    def hide_display(self) -> None:
        """隐藏调试显示"""
        if self.overlay_window and self.overlay_window.isVisible():
            self.overlay_window.hide_overlay()
            
        if self.cleanup_timer and self.cleanup_timer.isActive():
            self.cleanup_timer.stop()
            
    def clear_all_items(self) -> None:
        """清除所有调试项"""
        self.debug_items.clear()
        self.next_display_order = 0
        self.hide_display()
        
    def destroy(self) -> None:
        """销毁调试显示管理器"""
        if self.cleanup_timer:
            self.cleanup_timer.stop()
            self.cleanup_timer = None
            
        if self.overlay_window:
            self.overlay_window.close()
            self.overlay_window = None
            
        self.debug_items.clear()
        

# 全局调试显示管理器已移除，改为在AppController中管理