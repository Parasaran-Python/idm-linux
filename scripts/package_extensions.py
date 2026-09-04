#!/usr/bin/env python3
"""
Cross-Platform Extension Packaging Script for IDM
Packages Chrome MV3 and Firefox extensions into zip/xpi archives.
"""

import json
import os
import shutil
import sys
import zipfile


def get_repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def package_directory_to_zip(source_dir: str, output_zip: str):
    """Zip contents of source_dir into output_zip."""
    os.makedirs(os.path.dirname(os.path.abspath(output_zip)), exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(source_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, source_dir)
                zf.write(abs_path, rel_path)


def package_extensions():
    repo_root = get_repo_root()
    ext_dir = os.path.join(repo_root, "extension")
    dist_dir = os.path.join(repo_root, "dist")
    os.makedirs(dist_dir, exist_ok=True)

    chrome_stage = os.path.join(dist_dir, "chrome-extension")
    firefox_stage = os.path.join(dist_dir, "firefox-extension")

    if os.path.exists(chrome_stage):
        shutil.rmtree(chrome_stage)
    if os.path.exists(firefox_stage):
        shutil.rmtree(firefox_stage)

    os.makedirs(chrome_stage, exist_ok=True)
    os.makedirs(firefox_stage, exist_ok=True)

    # Subdirectories to copy
    subdirs = ["background", "content", "popup", "icons"]

    # 1. Stage Chrome Extension
    print("[*] Packaging Chrome Extension (MV3)...")
    for s in subdirs:
        src = os.path.join(ext_dir, s)
        if os.path.exists(src):
            shutil.copytree(src, os.path.join(chrome_stage, s))
    shutil.copy2(os.path.join(ext_dir, "manifest.json"), os.path.join(chrome_stage, "manifest.json"))

    chrome_zip = os.path.join(dist_dir, "pv-idm-extension-chrome-mv3.zip")
    package_directory_to_zip(chrome_stage, chrome_zip)
    shutil.copy2(chrome_zip, os.path.join(dist_dir, "idm-linux-extension-chrome-mv3.zip"))

    # 2. Stage Firefox Extension
    print("[*] Packaging Firefox Extension (MV2/MV3)...")
    for s in subdirs:
        src = os.path.join(ext_dir, s)
        if os.path.exists(src):
            shutil.copytree(src, os.path.join(firefox_stage, s))
    shutil.copy2(os.path.join(ext_dir, "manifest.firefox.json"), os.path.join(firefox_stage, "manifest.json"))

    firefox_zip = os.path.join(dist_dir, "pv-idm-extension-firefox.zip")
    firefox_xpi = os.path.join(dist_dir, "pv-idm-extension-firefox.xpi")
    package_directory_to_zip(firefox_stage, firefox_zip)
    shutil.copy2(firefox_zip, firefox_xpi)
    shutil.copy2(firefox_zip, os.path.join(dist_dir, "idm-linux-extension-firefox.zip"))
    shutil.copy2(firefox_xpi, os.path.join(dist_dir, "idm-linux-extension-firefox.xpi"))

    # Cleanup staging directories
    shutil.rmtree(chrome_stage, ignore_errors=True)
    shutil.rmtree(firefox_stage, ignore_errors=True)

    print("[OK] Built:")
    print(f"  - {chrome_zip}")
    print(f"  - {firefox_zip}")
    print(f"  - {firefox_xpi}")


if __name__ == "__main__":
    package_extensions()
