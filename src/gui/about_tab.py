import logging
from typing import Dict

from PySide6.QtCore import QLocale, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit

from i18n import translate, language_signals
from models import SettingsDict
from .ui_interface import UIInterface

try:
    from version import get_version, get_build_info
except ImportError:
    # Fallback if version.py doesn't exist
    def get_version() -> str:
        return "v0.0.0-dev"


    def get_build_info() -> Dict[str, str]:
        return {"commit_short": "unknown", "build_time": "unknown"}

logger = logging.getLogger(__name__)


class AboutTab(QWidget):
    def __init__(self, ui_interface: UIInterface, settings: SettingsDict) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.settings: SettingsDict = settings

        # UI组件类型注解
        self.version_label: QLabel
        self.feedback_btn: QPushButton
        self.contributors_text: QTextEdit

        self.init_ui()

        # 连接语言变更信号
        language_signals.language_changed.connect(self.update_ui_texts)

    def init_ui(self) -> None:
        """初始化关于选项卡UI"""
        layout = QVBoxLayout()

        # 版本信息
        version_layout = QVBoxLayout()
        current_version = get_version()
        build_info = get_build_info()
        self.version_label = QLabel(translate("about_tab.current_version_label").format(current_version))

        # 添加构建信息
        if build_info.get('commit_short') != 'unknown':
            build_label = QLabel(
                f"Build: {build_info['commit_short']} ({build_info.get('build_time', 'unknown')[:10]})")
            build_label.setStyleSheet("color: gray; font-size: 10px;")
            version_layout.addWidget(build_label)

        version_layout.addWidget(self.version_label)

        # 按钮布局
        buttons_layout = QHBoxLayout()

        # 问题反馈按钮
        self.feedback_btn = QPushButton(translate('about_tab.feedback'))
        self.feedback_btn.clicked.connect(self.open_feedback)
        buttons_layout.addWidget(self.feedback_btn)

        version_layout.addLayout(buttons_layout)
        layout.addLayout(version_layout)

        # 贡献信息
        self.contributors_text = QTextEdit()
        # 强制使用英文区域设置，避免数字显示为繁体中文
        self.contributors_text.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.contributors_text.setReadOnly(True)
        # 直接拼接字符串，不使用数组
        self.contributors_text.setText(
            "开发组织: ccvrc\n" +
            "\n" +
            "贡献者:\n" +
            "- MofuNadenade（架构重构，波形编辑器，OSC地址绑定）\n" +
            "- icrazt\n" +
            "- 光水\n" +
            "- icelly_QAQ\n" +
            "\n" +
            "特别感谢:\n" +
            "- ChrisFeline (ToNSaveManager)\n" +
            "- VRChat OSC 社区\n" +
            "- VRSuya SoundPad\n" +
            "- WastingMisaka（鱼板）\n" +
            "- Wanlin\n" +
            "- 所有参与测试、使用本项目及贡献问题反馈的用户\n" +
            "\n" +
            "项目地址: https://github.com/ccvrc/DG-LAB-VRCOSC\n" +
            "\n" +
            "使用的开源项目:\n" +
            "- PySide6 (LGPL)\n" +
            "- websockets (BSD)\n" +
            "- qasync (MIT)\n" +
            "- pydglab-ws (BSD)\n" +
            "- qrcode (LGPL)\n" +
            "- python-osc (MIT)\n" +
            "- colorlog (MIT)\n" +
            "- pillow (HPND)\n" +
            "- ruamel.yaml (MIT)\n" +
            "- psutil (BSD)"
        )

        layout.addWidget(self.contributors_text)
        self.setLayout(layout)

    def open_feedback(self) -> None:
        """打开问题反馈页面"""
        url = QUrl("https://qiz80xlgzfj.feishu.cn/share/base/form/shrcn5tv1swXYDkg8HZ99BwOWfh")
        QDesktopServices.openUrl(url)
        logger.info("已打开问题反馈页面")

    def update_ui_texts(self) -> None:
        """更新UI上的所有文本为当前语言"""
        self.feedback_btn.setText(translate('about_tab.feedback'))
        current_version = get_version()
        self.version_label.setText(translate("about_tab.current_version_label").format(current_version))
