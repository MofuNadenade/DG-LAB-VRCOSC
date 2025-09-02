"""
Auto-updater for DG-LAB-VRCOSC
"""

import asyncio
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Callable, Any, Dict, List, Set
from urllib.parse import urlparse

import requests
from packaging import version

from .models import ReleaseInfo

logger = logging.getLogger(__name__)


class AutoUpdater:
    """GitHub Release-based auto updater"""
    
    def __init__(self, repo: str, current_version: str) -> None:
        super().__init__()
        self.repo: str = repo
        self.current_version: str = current_version.lstrip('v')
        self.timeout: int = 30
        self._callbacks: Set[Callable[[str, Any], None]] = set()
        
    def register_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Register a callback for auto-updater events"""
        self._callbacks.add(callback)
        
    def unregister_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Unregister a callback"""
        self._callbacks.discard(callback)
        
    def _notify_callbacks(self, event: str, data: Any = None) -> None:
        """Notify all registered callbacks"""
        for callback in self._callbacks:
            try:
                callback(event, data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
    async def check_for_updates(self) -> Optional[ReleaseInfo]:
        """Check for new releases on GitHub"""
        try:
            loop = asyncio.get_event_loop()
            release_info = await loop.run_in_executor(None, self._fetch_latest_release)
            
            if release_info and self._is_newer_version(release_info.version):
                logger.info(f"New version available: {release_info.version}")
                self._notify_callbacks("update_available", release_info)
                return release_info
            else:
                logger.info("No updates available")
                self._notify_callbacks("no_update_available", None)
                return None
                
        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            self._notify_callbacks("check_error", str(e))
            return None
    
    def _fetch_latest_release(self) -> Optional[ReleaseInfo]:
        """Fetch latest release from GitHub API"""
        api_url: str = f"https://api.github.com/repos/{self.repo}/releases/latest"
        
        try:
            response = requests.get(api_url, timeout=self.timeout)
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            
            # Find Windows exe asset
            download_url: Optional[str] = None
            assets: List[Dict[str, Any]] = data.get('assets', [])
            for asset in assets:
                asset_name = asset.get('name', '')
                if isinstance(asset_name, str) and asset_name.endswith('.exe'):
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
            
        except requests.RequestException as e:
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
    
    async def download_and_install_update(self, release_info: ReleaseInfo, 
                                        progress_callback: Optional[Callable[[int], None]] = None) -> bool:
        """Download and install update"""
        if not release_info.download_url:
            logger.error("No download URL available")
            return False
            
        try:
            # Download update
            loop = asyncio.get_event_loop()
            update_path: Optional[str] = await loop.run_in_executor(
                None, self._download_update, release_info.download_url, progress_callback
            )
            
            if not update_path:
                return False
                
            self._notify_callbacks("download_complete", update_path)
                
            # Install update
            result: bool = await loop.run_in_executor(None, self._install_update, update_path)
            return result
            
        except Exception as e:
            logger.error(f"Failed to download and install update: {e}")
            self._notify_callbacks("download_error", str(e))
            return False
    
    def _download_update(self, download_url: str, progress_callback: Optional[Callable[[int], None]] = None) -> Optional[str]:
        """Download update file"""
        try:
            filename: str = Path(urlparse(download_url).path).name
            update_path: Path = Path.cwd() / f"update_{filename}"
            
            logger.info(f"Downloading update from: {download_url}")
            
            response = requests.get(download_url, stream=True, timeout=self.timeout)
            response.raise_for_status()
            
            total_size: int = int(response.headers.get('content-length', 0))
            downloaded: int = 0
            
            with open(update_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress: int = int((downloaded / total_size) * 100)
                            progress_callback(progress)
            
            logger.info(f"Update downloaded to: {update_path}")
            return str(update_path)
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None
    
    def _install_update(self, update_path: str) -> bool:
        """Install the downloaded update"""
        current_exe: Path = Path(sys.executable)
        backup_path: Path = current_exe.with_suffix('.bak')
        new_exe_path: Path = Path(update_path)
        
        try:
            # Create backup of current executable
            logger.info(f"Creating backup: {backup_path}")
            shutil.copy2(current_exe, backup_path)
            
            # Replace current executable
            logger.info(f"Installing update: {current_exe}")
            shutil.move(str(new_exe_path), str(current_exe))
            
            # Clean up
            if new_exe_path.exists():
                new_exe_path.unlink()
                
            logger.info("Update installed successfully")
            
            # Notify callbacks
            self._notify_callbacks("update_installed", None)
                
            return True
            
        except Exception as e:
            logger.error(f"Installation failed: {e}")
            self._notify_callbacks("install_error", str(e))
            
            # Try to restore backup  
            try:
                if backup_path.exists():
                    shutil.move(str(backup_path), str(current_exe))
                    logger.info("Restored backup after failed installation")
                    self._notify_callbacks("backup_restored", None)
            except Exception as restore_error:
                logger.error(f"Failed to restore backup: {restore_error}")
                self._notify_callbacks("restore_error", str(restore_error))
                    
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