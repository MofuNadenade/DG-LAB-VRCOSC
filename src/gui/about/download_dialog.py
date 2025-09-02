"""
下载进度对话框 - 纯UI逻辑，通过AutoUpdater处理下载业务
"""

import asyncio
import logging
from typing import Optional

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QTextEdit, QWidget, QMessageBox

from i18n import translate
from core.auto_updater.auto_updater import AutoUpdater
from core.auto_updater.models import ReleaseInfo

logger = logging.getLogger(__name__)


class DownloadDialog(QDialog):
    """下载进度对话框 - 纯UI逻辑"""
    
    def __init__(self, release_info: ReleaseInfo, updater: AutoUpdater, allow_choose_path: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.release_info: ReleaseInfo = release_info
        self.updater: AutoUpdater = updater
        self.allow_choose_path: bool = allow_choose_path
        self.download_path: Optional[str] = None
        self.should_stop: bool = False
        
        # UI组件类型注解
        self.progress_bar: QProgressBar
        self.status_label: QLabel
        self.log_text: QTextEdit
        self.cancel_button: QPushButton
        self.install_button: QPushButton
        
        self.init_ui()
        self.setup_updater_connections()
        
        # 启动下载
        asyncio.create_task(self._start_download())
        
    def init_ui(self) -> None:
        """初始化UI"""
        self.setWindowTitle(translate('download_dialog.title'))
        self.setFixedSize(400, 250)
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # 版本信息
        version_label = QLabel(translate('download_dialog.downloading_version').format(self.release_info.version))
        version_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(version_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel(translate('download_dialog.preparing'))
        layout.addWidget(self.status_label)
        
        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(80)
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton(translate('download_dialog.cancel'))
        self.cancel_button.clicked.connect(self.cancel_download)
        button_layout.addWidget(self.cancel_button)
        
        self.install_button = QPushButton(translate('download_dialog.install'))
        self.install_button.clicked.connect(self.install_update)
        self.install_button.setEnabled(False)
        
        # 在自动安装模式下隐藏安装按钮，因为安装是自动进行的
        if not self.allow_choose_path:
            self.install_button.hide()
        
        button_layout.addWidget(self.install_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def setup_updater_connections(self) -> None:
        """连接AutoUpdater信号到UI处理方法"""
        # 连接AutoUpdater信号到UI处理方法
        self.updater.download_progress.connect(self._on_download_progress)
        self.updater.download_complete.connect(self._on_download_complete)
        self.updater.download_error.connect(self._on_download_error)
        self.updater.install_complete.connect(self._on_install_complete)
        self.updater.install_error.connect(self._on_install_error)

    async def _start_download(self) -> None:
        """启动下载"""
        self._update_status(translate('download_dialog.connecting'))
        
        try:
            if self.allow_choose_path:
                # 仅下载模式
                self.download_path = await self.updater.download_update(self.release_info, self)
            else:
                # 下载并安装模式
                self._update_status(translate('download_dialog.auto_installing'))
                success = await self.updater.download_and_install_update(self.release_info)
                if success:
                    self._on_install_complete()
                else:
                    self._on_install_error("安装失败")
                    
        except Exception as e:
            logger.error(f"下载启动失败: {e}")
            self._on_download_error(str(e))

    # AutoUpdater信号处理方法 - 纯UI逻辑
    def _on_download_progress(self, progress: int) -> None:
        """处理下载进度信号"""
        self.progress_bar.setValue(progress)
        self._update_status(translate('download_dialog.downloading'))

    def _on_download_complete(self, download_path: str) -> None:
        """处理下载完成信号"""
        self.download_path = download_path
        self._update_status(translate('download_dialog.download_complete'))
        self.cancel_button.setText(translate('download_dialog.close'))
        self.install_button.setEnabled(True)
        self._log_message(translate('download_dialog.download_success').format(download_path))

    def _on_download_error(self, error_message: str) -> None:
        """处理下载错误信号"""
        logger.error(f"下载失败: {error_message}")
        self._update_status(translate('download_dialog.download_failed'))
        self._log_message(translate('download_dialog.error_detail').format(error_message))
        self.cancel_button.setText(translate('download_dialog.close'))

    def _on_install_complete(self) -> None:
        """处理安装完成信号"""
        self._update_status(translate('download_dialog.install_complete'))
        self.cancel_button.setText(translate('download_dialog.close'))
        self.install_button.setEnabled(False)
        self._log_message(translate('download_dialog.install_success'))
        
        # 询问是否重启程序
        reply = QMessageBox.question(
            self,
            translate('download_dialog.restart_confirm_title'),
            translate('download_dialog.restart_confirm_message'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.updater.restart_application()
        else:
            self._log_message(translate('download_dialog.restart_cancelled'))

    def _on_install_error(self, error_message: str) -> None:
        """处理安装错误信号"""
        logger.error(f"安装失败: {error_message}")
        self._update_status(translate('download_dialog.install_failed'))
        self._log_message(translate('download_dialog.install_error_detail').format(error_message))
        self.cancel_button.setText(translate('download_dialog.close'))

    def _update_status(self, status: str) -> None:
        """更新状态 - UI逻辑"""
        self.status_label.setText(status)
        
    def _log_message(self, message: str) -> None:
        """记录日志消息 - UI逻辑"""
        self.log_text.append(message)
        
    def cancel_download(self) -> None:
        """取消下载 - UI逻辑"""
        self.should_stop = True
        self.updater.cancel_current_task()
        self.reject()
        
    def install_update(self) -> None:
        """安装更新 - UI逻辑"""
        if self.download_path:
            # 启动安装
            asyncio.create_task(self._install_update_async())
        else:
            self.accept()  # 返回成功状态
    
    async def _install_update_async(self) -> None:
        """异步安装更新"""
        if self.download_path:
            success = await self.updater.install_update(self.download_path)
            if success:
                self._on_install_complete()
            else:
                self._on_install_error("安装失败")
        
    def get_download_path(self) -> Optional[str]:
        """获取下载文件路径"""
        return self.download_path