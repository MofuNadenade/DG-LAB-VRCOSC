"""
Auto-updater for DG-LAB-VRCOSC - 整合所有升级逻辑
"""

import asyncio
import logging
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Callable, List, Set, TypedDict, Any
from urllib.parse import urlparse

import aiohttp
from packaging import version
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog, QWidget

from .models import ReleaseInfo
from models import SettingsDict

logger = logging.getLogger(__name__)


# GitHub API 响应类型定义
class GitHubAssetDict(TypedDict):
    """GitHub Release Asset 类型"""
    name: str
    browser_download_url: str
    size: int
    download_count: int


class GitHubReleaseDict(TypedDict):
    """GitHub Release 响应类型"""
    tag_name: str
    name: str
    body: str
    published_at: str
    prerelease: bool
    assets: List[GitHubAssetDict]


class AutoUpdater(QObject):
    """GitHub Release-based auto updater - 整合所有升级逻辑"""
    
    # 信号定义
    update_available = Signal(ReleaseInfo)
    no_update_available = Signal()
    check_error = Signal(str)
    download_progress = Signal(int)
    download_complete = Signal(str)
    download_error = Signal(str)
    install_complete = Signal()
    install_error = Signal(str)
    restart_required = Signal()  # 需要重启的信号
    
    def __init__(self, repo: str, current_version: str, settings: SettingsDict) -> None:
        super().__init__()
        self.repo: str = repo
        self.current_version: str = current_version.lstrip('v')
        self.settings: SettingsDict = settings
        self.timeout: int = 30
        self._callbacks: Set[Callable[[str, str], None]] = set()
        
        # 当前任务
        self.current_task: Optional[asyncio.Task[bool]] = None
        
    def register_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register a callback for auto-updater events"""
        self._callbacks.add(callback)
        
    def unregister_callback(self, callback: Callable[[str, str], None]) -> None:
        """Unregister a callback"""
        self._callbacks.discard(callback)
        
    def _notify_callbacks(self, event: str, data: str = "") -> None:
        """Notify all registered callbacks"""
        for callback in self._callbacks:
            try:
                callback(event, data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _is_development_environment(self) -> bool:
        """检测是否为开发环境"""
        # 检查是否直接运行Python脚本
        if sys.argv[0].endswith('.py'):
            return True
        
        # 检查是否在虚拟环境中
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            return True
        
        # 检查可执行文件路径是否包含开发相关目录
        exe_path = Path(sys.executable).resolve()
        dev_indicators = ['python', 'Scripts', 'venv', 'env', 'conda']
        
        for indicator in dev_indicators:
            if indicator in str(exe_path).lower():
                return True
        
        return False
    
    def _is_windows(self) -> bool:
        """检测是否为Windows系统"""
        return platform.system().lower() == 'windows'
    
    def _get_resource_path(self, relative_path: str) -> Optional[Path]:
        """获取打包后的资源文件路径"""
        try:
            # PyInstaller打包后的资源路径
            if hasattr(sys, '_MEIPASS'):
                # 打包后的临时目录
                meipass: Any = getattr(sys, '_MEIPASS')
                base_path = Path(meipass)
            else:
                # 开发环境
                base_path = Path(__file__).parent.parent.parent
            
            resource_path = base_path / relative_path
            if resource_path.exists():
                return resource_path
            else:
                logger.warning(f"资源文件不存在: {resource_path}")
                return None
        except Exception as e:
            logger.error(f"获取资源路径失败: {e}")
            return None
    
    def _extract_install_helper(self) -> Optional[Path]:
        """解压安装助手脚本到临时目录"""
        try:
            # 获取打包的bat文件
            resource_path = self._get_resource_path("resources/install_helper.bat")
            if not resource_path:
                logger.error("无法找到安装助手脚本资源")
                return None
            
            # 创建临时目录
            temp_dir = Path(tempfile.gettempdir()) / "DG-LAB-VRCOSC-Install"
            temp_dir.mkdir(exist_ok=True)
            
            # 解压到临时目录
            temp_bat_path = temp_dir / "install_helper.bat"
            shutil.copy2(resource_path, temp_bat_path)
            
            logger.info(f"安装助手脚本已解压到: {temp_bat_path}")
            return temp_bat_path
            
        except Exception as e:
            logger.error(f"解压安装助手脚本失败: {e}")
            return None
    
    def _validate_paths(self, *paths: Path) -> bool:
        """验证路径安全性"""
        try:
            for path in paths:
                # 检查路径是否在允许的范围内
                resolved_path = path.resolve()
                
                # 检查是否包含危险字符
                path_str = str(resolved_path)
                dangerous_chars = ['..', '~', '$', '`', '|', '&', ';', '(', ')']
                for char in dangerous_chars:
                    if char in path_str:
                        logger.warning(f"路径包含危险字符: {char} in {path_str}")
                        return False
                
                # 检查路径长度
                if len(path_str) > 260:  # Windows路径长度限制
                    logger.warning(f"路径过长: {len(path_str)} > 260")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"路径验证失败: {e}")
            return False
    
    def get_download_strategy(self) -> str:
        """获取下载策略"""
        auto_updater_settings = self.settings.get('auto_updater', {})
        auto_download = auto_updater_settings.get('auto_download', True)
        auto_install = auto_updater_settings.get('auto_install', True)
        
        # 检查是否为开发环境，如果是则强制禁用自动安装
        is_dev_env = self._is_development_environment()
        if is_dev_env and auto_install:
            auto_install = False
        
        if not auto_download:
            return "manual"
        elif auto_download and not auto_install:
            return "download_only"
        else:
            return "download_and_install"
        
    async def check_for_updates(self) -> Optional[ReleaseInfo]:
        """Check for new releases on GitHub"""
        try:
            # 创建异步任务获取最新发布信息
            fetch_task = asyncio.create_task(self._fetch_latest_release_async())
            release_info = await fetch_task
            
            if release_info and self._is_newer_version(release_info.version):
                logger.info(f"New version available: {release_info.version}")
                self._notify_callbacks("update_available", release_info.version)
                self.update_available.emit(release_info)
                return release_info
            else:
                logger.info("No updates available")
                self._notify_callbacks("no_update_available", "")
                self.no_update_available.emit()
                return None
                
        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            self._notify_callbacks("check_error", str(e))
            self.check_error.emit(str(e))
            return None
    
    async def _fetch_latest_release_async(self) -> Optional[ReleaseInfo]:
        """异步获取最新发布信息"""
        api_url: str = f"https://api.github.com/repos/{self.repo}/releases/latest"
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(api_url) as response:
                    response.raise_for_status()
                    data: GitHubReleaseDict = await response.json()
                    
                    # Find Windows exe asset
                    download_url: Optional[str] = None
                    assets: List[GitHubAssetDict] = data.get('assets', [])
                    for asset in assets:
                        asset_name = asset.get('name', '')
                        if asset_name.endswith('.exe'):
                            download_url = asset.get('browser_download_url')
                            break
                    
                    return ReleaseInfo(
                        tag_name=data['tag_name'],
                        name=data['name'],
                        body=data['body'],
                        download_url=download_url,
                        published_at=data['published_at'],
                        prerelease=data['prerelease']
                    )
                    
        except aiohttp.ClientError as e:
            logger.error(f"GitHub API request failed: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse GitHub API response: {e}")
            return None
    
    def _is_newer_version(self, new_version: str) -> bool:
        """Compare versions using packaging.version"""
        try:
            return version.parse(new_version) > version.parse(self.current_version)
        except Exception as e:
            logger.warning(f"Version comparison failed: {e}, falling back to string comparison")
            return new_version != self.current_version
    
    async def download_update(self, release_info: ReleaseInfo, parent_widget: Optional[QWidget] = None) -> Optional[str]:
        """下载更新 - 根据策略选择下载方式"""
        if not release_info.download_url:
            self.download_error.emit("没有可用的下载链接")
            return None
        
        strategy = self.get_download_strategy()
        
        if strategy == "manual":
            return await self._manual_download(release_info, parent_widget)
        elif strategy == "download_only":
            return await self._download_only(release_info, parent_widget)
        else:
            return await self._download_for_install(release_info)
    
    async def _manual_download(self, release_info: ReleaseInfo, parent_widget: Optional[QWidget] = None) -> Optional[str]:
        """手动下载 - 打开浏览器"""
        # 这个方法实际上不下载文件，只是返回下载URL
        # UI层会处理打开浏览器
        return release_info.download_url
    
    async def _download_only(self, release_info: ReleaseInfo, parent_widget: Optional[QWidget] = None) -> Optional[str]:
        """仅下载 - 让用户选择保存位置"""
        if not parent_widget:
            self.download_error.emit("需要父窗口来选择保存位置")
            return None
        
        # 获取文件名
        filename = Path(str(urlparse(release_info.download_url).path)).name
        if not filename:
            filename = "DG-LAB-VRCOSC-Update.exe"
        
        # 让用户选择保存位置
        chosen_path, _ = QFileDialog.getSaveFileName(
            parent_widget,
            "选择保存位置",
            str(Path.home() / "Downloads" / filename),
            "Executable Files (*.exe);;All Files (*.*)"
        )
        
        if not chosen_path:
            return None
        
        # 下载到指定位置
        if release_info.download_url:
            return await self._download_to_path(release_info.download_url, Path(str(chosen_path)))
        return None
    
    async def _download_for_install(self, release_info: ReleaseInfo) -> Optional[str]:
        """为安装而下载 - 下载到临时目录"""
        # 获取文件名
        filename = Path(str(urlparse(release_info.download_url).path)).name
        if not filename:
            filename = "DG-LAB-VRCOSC-Update.exe"
        
        # 下载到临时目录，使用随机后缀避免冲突
        temp_dir = Path(tempfile.gettempdir()) / "DG-LAB-VRCOSC-Update"
        temp_dir.mkdir(exist_ok=True)
        
        # 添加随机后缀到文件名
        base_name = Path(filename).stem
        extension = Path(filename).suffix
        random_suffix = str(uuid.uuid4())[:8]  # 使用前8位UUID
        filename_with_suffix = f"{base_name}_{random_suffix}{extension}"
        
        update_path = temp_dir / filename_with_suffix
        logger.info(f"下载到临时目录: {update_path}")
        
        if release_info.download_url:
            return await self._download_to_path(release_info.download_url, update_path)
        return None
    
    async def _download_to_path(self, download_url: str, target_path: Path) -> Optional[str]:
        """下载文件到指定路径"""
        try:
            logger.info(f"开始下载: {download_url}")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(download_url) as response:
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    with open(target_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                if total_size > 0:
                                    progress = int((downloaded / total_size) * 100)
                                    self.download_progress.emit(progress)
                                
                                # 让出控制权给事件循环
                                await asyncio.sleep(0)
            
            logger.info(f"下载完成: {target_path}")
            self.download_complete.emit(str(target_path))
            return str(target_path)
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            self.download_error.emit(str(e))
            return None
    
    async def install_update(self, update_path: str) -> bool:
        """安装更新"""
        try:
            # 检测开发环境，如果是在开发环境中则拒绝安装
            if self._is_development_environment():
                error_msg = "检测到开发环境，无法安装更新以避免覆盖Python解释器"
                logger.warning(error_msg)
                self.install_error.emit(error_msg)
                return False
            
            if self.current_task and not self.current_task.done():
                self.current_task.cancel()
            
            # 创建假的ReleaseInfo用于安装
            fake_release = ReleaseInfo(
                tag_name="",
                name="",
                body="",
                download_url=update_path,
                published_at="",
                prerelease=False
            )
            
            self.current_task = asyncio.create_task(
                self._download_and_install_update_internal(fake_release)
            )
            return await self.current_task
            
        except Exception as e:
            logger.error(f"安装更新失败: {e}")
            self.install_error.emit(str(e))
            return False
    
    async def download_and_install_update(self, release_info: ReleaseInfo, 
                                        progress_callback: Optional[Callable[[int], None]] = None) -> bool:
        """Download and install update"""
        if not release_info.download_url:
            logger.error("No download URL available")
            return False
        
        # 检测开发环境，如果是在开发环境中则拒绝安装
        if self._is_development_environment():
            error_msg = "检测到开发环境，无法安装更新以避免覆盖Python解释器"
            logger.warning(error_msg)
            self.install_error.emit(error_msg)
            return False
            
        try:
            # 先下载
            download_path = await self._download_for_install(release_info)
            if not download_path:
                return False
            
            # 再安装
            return await self.install_update(download_path)
            
        except Exception as e:
            logger.error(f"Failed to download and install update: {e}")
            self._notify_callbacks("download_error", str(e))
            self.download_error.emit(str(e))
            return False
    
    async def _download_and_install_update_internal(self, release_info: ReleaseInfo) -> bool:
        """内部下载和安装方法"""
        if not release_info.download_url:
            logger.error("No download URL available")
            return False
            
        try:
            # 创建异步安装任务
            install_task = asyncio.create_task(self._install_update_async(release_info.download_url))
            result: bool = await install_task
            return result
            
        except Exception as e:
            logger.error(f"Failed to download and install update: {e}")
            self._notify_callbacks("download_error", str(e))
            self.download_error.emit(str(e))
            return False
    
    async def _install_update_async(self, update_path: str) -> bool:
        """异步安装下载的更新"""
        # 检测开发环境，如果是在开发环境中则拒绝安装
        if self._is_development_environment():
            error_msg = "检测到开发环境，无法安装更新以避免覆盖Python解释器"
            logger.warning(error_msg)
            self.install_error.emit(error_msg)
            return False
        
        current_exe: Path = Path(sys.executable)
        backup_path: Path = current_exe.with_suffix('.bak')
        new_exe_path: Path = Path(update_path)
        
        try:
            # 创建异步任务进行文件操作
            install_task = asyncio.create_task(self._perform_install_async(current_exe, backup_path, new_exe_path))
            result = await install_task
            
            if result:
                logger.info("Update installed successfully")
                self._notify_callbacks("update_installed", "")
                self.install_complete.emit()
            else:
                logger.error("Installation failed")
                self._notify_callbacks("install_error", "Installation failed")
                self.install_error.emit("Installation failed")
                
            return result
            
        except Exception as e:
            logger.error(f"Installation failed: {e}")
            self._notify_callbacks("install_error", str(e))
            self.install_error.emit(str(e))
            
            # 尝试恢复备份
            try:
                if backup_path.exists():
                    shutil.move(str(backup_path), str(current_exe))
                    logger.info("Restored backup after failed installation")
                    self._notify_callbacks("backup_restored", "")
            except Exception as restore_error:
                logger.error(f"Failed to restore backup: {restore_error}")
                self._notify_callbacks("restore_error", str(restore_error))
                    
            return False
    
    async def _perform_install_async(self, current_exe: Path, backup_path: Path, new_exe_path: Path) -> bool:
        """异步执行安装操作"""
        try:
            # 验证路径安全性
            if not self._validate_paths(current_exe, backup_path, new_exe_path):
                logger.error("路径验证失败，拒绝安装")
                return False
            
            # 在Windows系统上使用批处理脚本进行文件替换
            if self._is_windows():
                return await self._perform_windows_install_async(current_exe, backup_path, new_exe_path)
            else:
                # 非Windows系统的传统安装方式
                return await self._perform_traditional_install_async(current_exe, backup_path, new_exe_path)
            
        except Exception as e:
            logger.error(f"Install operation failed: {e}")
            return False
    
    async def _perform_windows_install_async(self, current_exe: Path, backup_path: Path, new_exe_path: Path) -> bool:
        """Windows系统专用安装方法 - 使用批处理脚本"""
        try:
            # 解压安装助手脚本
            helper_script = self._extract_install_helper()
            if not helper_script:
                logger.error("无法解压安装助手脚本")
                return False
            
            logger.info("使用Windows批处理脚本进行安装...")
            logger.info(f"当前程序: {current_exe}")
            logger.info(f"新程序: {new_exe_path}")
            logger.info(f"备份位置: {backup_path}")
            logger.info(f"助手脚本: {helper_script}")
            
            # 构建批处理脚本命令
            cmd: List[str] = [
                str(helper_script),
                str(current_exe),
                str(new_exe_path),
                str(backup_path)
            ]
            
            # 在后台启动批处理脚本
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: subprocess.Popen(
                    cmd,
                    stdout=None,  # 不重定向输出，让批处理脚本显示在控制台
                    stderr=None,  # 不重定向错误输出
                    stdin=None,   # 不重定向输入
                    creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0
                )
            )

            # 发出重启信号，让UI层处理重启确认
            self.restart_required.emit()
            return True
            
        except Exception as e:
            logger.error(f"Windows安装失败: {e}")
            return False
    
    async def _perform_traditional_install_async(self, current_exe: Path, backup_path: Path, new_exe_path: Path) -> bool:
        """传统安装方法 - 适用于非Windows系统"""
        try:
            # 创建备份
            logger.info(f"Creating backup: {backup_path}")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.copy2, current_exe, backup_path)
            
            # 替换当前可执行文件
            logger.info(f"Installing update: {current_exe}")
            await loop.run_in_executor(None, shutil.move, str(new_exe_path), str(current_exe))
            
            # 清理
            if new_exe_path.exists():
                await loop.run_in_executor(None, new_exe_path.unlink)
                
            return True
            
        except Exception as e:
            logger.error(f"传统安装失败: {e}")
            return False
    
    def restart_application(self) -> None:
        """Restart the application after update"""
        try:
            logger.info("Restarting application...")
            # Start new process
            subprocess.Popen([sys.executable] + sys.argv)
            # Exit current process
            sys.exit(0)
        except Exception as e:
            logger.error(f"Failed to restart application: {e}")
    
    def cancel_current_task(self) -> None:
        """取消当前任务"""
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
            logger.info("已取消当前升级任务")