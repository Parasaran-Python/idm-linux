"""
Storage Manager: Sparse File Allocation, Temporary Segment I/O, and Merging
"""

import hashlib
import os
import shutil
from typing import Any, List, Optional
from idm_core.config import Config


class StorageManager:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.config.ensure_directories()

    def prepare_download_file(self, filepath: str, total_bytes: int = 0) -> str:
        """Pre-allocate destination file space."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        if total_bytes > 0:
            try:
                with open(filepath, "wb") as f:
                    f.truncate(total_bytes)
            except Exception:
                with open(filepath, "wb") as f:
                    f.seek(total_bytes - 1)
                    f.write(b"\0")
        else:
            with open(filepath, "wb") as f:
                pass
        return filepath

    def get_temp_segment_path(self, download_id: str, segment_idx: int) -> str:
        """Return the temporary path for a specific segment."""
        temp_dl_dir = os.path.join(self.config.temp_dir, download_id)
        os.makedirs(temp_dl_dir, exist_ok=True)
        return os.path.join(temp_dl_dir, f"seg_{segment_idx}.part")

    def write_segment_chunk(self, temp_path: str, offset: int, data: bytes):
        """Write chunk at specific offset in temporary segment file."""
        os.makedirs(os.path.dirname(os.path.abspath(temp_path)), exist_ok=True)
        mode = "r+b" if os.path.exists(temp_path) else "wb"
        with open(temp_path, mode) as f:
            f.seek(offset)
            f.write(data)

    def append_segment_chunk(self, temp_path: str, data: bytes):
        """Append chunk to temporary segment file."""
        os.makedirs(os.path.dirname(os.path.abspath(temp_path)), exist_ok=True)
        with open(temp_path, "ab") as f:
            f.write(data)

    def merge_segments(
        self,
        download_id: str,
        segment_files: List[Any],
        destination_path: str,
        total_bytes: Optional[int] = None
    ) -> bool:
        """Merge segment files in sequence into the final destination file."""
        os.makedirs(os.path.dirname(os.path.abspath(destination_path)), exist_ok=True)
        temp_dest = destination_path + ".merging"

        with open(temp_dest, "wb") as outfile:
            for item in segment_files:
                if isinstance(item, tuple):
                    seg_file, max_bytes = item
                else:
                    seg_file, max_bytes = item, None

                if not os.path.exists(seg_file):
                    continue

                with open(seg_file, "rb") as infile:
                    if max_bytes is not None and max_bytes >= 0:
                        remaining = max_bytes
                        while remaining > 0:
                            chunk_size = min(1024 * 1024, remaining)
                            chunk = infile.read(chunk_size)
                            if not chunk:
                                break
                            outfile.write(chunk)
                            remaining -= len(chunk)
                    else:
                        shutil.copyfileobj(infile, outfile, length=1024 * 1024)

        if os.path.exists(destination_path):
            os.remove(destination_path)
        os.rename(temp_dest, destination_path)
        return True

    def verify_checksum(self, filepath: str, expected_hash: str, algorithm: str = "sha256") -> bool:
        """Verify the integrity of a file against expected hash string."""
        if not os.path.exists(filepath):
            return False
        algo = algorithm.lower().strip()
        if algo == "sha256":
            hasher = hashlib.sha256()
        elif algo == "sha1":
            hasher = hashlib.sha1()
        elif algo == "md5":
            hasher = hashlib.md5()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")

        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)

        calculated = hasher.hexdigest().lower()
        return calculated == expected_hash.lower().strip()

    def cleanup_temp(self, download_id: str):
        """Remove temporary segments folder for a download."""
        temp_dl_dir = os.path.join(self.config.temp_dir, download_id)
        if os.path.exists(temp_dl_dir):
            shutil.rmtree(temp_dl_dir, ignore_errors=True)

    def get_free_space(self, path: Optional[str] = None) -> int:
        """Return free space in bytes at the specified path."""
        target = path or self.config.download_dir
        if not os.path.exists(target):
            os.makedirs(target, exist_ok=True)
        return shutil.disk_usage(target).free

    def get_unique_filename(self, directory: str, filename: str) -> str:
        """Generate a collision-free filename in directory (e.g. file (1).zip)."""
        base, ext = os.path.splitext(filename)
        candidate = filename
        counter = 1
        while os.path.exists(os.path.join(directory, candidate)):
            candidate = f"{base} ({counter}){ext}"
            counter += 1
        return candidate
