"""
Configuration and Defaults for IDM Linux
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from idm_core.platform import (
    get_config_dir,
    get_database_path,
    get_default_ipc_endpoint,
    get_download_dir,
    get_temp_dir,
)


@dataclass
class Config:
    config_dir: str = field(default_factory=lambda: get_config_dir())
    database_path: Optional[str] = None
    socket_path: Optional[str] = None
    temp_dir: Optional[str] = None
    download_dir: Optional[str] = None
    
    # Engine Settings
    max_connections: int = 8
    max_concurrent_downloads: int = 4
    speed_limit: int = 0  # 0 = unlimited, in bytes/sec
    min_split_size: int = 1048576  # 1 MB minimum remaining to dynamically split chunk
    chunk_read_size: int = 65536  # 64 KB buffer
    network_timeout: int = 30  # seconds
    max_retries: int = 10
    retry_delay: int = 3  # seconds
    
    # Category Mappings & Intercept Extensions
    categories: Dict[str, List[str]] = field(default_factory=lambda: {
        "Compressed": ["zip", "rar", "7z", "tar", "gz", "bz2", "xz", "iso", "tgz", "zst", "apk"],
        "Documents": ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "rtf", "epub", "mobi", "csv"],
        "Music": ["mp3", "flac", "aac", "wav", "ogg", "m4a", "wma", "opus", "alac"],
        "Programs": ["exe", "msi", "deb", "rpm", "appimage", "bin", "run", "sh", "dmg", "pkg"],
        "Video": ["mp4", "mkv", "avi", "webm", "flv", "mov", "wmv", "m4v", "ts", "m3u8", "mpd"]
    })
    
    # Default file extensions to automatically intercept from browser
    intercept_extensions: List[str] = field(default_factory=lambda: [
        "3gp", "7z", "aac", "ace", "aif", "apk", "appimage", "arj", "asf", "avi", "bin", "bz2",
        "deb", "dmg", "doc", "docx", "epub", "exe", "flac", "flv", "gz", "iso", "jar", "m4a",
        "m4v", "mkv", "mov", "mp3", "mp4", "mpa", "mpe", "mpeg", "mpg", "msi", "ogg", "opus",
        "pdf", "pkg", "ppt", "pptx", "rar", "rpm", "rtf", "sh", "tar", "tgz", "torrent", "ts",
        "txt", "wav", "webm", "wma", "wmv", "xls", "xlsx", "xz", "zip", "zst"
    ])
    
    # File extensions to ignore
    ignore_extensions: List[str] = field(default_factory=lambda: [
        "html", "htm", "php", "asp", "aspx", "jsp", "css", "js", "json", "xml"
    ])

    @property
    def ipc_endpoint(self) -> str:
        return self.socket_path or get_default_ipc_endpoint(self.config_dir)

    def __post_init__(self):
        if not self.config_dir:
            self.config_dir = get_config_dir()
        if not self.database_path:
            self.database_path = get_database_path(self.config_dir)
        if not self.socket_path:
            self.socket_path = get_default_ipc_endpoint(self.config_dir)
        if not self.temp_dir:
            self.temp_dir = get_temp_dir(self.config_dir)
        if not self.download_dir:
            self.download_dir = get_download_dir()

    def ensure_directories(self):
        """Create necessary config, temp, and download category directories."""
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.download_dir, exist_ok=True)
        for cat in self.categories.keys():
            os.makedirs(os.path.join(self.download_dir, cat), exist_ok=True)

    def get_category_path(self, category: str) -> str:
        """Return destination folder for a specific category."""
        if category and category in self.categories:
            cat_dir = os.path.join(self.download_dir, category)
            os.makedirs(cat_dir, exist_ok=True)
            return cat_dir
        return self.download_dir
