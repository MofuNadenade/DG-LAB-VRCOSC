"""
Auto-updater for DG-LAB-VRCOSC - 整合所有升级逻辑
"""

import asyncio
import logging
import platform
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import List, TypedDict, Any, Callable, Optional
from enum import Enum
from urllib.parse import urlparse
from contextlib import asynccontextmanager

import aiohttp
from packaging import version
from PySide6.QtCore import QObject, Signal

from .models import ReleaseInfo
from models import SettingsDict

logger = logging.getLogger(__name__)


# 常量定义
class AutoUpdaterConstants:
    """自动更新器常量"""
    DEFAULT_TIMEOUT = 30
    WINDOWS_MAX_PATH_LENGTH = 260
    DEFAULT_UPDATE_FILENAME = "DG-LAB-VRCOSC-Update.exe"
    TEMP_DIR_NAME = "DG-LAB-VRCOSC-Update"
    CHUNK_SIZE = 8192
    
    # 下载策略
    STRATEGY_MANUAL = "manual"
    STRATEGY_DOWNLOAD_ONLY = "download_only"
    STRATEGY_DOWNLOAD_AND_INSTALL = "download_and_install"
    
    # 危险字符列表
    DANGEROUS_PATH_CHARS = ['..', '~', '$', '`', '|', '&', ';', '(', ')', '<', '>', '"', '*', '?', '\x00']
    
    # 开发环境指示符
    DEV_INDICATORS = ['python', 'Scripts', 'venv', 'env', 'conda']


class UpdateState(Enum):
    """更新状态枚举"""
    IDLE = "idle"
    CHECKING = "checking"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"


