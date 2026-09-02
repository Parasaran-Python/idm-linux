#!/usr/bin/env python3
"""
Download Windows Third-Party Binaries for Packaging (Phase 6)
Fetches official standalone yt-dlp.exe and ffmpeg.exe into bin/ directory.
"""

import argparse
import io
import os
import shutil
import sys
import urllib.request
import zipfile

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
# Gyan.dev or BtbN official FFmpeg builds
FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def download_file(url: str, dest_path: str):
    print(f"[*] Downloading {url} -> {dest_path}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as out_f:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        while chunk := resp.read(65536):
            out_f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = (downloaded / total) * 100
                sys.stdout.write(f"\r  Progress: {pct:.1f}% ({downloaded}/{total} bytes)")
                sys.stdout.flush()
    print("\n[OK] Download complete.")


def download_ytdlp(bin_dir: str):
    dest = os.path.join(bin_dir, "yt-dlp.exe")
    if os.path.exists(dest) and os.path.getsize(dest) > 1000000:
        print(f"[*] yt-dlp.exe already exists at {dest} ({os.path.getsize(dest)} bytes). Skipping.")
        return
    try:
        download_file(YTDLP_URL, dest)
    except Exception as e:
        print(f"[WARN] Failed to download yt-dlp.exe: {e}")


def download_ffmpeg(bin_dir: str):
    dest_ffmpeg = os.path.join(bin_dir, "ffmpeg.exe")
    if os.path.exists(dest_ffmpeg) and os.path.getsize(dest_ffmpeg) > 1000000:
        print(f"[*] ffmpeg.exe already exists at {dest_ffmpeg}. Skipping.")
        return

    temp_zip = os.path.join(bin_dir, "ffmpeg_temp.zip")
    try:
        download_file(FFMPEG_ZIP_URL, temp_zip)
        print("[*] Extracting ffmpeg.exe from archive...")
        with zipfile.ZipFile(temp_zip, "r") as zf:
            for item in zf.namelist():
                if item.endswith("bin/ffmpeg.exe") or item.endswith("/ffmpeg.exe") or item == "ffmpeg.exe":
                    with zf.open(item) as src, open(dest_ffmpeg, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    print(f"[OK] Extracted {dest_ffmpeg}")
                    break
    except Exception as e:
        print(f"[WARN] Failed to download ffmpeg: {e}")
    finally:
        if os.path.exists(temp_zip):
            try:
                os.remove(temp_zip)
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Download official Windows binaries (yt-dlp, ffmpeg) for bundling.")
    parser.add_argument(
        "--output-dir",
        "-o",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin"),
        help="Target directory for downloaded binaries (default: bin/)"
    )
    parser.add_argument("--ytdlp-only", action="store_true", help="Download only yt-dlp.exe")
    parser.add_argument("--ffmpeg-only", action="store_true", help="Download only ffmpeg.exe")

    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    if not args.ffmpeg_only:
        download_ytdlp(args.output_dir)
    if not args.ytdlp_only:
        download_ffmpeg(args.output_dir)

    print(f"\n[DONE] Bundling directory ready: {args.output_dir}")


if __name__ == "__main__":
    main()
