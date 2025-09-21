"""
欢迎对话框 - 首次启动功能介绍
显示应用主要功能介绍，帮助新用户了解软件使用方法
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTextBrowser, QCheckBox, QLabel, QWidget)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont, QDesktopServices
import os
from typing import Optional

from util import resource_path
from i18n import translate
from gui.styles import CommonColors


class WelcomeDialog(QDialog):
    """欢迎介绍对话框"""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(translate("welcome_dialog.title"))
        self.setModal(True)
        self.setMinimumSize(800, 600)
        self.resize(900, 700)
        
        # UI组件类型注解
        self.content_browser: QTextBrowser
        self.dont_show_again_checkbox: QCheckBox
        self.help_button: QPushButton
        self.start_button: QPushButton
        
        # 设置窗口标志
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowTitleHint
        )
        
        self._setup_ui()
        self._load_content()
        
    def _setup_ui(self) -> None:
        """设置用户界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题区域
        self._create_header(layout)
        
        # 内容区域 
        self._create_content_area(layout)
        
        # 底部按钮区域
        self._create_bottom_area(layout)
        
    def _create_header(self, layout: QVBoxLayout) -> None:
        """创建标题区域"""
        # 主标题
        title_label = QLabel(translate("welcome_dialog.welcome_title"))
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #2c3e50; margin: 10px 0;")
        layout.addWidget(title_label)
        
        # 副标题
        subtitle_label = QLabel(translate("welcome_dialog.welcome_subtitle"))
        subtitle_font = QFont()
        subtitle_font.setPointSize(11)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: #7f8c8d; margin-bottom: 20px;")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
        
    def _create_content_area(self, layout: QVBoxLayout) -> None:
        """创建内容区域"""
        # 创建文本浏览器显示Markdown内容
        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(False)  # 禁用外部链接
        
        layout.addWidget(self.content_browser)
        
    def _create_bottom_area(self, layout: QVBoxLayout) -> None:
        """创建底部区域"""
        # 复选框：不再显示此对话框
        self.dont_show_again_checkbox = QCheckBox(translate("welcome_dialog.dont_show_again"))
        self.dont_show_again_checkbox.setStyleSheet("margin: 10px 0;")
        layout.addWidget(self.dont_show_again_checkbox)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        # 左侧：帮助按钮
        self.help_button = QPushButton(translate("welcome_dialog.more_help"))
        self.help_button.setMinimumHeight(36)
        self.help_button.setStyleSheet(CommonColors.get_secondary_button_style())
        self.help_button.clicked.connect(self._show_help)
        button_layout.addWidget(self.help_button)
        
        # 弹簧
        button_layout.addStretch()
        
        # 右侧：开始使用按钮
        self.start_button = QPushButton(translate("welcome_dialog.start_using"))
        self.start_button.setMinimumHeight(36)
        self.start_button.setMinimumWidth(120)
        self.start_button.setDefault(True)
        self.start_button.setStyleSheet(CommonColors.get_primary_button_style())
        self.start_button.clicked.connect(self.accept)
        button_layout.addWidget(self.start_button)
        
        layout.addLayout(button_layout)
        
    def _load_content(self) -> None:
        """加载Markdown内容"""
        try:
            # 读取Markdown文件
            markdown_file = resource_path("resources/feature_introduction.md")
            if os.path.exists(markdown_file):
                with open(markdown_file, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
                
                # 直接使用PySide6内置Markdown支持
                self.content_browser.setMarkdown(markdown_content)
                
                # 添加一些基础样式
                self.content_browser.setStyleSheet("""
                    QTextBrowser {
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        padding: 16px;
                        background-color: white;
                        font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
                        font-size: 11pt;
                        line-height: 1.5;
                    }
                """)
            else:
                # 如果文件不存在，显示默认内容
                self._show_fallback_content()
                
        except Exception as e:
            print(f"加载欢迎内容失败: {e}")
            self._show_fallback_content()
            
    def _show_fallback_content(self) -> None:
        """显示备用内容（如果Markdown文件不可用）"""
        fallback_html = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6;">
            <h2 style="color: #2c3e50;">🎉 {translate("welcome_dialog.welcome_title")}</h2>
            
            <p>{translate("welcome_dialog.feature_overview")}:</p>
            
            <h3 style="color: #3498db;">🔗 {translate("welcome_dialog.main_features")}</h3>
            <ul>
                <li><strong>{translate("welcome_dialog.device_connection")}</strong> - {translate("welcome_dialog.device_connection_desc")}</li>
                <li><strong>{translate("welcome_dialog.pulse_system")}</strong> - {translate("welcome_dialog.pulse_system_desc")}</li>
                <li><strong>{translate("welcome_dialog.osc_integration")}</strong> - {translate("welcome_dialog.osc_integration_desc")}</li>
                <li><strong>{translate("welcome_dialog.debug_display")}</strong> - {translate("welcome_dialog.debug_display_desc")}</li>
            </ul>
            
            <h3 style="color: #27ae60;">🚀 {translate("welcome_dialog.quick_start")}</h3>
            <ol>
                <li>{translate("welcome_dialog.step1")}</li>
                <li>{translate("welcome_dialog.step2")}</li>
                <li>{translate("welcome_dialog.step3")}</li>
                <li>{translate("welcome_dialog.step4")}</li>
            </ol>
            
            <p style="background-color: #e8f5e8; padding: 12px; border-radius: 6px; border-left: 4px solid #27ae60;">
                💡 <strong>{translate("welcome_dialog.tip")}</strong>: {translate("welcome_dialog.tip_content")}
            </p>
        </div>
        """
        self.content_browser.setHtml(fallback_html)
        
    def _show_help(self) -> None:
        """显示更多帮助信息"""
        # 打开QQ群获取帮助
        QDesktopServices.openUrl(QUrl("https://qm.qq.com/q/1Mc6R9IvTq"))
        
    def is_dont_show_again_checked(self) -> bool:
        """检查是否勾选了"不再显示"选项"""
        return self.dont_show_again_checkbox.isChecked()
        
    def retranslate_ui(self) -> None:
        """重新翻译界面"""
        self.setWindowTitle(translate("welcome_dialog.title"))
        self.dont_show_again_checkbox.setText(translate("welcome_dialog.dont_show_again"))
        self.help_button.setText(translate("welcome_dialog.more_help"))
        self.start_button.setText(translate("welcome_dialog.start_using"))
        self._load_content()  # 重新加载内容以应用新的语言