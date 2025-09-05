"""
Deepseek选项卡 - 集成Deepseek网页
"""

import logging

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel

from i18n import translate, language_signals
from gui.ui_interface import UIInterface

logger = logging.getLogger(__name__)


class DeepseekTab(QWidget):
    """Deepseek选项卡 - 显示Deepseek网页"""
    
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface

        # UI组件类型注解
        self.url_input: QLineEdit
        self.go_button: QPushButton
        self.home_button: QPushButton
        self.refresh_button: QPushButton
        self.web_view: QWebEngineView
        
        # 默认URL
        self.default_url = "https://chat.deepseek.com/"

        self.init_ui()

        # 连接语言变更信号
        language_signals.language_changed.connect(self.update_ui_texts)
    
    def init_ui(self) -> None:
        """初始化Deepseek选项卡UI"""
        layout = QVBoxLayout()

        # 导航栏
        nav_layout = QHBoxLayout()
        
        # URL输入框
        url_label = QLabel(translate("deepseek_tab.url_label"))
        nav_layout.addWidget(url_label)
        
        self.url_input = QLineEdit()
        self.url_input.setText(self.default_url)
        self.url_input.returnPressed.connect(self.navigate_to_url)
        nav_layout.addWidget(self.url_input)
        
        # 导航按钮
        self.go_button = QPushButton(translate("deepseek_tab.go"))
        self.go_button.clicked.connect(self.navigate_to_url)
        nav_layout.addWidget(self.go_button)
        
        self.home_button = QPushButton(translate("deepseek_tab.home"))
        self.home_button.clicked.connect(self.go_home)
        nav_layout.addWidget(self.home_button)
        
        self.refresh_button = QPushButton(translate("deepseek_tab.refresh"))
        self.refresh_button.clicked.connect(self.refresh_page)
        nav_layout.addWidget(self.refresh_button)
        
        layout.addLayout(nav_layout)

        # 网页视图
        try:
            self.web_view = QWebEngineView()
            self.web_view.urlChanged.connect(self.on_url_changed)
            self.web_view.setUrl(QUrl(self.default_url))
            layout.addWidget(self.web_view)
            
            logger.info("Deepseek网页视图初始化成功")
        except Exception as e:
            logger.error(f"初始化网页视图失败: {e}")
            error_label = QLabel(f"网页视图初始化失败: {str(e)}")
            layout.addWidget(error_label)

        self.setLayout(layout)

    def navigate_to_url(self) -> None:
        """导航到输入的URL"""
        url_text = self.url_input.text().strip()
        if not url_text:
            return
            
        # 确保URL有协议前缀
        if not url_text.startswith(('http://', 'https://')):
            url_text = 'https://' + url_text
            
        try:
            url = QUrl(url_text)
            if url.isValid():
                self.web_view.setUrl(url)
                logger.info(f"导航到URL: {url_text}")
            else:
                logger.warning(f"无效的URL: {url_text}")
        except Exception as e:
            logger.error(f"导航失败: {e}")

    def go_home(self) -> None:
        """返回主页"""
        self.url_input.setText(self.default_url)
        self.web_view.setUrl(QUrl(self.default_url))
        logger.info("返回Deepseek主页")

    def refresh_page(self) -> None:
        """刷新页面"""
        self.web_view.reload()
        logger.info("刷新页面")

    def on_url_changed(self, url: QUrl) -> None:
        """URL变更时更新输入框"""
        self.url_input.setText(url.toString())

    def update_ui_texts(self) -> None:
        """更新UI上的所有文本为当前语言"""
        self.go_button.setText(translate("deepseek_tab.go"))
        self.home_button.setText(translate("deepseek_tab.home"))
        self.refresh_button.setText(translate("deepseek_tab.refresh"))