"""
关于选项卡 - 纯UI逻辑，升级功能通过AutoUpdater处理
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QLocale, QUrl, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QMessageBox

from i18n import translate, language_signals
from models import SettingsDict
from gui.ui_interface import UIInterface
from gui.about.download_dialog import DownloadDialog
from util import resource_path
from core.auto_updater.auto_updater import AutoUpdater
from core.auto_updater.models import ReleaseInfo

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
    """关于选项卡 - 纯UI逻辑"""
    
    def __init__(self, ui_interface: UIInterface) -> None:
        super().__init__()
        self.ui_interface: UIInterface = ui_interface
        self.settings: SettingsDict = ui_interface.settings

        # UI组件类型注解
        self.version_label: QLabel
        self.feedback_btn: QPushButton
        self.check_update_btn: QPushButton
        self.contributors_text: QTextEdit
        
        # AutoUpdater实例
        self.updater: Optional[AutoUpdater] = None
        
        # 标记是否为启动时自动检查
        self.is_startup_check: bool = False

        self.init_ui()
        self.setup_updater()

        # 连接语言变更信号
        language_signals.language_changed.connect(self.update_ui_texts)
        
        # 使用QTimer延迟执行启动检查，确保事件循环已启动
        QTimer.singleShot(1000, self.check_startup_update)
    
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
        
        # 检查更新按钮
        self.check_update_btn = QPushButton(translate('about_tab.check_updates'))
        self.check_update_btn.clicked.connect(self.check_for_updates)
        buttons_layout.addWidget(self.check_update_btn)

        version_layout.addLayout(buttons_layout)
        layout.addLayout(version_layout)

        # 贡献信息
        self.contributors_text = QTextEdit()
        # 强制使用英文区域设置，避免数字显示为繁体中文
        self.contributors_text.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        self.contributors_text.setReadOnly(True)
        
        # 从文件中读取贡献者信息
        try:
            contributors_file = resource_path("resources/contributors.txt")
            with open(contributors_file, 'r', encoding='utf-8') as f:
                contributors_content = f.read()
            self.contributors_text.setText(contributors_content)
        except Exception as e:
            logger.warning(f"无法读取贡献者信息文件: {e}")
            self.contributors_text.setText("贡献者信息加载失败！")

        layout.addWidget(self.contributors_text)
        self.setLayout(layout)

    def setup_updater(self) -> None:
        """设置AutoUpdater并连接信号"""
        auto_updater_settings = self.settings.get('auto_updater', {})
        enabled = auto_updater_settings.get('enabled', False)
        github_repo = auto_updater_settings.get('github_repo', '')
        
        if enabled and github_repo:
            self.updater = AutoUpdater(github_repo, get_version(), self.settings)
            
            # 连接AutoUpdater信号到UI处理方法
            self.updater.update_available.connect(self._on_update_available)
            self.updater.no_update_available.connect(self._on_no_update_available)
            self.updater.check_error.connect(self._on_check_error)
            self.updater.download_complete.connect(self._on_download_complete)
            self.updater.download_error.connect(self._on_download_error)
            self.updater.install_complete.connect(self._on_install_complete)
            self.updater.install_error.connect(self._on_install_error)
            
            logger.info("AutoUpdater已初始化")
        elif not enabled:
            logger.info("自动更新功能已禁用，AutoUpdater未初始化")
        elif not github_repo:
            logger.warning("GitHub仓库未配置，AutoUpdater未初始化")

    def check_startup_update(self) -> None:
        """启动时自动检查更新"""
        auto_updater_settings = self.settings.get('auto_updater', {})
        enabled = auto_updater_settings.get('enabled', False)
        check_on_startup = auto_updater_settings.get('check_on_startup', False)
        
        if enabled and check_on_startup and self.updater:
            logger.info("启动时自动检查更新")
            asyncio.create_task(self._delayed_startup_check())
        elif not enabled:
            logger.info("自动更新功能已禁用，跳过启动检查")
        elif not check_on_startup:
            logger.info("启动时检查更新已禁用")

    async def _delayed_startup_check(self) -> None:
        """延迟启动检查更新"""
        if self.updater:
            self.is_startup_check = True
            await self.updater.check_for_updates()
            self.is_startup_check = False

    def open_feedback(self) -> None:
        """打开问题反馈页面"""
        url = QUrl("https://qm.qq.com/q/1Mc6R9IvTq")
        QDesktopServices.openUrl(url)
        logger.info("已打开问题反馈页面")

    def check_for_updates(self) -> None:
        """检查更新 - UI逻辑"""
        auto_updater_settings = self.settings.get('auto_updater', {})
        enabled = auto_updater_settings.get('enabled', False)
        
        if not enabled:
            QMessageBox.information(
                self,
                translate('about_tab.update_check_title'),
                translate('about_tab.auto_update_disabled')
            )
            return
            
        if not self.updater:
            QMessageBox.warning(
                self, 
                translate('about_tab.update_check_title'),
                translate('about_tab.no_repo_configured')
            )
            return
            
        # 禁用按钮防止重复点击
        self.check_update_btn.setEnabled(False)
        self.check_update_btn.setText(translate('about_tab.checking_updates'))
        
        # 使用AutoUpdater检查更新
        asyncio.create_task(self._check_updates_async())
        
    async def _check_updates_async(self) -> None:
        """异步检查更新"""
        if self.updater:
            await self.updater.check_for_updates()

    # AutoUpdater信号处理方法 - 纯UI逻辑
    def _on_update_available(self, release_info: ReleaseInfo) -> None:
        """处理发现新版本信号"""
        # 如果不是启动时自动检查，恢复按钮状态
        if not self.is_startup_check:
            self.check_update_btn.setEnabled(True)
            self.check_update_btn.setText(translate('about_tab.check_updates'))
        
        # 显示更新可用对话框
        reply = QMessageBox.question(
            self,
            translate('about_tab.update_available_title'),
            translate('about_tab.update_available_message').format(
                release_info.version, release_info.name
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._handle_update_download(release_info)

    def _on_no_update_available(self) -> None:
        """处理无更新信号"""
        # 如果不是启动时自动检查，恢复按钮状态并显示信息
        if not self.is_startup_check:
            self.check_update_btn.setEnabled(True)
            self.check_update_btn.setText(translate('about_tab.check_updates'))
            
            # 显示无更新信息
            QMessageBox.information(
                self,
                translate('about_tab.no_update_title'),
                translate('about_tab.no_update_message')
            )
        else:
            # 启动时自动检查，只记录日志
            logger.info("启动时检查更新：当前已是最新版本")

    def _on_check_error(self, error_message: str) -> None:
        """处理检查错误信号"""
        # 如果不是启动时自动检查，恢复按钮状态并显示错误信息
        if not self.is_startup_check:
            self.check_update_btn.setEnabled(True)
            self.check_update_btn.setText(translate('about_tab.check_updates'))
            
            # 显示错误信息
            QMessageBox.critical(
                self,
                translate('about_tab.check_error_title'),
                translate('about_tab.check_error_message').format(error_message)
            )
        else:
            # 启动时自动检查，只记录错误日志
            logger.error(f"启动时检查更新失败: {error_message}")

    def _on_download_complete(self, download_path: str) -> None:
        """处理下载完成信号"""
        logger.info(f"下载完成: {download_path}")
        
        # 根据下载策略显示不同的完成信息
        strategy = self.updater.get_download_strategy() if self.updater else "unknown"
        
        if strategy == "download_only":
            # 仅下载模式：询问是否打开文件位置
            download_dir = str(Path(download_path).parent)
            reply = QMessageBox.question(
                self,
                translate('about_tab.open_file_location_title'),
                translate('about_tab.open_file_location_message').format(download_path),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl.fromLocalFile(download_dir))
                logger.info(f"已打开文件位置: {download_dir}")
            
            QMessageBox.information(
                self,
                translate('about_tab.download_complete_title'),
                translate('about_tab.download_saved_message').format(download_path)
            )

    def _on_download_error(self, error_message: str) -> None:
        """处理下载错误信号"""
        QMessageBox.critical(
            self,
            translate('about_tab.download_error_title'),
            translate('about_tab.download_error_detail').format(error_message)
        )

    def _on_install_complete(self) -> None:
        """处理安装完成信号"""
        # 询问是否重启
        reply = QMessageBox.question(
            self,
            translate('about_tab.install_success_title'),
            translate('about_tab.install_success_message'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes and self.updater:
            self.updater.restart_application()

    def _on_install_error(self, error_message: str) -> None:
        """处理安装错误信号"""
        QMessageBox.critical(
            self,
            translate('about_tab.install_error_title'),
            translate('about_tab.install_error_detail').format(error_message)
        )

    def _handle_update_download(self, release_info: ReleaseInfo) -> None:
        """处理更新下载 - 根据策略决定下载方式"""
        if not self.updater:
            return
            
        strategy = self.updater.get_download_strategy()
        
        if strategy == "manual":
            self._handle_manual_download(release_info)
        elif strategy == "download_only":
            self._handle_download_only(release_info)
        else:
            self._handle_download_and_install(release_info)

    def _handle_manual_download(self, release_info: ReleaseInfo) -> None:
        """处理手动下载"""
        reply = QMessageBox.question(
            self,
            translate('about_tab.manual_download_title'),
            translate('about_tab.manual_download_message').format(release_info.version),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes and release_info.download_url:
            url = QUrl(release_info.download_url)
            QDesktopServices.openUrl(url)
            logger.info(f"已打开手动下载页面: {release_info.download_url}")

    def _handle_download_only(self, release_info: ReleaseInfo) -> None:
        """处理仅下载模式"""
        if not self.updater:
            return
        
        dialog = DownloadDialog(release_info, self.updater, allow_choose_path=True, parent=self)
        dialog.show()

    def _handle_download_and_install(self, release_info: ReleaseInfo) -> None:
        """处理下载并安装模式"""
        # 确认安装
        reply = QMessageBox.question(
            self,
            translate('about_tab.auto_install_title'),
            translate('about_tab.auto_install_message').format(release_info.version),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes and self.updater:
            # 显示下载进度框进行自动下载和安装
            dialog = DownloadDialog(release_info, self.updater, allow_choose_path=False, parent=self)
            dialog.show()

    def update_ui_texts(self) -> None:
        """更新UI上的所有文本为当前语言"""
        self.feedback_btn.setText(translate('about_tab.feedback'))
        self.check_update_btn.setText(translate('about_tab.check_updates'))
        current_version = get_version()
        self.version_label.setText(translate("about_tab.current_version_label").format(current_version))