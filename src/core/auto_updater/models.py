"""
Data models for auto-updater
"""

from typing import Optional
from pydantic import BaseModel


class ReleaseInfo(BaseModel):
    """GitHub release information"""
    tag_name: str
    name: str
    body: str
    download_url: Optional[str] = None
    published_at: str
    prerelease: bool = False
    
    @property
    def version(self) -> str:
        """Extract version from tag name"""
        return self.tag_name.lstrip('v')
        