class CheckType(Enum):
    """检查类型枚举"""
    AUTO = "auto"      # 自动检查（启动时）
    MANUAL = "manual"  # 手动检查（用户触发）


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
    no_update_available = Signal(CheckType)  # 传递检查类型
    check_error = Signal(str, CheckType)     # 传递错误信息和检查类型
    download_progress = Signal(int)
    download_complete = Signal(str)
    download_error = Signal(str)
    install_complete = Signal()
    install_error = Signal(str)
    state_changed = Signal(str)  # 新增状态变化信号
    
    def __init__(self, repo: str, current_version: str, settings: SettingsDict) -> None:
        super().__init__()
        self.repo: str = repo
        self.current_version: str = current_version.lstrip('v')
        self.settings: SettingsDict = settings
        self.timeout: int = AutoUpdaterConstants.DEFAULT_TIMEOUT
        
        # 当前任务和状态
        self.current_task: Optional[asyncio.Task[Any]] = None
        self._current_state: UpdateState = UpdateState.IDLE
        
        
    def _set_state(self, state: UpdateState) -> None:
        """设置当前状态并发送信号"""
        if self._current_state != state:
            self._current_state = state
            self.state_changed.emit(state.value)
            logger.debug(f"更新状态变更为: {state.value}")
    
    def get_current_state(self) -> UpdateState:
        """获取当前状态"""
        return self._current_state
    
    @asynccontextmanager
    async def _task_context(self, state: UpdateState, task_name: str, error_handler: Callable[[str], None], allowed_states: Optional[List[UpdateState]] = None):
        """统一的任务执行上下文管理器"""
        if allowed_states is None:
            allowed_states = [UpdateState.IDLE]
            
        if self._current_state not in allowed_states:
            logger.warning(f"{task_name}已在进行中，跳过重复请求")
            yield False
            return
            
        try:
            self._set_state(state)
            yield True
        except asyncio.CancelledError:
            logger.info(f"{task_name}任务被取消")
            raise  # 重新抛出取消异常
        except Exception as e:
            logger.error(f"{task_name}失败: {e}")
            error_handler(str(e))
            raise  # 重新抛出异常以便调用者处理
        finally:
            self._set_state(UpdateState.IDLE)
            self.current_task = None
        
    
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
        
        for indicator in AutoUpdaterConstants.DEV_INDICATORS:
            if indicator in str(exe_path).lower():
                return True
        
        return False
    
    
    def _validate_paths(self, *paths: Path) -> bool:
        """验证路径安全性"""
        try:
            for path in paths:
                # 检查路径是否在允许的范围内
                resolved_path = path.resolve()
                
                # 检查是否包含危险字符
                path_str = str(resolved_path)
                for char in AutoUpdaterConstants.DANGEROUS_PATH_CHARS:
                    if char in path_str:
                        logger.warning(f"路径包含危险字符: {char} in {path_str}")
                        return False
                
                # 检查路径长度
                if len(path_str) > AutoUpdaterConstants.WINDOWS_MAX_PATH_LENGTH:
                    logger.warning(f"路径过长: {len(path_str)} > {AutoUpdaterConstants.WINDOWS_MAX_PATH_LENGTH}")
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
            return AutoUpdaterConstants.STRATEGY_MANUAL
        elif auto_download and not auto_install:
            return AutoUpdaterConstants.STRATEGY_DOWNLOAD_ONLY
        else:
            return AutoUpdaterConstants.STRATEGY_DOWNLOAD_AND_INSTALL
        
    async def check_for_updates(self, check_type: CheckType = CheckType.AUTO) -> Optional[ReleaseInfo]:
        """Check for new releases on GitHub
        
        Args:
            check_type: 检查类型，AUTO为自动检查，MANUAL为手动检查
        """
        try:
            # 创建带检查类型的错误处理函数
            def error_handler(error_msg: str) -> None:
                self.check_error.emit(error_msg, check_type)
            
            async with self._task_context(UpdateState.CHECKING, "更新检查", error_handler) as should_continue:
                if not should_continue:
                    return None
                    
                # 创建异步任务获取最新发布信息并设置为当前任务
                fetch_task = asyncio.create_task(self._fetch_latest_release_async())
                self.current_task = fetch_task
                release_info = await fetch_task
                
                if release_info and self._is_newer_version(release_info.version):
                    logger.info(f"New version available: {release_info.version}")
                    self.update_available.emit(release_info)
                    return release_info
                else:
                    logger.info("No updates available")
                    self.no_update_available.emit(check_type)
                    return None
        except asyncio.CancelledError:
            return None
        except Exception:
            return None
    
    async def _fetch_latest_release_async(self) -> Optional[ReleaseInfo]:
        """异步获取最新发布信息"""
        api_url: str = f"https://api.github.com/repos/{self.repo}/releases/latest"
        
        try:
            # 使用trust_env=True自动使用系统代理
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                trust_env=True
            ) as session:
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
    
    async def download_update(self, release_info: ReleaseInfo, save_path: Optional[str] = None) -> Optional[str]:
        """下载更新到指定路径，如果未指定路径则下载到临时目录"""
        if not release_info.download_url:
            self.download_error.emit("没有可用的下载链接")
            return None
            
        try:
            async with self._task_context(UpdateState.DOWNLOADING, "下载", lambda msg: self.download_error.emit(msg), 
                                       [UpdateState.IDLE, UpdateState.CHECKING]) as should_continue:
                if not should_continue:
                    return None
                
                # 取消之前的任务
                if self.current_task and not self.current_task.done():
                    self.current_task.cancel()
                    try:
                        await asyncio.wait_for(self.current_task, timeout=1.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass  # 预期的取消或超时
                
                # 确定下载路径
                if save_path:
                    target_path = Path(save_path)
                else:
                    # 下载到临时目录
                    filename = Path(str(urlparse(release_info.download_url).path)).name
                    if not filename:
                        filename = AutoUpdaterConstants.DEFAULT_UPDATE_FILENAME
                        
                    temp_dir = Path(tempfile.gettempdir()) / AutoUpdaterConstants.TEMP_DIR_NAME
                    temp_dir.mkdir(exist_ok=True)
                    
                    # 添加随机后缀避免冲突
                    base_name = Path(filename).stem
                    extension = Path(filename).suffix
                    random_suffix = str(uuid.uuid4())[:8]
                    filename_with_suffix = f"{base_name}_{random_suffix}{extension}"
                    target_path = temp_dir / filename_with_suffix
                
                # 创建下载任务并设置为当前任务
                download_task = asyncio.create_task(self._download_to_path(release_info.download_url, target_path))
                self.current_task = download_task
                return await download_task
                
        except asyncio.CancelledError:
            return None
        except Exception:
            return None
    
    
    async def _download_to_path(self, download_url: str, target_path: Path) -> Optional[str]:
        """下载文件到指定路径"""
        try:
            logger.info(f"开始下载: {download_url}")
            
            # 使用trust_env=True自动使用系统代理
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                trust_env=True
            ) as session:
                async with session.get(download_url) as response:
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    with open(target_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(AutoUpdaterConstants.CHUNK_SIZE):
                            # 检查是否被取消（在写入前检查，避免写入无用数据）
                            if self.current_task and self.current_task.cancelled():
                                logger.info("下载任务被取消")
                                # 删除未完成的文件
                                try:
                                    if target_path.exists():
                                        target_path.unlink()
                                except Exception as cleanup_error:
                                    logger.warning(f"清理未完成下载文件失败: {cleanup_error}")
                                return None
                                
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
        if self._current_state not in [UpdateState.IDLE, UpdateState.DOWNLOADING]:
            logger.warning("安装已在进行中，跳过重复请求")
            return False
            
        try:
            # 检测开发环境，如果是在开发环境中则拒绝安装
            if self._is_development_environment():
                error_msg = "检测到开发环境，无法安装更新以避免覆盖Python解释器"
                logger.warning(error_msg)
                self.install_error.emit(error_msg)
                return False
            
            self._set_state(UpdateState.INSTALLING)
            
            # 取消之前的任务
            if self.current_task and not self.current_task.done():
                self.current_task.cancel()
                try:
                    await asyncio.wait_for(self.current_task, timeout=1.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass  # 预期的取消或超时
            
            # 创建安装任务并设置为当前任务
            install_task = asyncio.create_task(self._install_update_async(update_path))
            self.current_task = install_task
            return await install_task
            
        except asyncio.CancelledError:
            logger.info("安装任务被取消")
            return False
        except Exception as e:
            logger.error(f"安装更新失败: {e}")
            self.install_error.emit(str(e))
            return False
        finally:
            self._set_state(UpdateState.IDLE)
            self.current_task = None
    
    async def download_and_install_update(self, release_info: ReleaseInfo) -> bool:
        """Download and install update"""
        if not release_info.download_url:
            logger.error("No download URL available")
            self.download_error.emit("没有可用的下载链接")
            return False
        
        # 检测开发环境，如果是在开发环境中则拒绝安装
        if self._is_development_environment():
            error_msg = "检测到开发环境，无法安装更新以避免覆盖Python解释器"
            logger.warning(error_msg)
            self.install_error.emit(error_msg)
            return False
            
        try:
            # 创建组合任务并设置为当前任务
            combined_task = asyncio.create_task(self._download_and_install_task(release_info))
            self.current_task = combined_task
            return await combined_task
            
        except asyncio.CancelledError:
            logger.info("下载安装任务被取消")
            return False
        except Exception as e:
            logger.error(f"Failed to download and install update: {e}")
            self.download_error.emit(str(e))
            return False
        finally:
            self.current_task = None
    
    async def _download_and_install_task(self, release_info: ReleaseInfo) -> bool:
        """下载和安装的组合任务"""
        # 先下载到临时目录
        download_path = await self.download_update(release_info)
        if not download_path:
            return False
        
        # 再安装
        return await self.install_update(download_path)
    
    
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
                self.install_complete.emit()
            else:
                logger.error("Installation failed")
                self.install_error.emit("Installation failed")
                
            return result
            
        except Exception as e:
            logger.error(f"Installation failed: {e}")
            self.install_error.emit(str(e))
            
            # 尝试恢复备份
            try:
                if backup_path.exists():
                    shutil.move(str(backup_path), str(current_exe))
                    logger.info("Restored backup after failed installation")
            except Exception as restore_error:
                logger.error(f"Failed to restore backup: {restore_error}")
                    
            return False
    
    async def _perform_install_async(self, current_exe: Path, backup_path: Path, new_exe_path: Path) -> bool:
        """异步执行安装操作 - 使用重命名策略绕过文件锁定"""
        try:
            # 验证路径安全性
            if not self._validate_paths(current_exe, backup_path, new_exe_path):
                logger.error("路径验证失败，拒绝安装")
                return False
            
            # 使用重命名策略进行安装
            return await self._perform_rename_install_async(current_exe, backup_path, new_exe_path)
            
        except Exception as e:
            logger.error(f"Install operation failed: {e}")
            return False
    
    async def _perform_rename_install_async(self, current_exe: Path, backup_path: Path, new_exe_path: Path) -> bool:
        """使用重命名策略安装更新 - 绕过文件锁定问题"""
        try:
            loop = asyncio.get_event_loop()
            
            logger.info("使用重命名策略进行安装...")
            logger.info(f"当前程序: {current_exe}")
            logger.info(f"新程序: {new_exe_path}")
            logger.info(f"备份位置: {backup_path}")
            
            logger.info("准备执行安装操作...")
            
            # 删除可能存在的老备份文件
            if backup_path.exists():
                logger.info(f"删除已存在的备份文件: {backup_path}")
                await loop.run_in_executor(None, backup_path.unlink)
            
            # 将当前可执行文件重命名为备份文件，释放原文件名的占用
            logger.info(f"重命名当前程序为备份文件: {current_exe} -> {backup_path}")
            await loop.run_in_executor(None, shutil.move, str(current_exe), str(backup_path))
            
            # 将新的可执行文件复制到原位置
            logger.info(f"复制新程序到原位置: {new_exe_path} -> {current_exe}")
            await loop.run_in_executor(None, shutil.copy2, str(new_exe_path), str(current_exe))
            
            # 设置可执行权限（在类Unix系统上）
            if platform.system().lower() != 'windows':
                import stat
                await loop.run_in_executor(
                    None, 
                    current_exe.chmod, 
                    stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
                )
                logger.info("已设置可执行权限")
            
            # 清理临时文件
            if new_exe_path.exists():
                await loop.run_in_executor(None, new_exe_path.unlink)
                logger.info("已清理临时文件")
            
            logger.info("安装完成，请重启应用程序以使用新版本")
            return True
            
        except Exception as e:
            logger.error(f"重命名策略安装失败: {e}")
            
            # 尝试恢复：如果备份存在且当前exe不存在，则恢复备份
            try:
                if backup_path.exists() and not current_exe.exists():
                    logger.info("尝试恢复备份文件...")
                    restore_loop = asyncio.get_event_loop()
                    await restore_loop.run_in_executor(None, shutil.move, str(backup_path), str(current_exe))
                    logger.info("已恢复备份文件")
            except Exception as restore_error:
                logger.error(f"恢复备份失败: {restore_error}")
            
            return False
    
    def cancel_current_task(self) -> None:
        """取消当前任务"""
        if self.current_task and not self.current_task.done():
            logger.info(f"正在取消当前任务: {self.current_task}")
            self.current_task.cancel()
            try:
                # 等待任务真正取消
                asyncio.create_task(self._wait_for_cancellation())
            except Exception as e:
                logger.error(f"等待任务取消时出错: {e}")
            logger.info("已取消当前升级任务")
        else:
            logger.info("没有正在运行的任务需要取消")
    
    async def _wait_for_cancellation(self) -> None:
        """等待任务取消完成"""
        if self.current_task:
            try:
                await asyncio.wait_for(self.current_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass  # 预期的取消或超时
            except Exception as e:
                logger.debug(f"任务取消过程中的异常（可忽略）: {e}")
            finally:
                self.current_task = None