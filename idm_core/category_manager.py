"""
Category Manager: Automatic File Type and MIME Classification
"""

import os
from typing import Dict, List, Optional
from idm_core.config import Config


class CategoryManager:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.categories: Dict[str, List[str]] = dict(self.config.categories)

    def add_category_extension(self, category: str, extension: str):
        """Dynamically add or override an extension for a category."""
        ext_clean = extension.lower().lstrip(".")
        if category not in self.categories:
            self.categories[category] = []
        if ext_clean not in self.categories[category]:
            self.categories[category].append(ext_clean)

    def get_category_for_filename(self, filename: str) -> str:
        """Determine category from filename extension."""
        if not filename:
            return "General"

        name_lower = filename.lower().strip()
        # Handle composite extensions like .tar.gz
        parts = name_lower.split(".")
        if len(parts) > 2 and parts[-2] == "tar":
            ext = f"tar.{parts[-1]}"
        elif len(parts) > 1:
            ext = parts[-1]
        else:
            return "General"

        for cat, ext_list in self.categories.items():
            if ext in ext_list:
                return cat
            # Check single ext part for .tar.gz
            if parts[-1] in ext_list:
                return cat

        return "General"

    def get_category_for_mime(self, mime_type: str) -> str:
        """Determine category from HTTP Content-Type MIME string."""
        if not mime_type:
            return "General"

        mime = mime_type.lower().split(";")[0].strip()
        if mime.startswith("video/"):
            return "Video"
        if mime.startswith("audio/"):
            return "Music"
        if "zip" in mime or "tar" in mime or "compressed" in mime or "archive" in mime or "7z" in mime:
            return "Compressed"
        if "pdf" in mime or "document" in mime or "msword" in mime or "text/" in mime or "sheet" in mime:
            return "Documents"
        if "executable" in mime or "octet-stream" in mime and ("exe" in mime or "deb" in mime or "rpm" in mime):
            return "Programs"

        return "General"

    def get_category(self, filename: str, mime_type: Optional[str] = None) -> str:
        """Resolve category with precedence: filename extension first, then MIME."""
        cat = self.get_category_for_filename(filename)
        if cat != "General":
            return cat
        if mime_type:
            mime_cat = self.get_category_for_mime(mime_type)
            if mime_cat != "General":
                return mime_cat
        return "General"

    def get_destination_directory(self, category: str, base_download_dir: Optional[str] = None) -> str:
        """Get destination subfolder for category."""
        base = base_download_dir or self.config.download_dir
        if category and category in self.categories and category != "General":
            cat_dir = os.path.join(base, category)
            os.makedirs(cat_dir, exist_ok=True)
            return cat_dir
        return base
