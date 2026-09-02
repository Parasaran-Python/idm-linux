#!/usr/bin/env python3
"""
IDM Linux Multi-Browser Native Messaging Host Installer
Registers native messaging manifests for Chrome, Chromium, Brave, Edge, Opera, Vivaldi, Firefox, Librewolf.
"""

import argparse
import base64
import hashlib
import json
import os
import stat
import sys
from typing import List, Optional

HOST_NAME = "com.idm.linux.native_host"


def get_repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def derive_chrome_extension_id(key_b64: str) -> str:
    """Compute 32-character Chrome extension ID from public key DER base64."""
    try:
        der = base64.b64decode(key_b64)
        sha = hashlib.sha256(der).digest()
        return "".join(chr(ord("a") + (b >> 4)) + chr(ord("a") + (b & 0x0F)) for b in sha[:16])
    except Exception:
        return ""


def get_default_chrome_extension_ids(repo_root: str) -> List[str]:
    """Extract standard extension IDs from manifest.json and defaults."""
    ids = set()
    manifest_path = os.path.join(repo_root, "extension", "manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                key = data.get("key")
                if key:
                    derived_id = derive_chrome_extension_id(key)
                    if derived_id:
                        ids.add(derived_id)
        except Exception:
            pass

    # Ensure known fixed ID is present
    if not ids:
        ids.add("cacfhfpjipjnanbefddajafhgpmpibej")
    return sorted(list(ids))


def create_wrapper_script(repo_root: str) -> str:
    """Create executable shell wrapper or batch wrapper ensuring correct Python interpreter and PYTHONPATH."""
    py_exec = sys.executable or ("python.exe" if sys.platform == "win32" else "/usr/bin/python3")

    if sys.platform == "win32":
        wrapper_path = os.path.join(repo_root, "scripts", "idm-native-host-wrapper.bat")
        script_content = f"""@echo off
setlocal
set "PYTHONPATH={repo_root};%PYTHONPATH%"
"{py_exec}" -m idm_native_host.host %*
"""
        with open(wrapper_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        return wrapper_path

    wrapper_path = os.path.join(repo_root, "scripts", "idm-native-host-wrapper.sh")
    script_content = f"""#!/bin/bash
export PYTHONPATH="/usr/lib/python3/dist-packages:/usr/local/lib/python3.14/dist-packages:{repo_root}:$PYTHONPATH"
exec "{py_exec}" -m idm_native_host.host "$@"
"""
    with open(wrapper_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    st = os.stat(wrapper_path)
    os.chmod(wrapper_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return wrapper_path


def install_manifests(custom_chrome_ids: Optional[List[str]] = None):
    repo_root = get_repo_root()
    wrapper_path = create_wrapper_script(repo_root)
    home = os.path.expanduser("~")

    chrome_ids = get_default_chrome_extension_ids(repo_root)
    if custom_chrome_ids:
        for cid in custom_chrome_ids:
            clean_id = cid.strip()
            if clean_id and clean_id not in chrome_ids:
                chrome_ids.append(clean_id)

    env_id = os.environ.get("IDM_CHROME_EXTENSION_ID")
    if env_id and env_id.strip() not in chrome_ids:
        chrome_ids.append(env_id.strip())

    # Build allowed_origins for Chromium (must be exact: chrome-extension://<id>/)
    allowed_origins = [f"chrome-extension://{cid}/" for cid in chrome_ids]

    # Chromium manifest
    chrome_manifest = {
        "name": HOST_NAME,
        "description": "IDM Linux Browser Integration Native Messaging Host",
        "path": wrapper_path,
        "type": "stdio",
        "allowed_origins": allowed_origins
    }

    # Firefox manifest
    firefox_manifest = {
        "name": HOST_NAME,
        "description": "IDM Linux Browser Integration Native Messaging Host",
        "path": wrapper_path,
        "type": "stdio",
        "allowed_extensions": [
            "idm-linux@idm-linux.local"
        ]
    }

    installed_count = 0

    # Windows: Register manifests via Windows Registry (HKCU\Software\...\NativeMessagingHosts)
    if sys.platform == "win32":
        try:
            import winreg

            manifests_dir = os.path.join(repo_root, "scripts")
            chrome_manifest_file = os.path.join(manifests_dir, f"{HOST_NAME}.json")
            firefox_manifest_file = os.path.join(manifests_dir, f"{HOST_NAME}.firefox.json")

            with open(chrome_manifest_file, "w", encoding="utf-8") as f:
                json.dump(chrome_manifest, f, indent=2)
            with open(firefox_manifest_file, "w", encoding="utf-8") as f:
                json.dump(firefox_manifest, f, indent=2)

            reg_paths_chrome = [
                r"Software\Google\Chrome\NativeMessagingHosts",
                r"Software\Microsoft\Edge\NativeMessagingHosts",
                r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts",
            ]

            for rp in reg_paths_chrome:
                try:
                    full_key = f"{rp}\\{HOST_NAME}"
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, full_key) as k:
                        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, chrome_manifest_file)
                    print(f"[OK] Registered Windows Registry key: HKCU\\{full_key}")
                    installed_count += 1
                except Exception as e:
                    print(f"[SKIP] Failed to register HKCU\\{rp}: {e}")

            # Firefox
            try:
                ff_key = f"Software\\Mozilla\\NativeMessagingHosts\\{HOST_NAME}"
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ff_key) as k:
                    winreg.SetValueEx(k, "", 0, winreg.REG_SZ, firefox_manifest_file)
                print(f"[OK] Registered Windows Registry key: HKCU\\{ff_key}")
                installed_count += 1
            except Exception as e:
                print(f"[SKIP] Failed to register Firefox HKCU\\{ff_key}: {e}")

        except Exception as e:
            print(f"[ERROR] Windows registry registration failed: {e}")

    else:
        # Linux / POSIX filesystem directories
        chromium_targets = [
            os.path.join(home, ".config", "google-chrome", "NativeMessagingHosts"),
            os.path.join(home, ".config", "chromium", "NativeMessagingHosts"),
            os.path.join(home, ".config", "BraveSoftware", "Brave-Browser", "NativeMessagingHosts"),
            os.path.join(home, ".config", "microsoft-edge", "NativeMessagingHosts"),
            os.path.join(home, ".config", "opera", "NativeMessagingHosts"),
            os.path.join(home, ".config", "vivaldi", "NativeMessagingHosts"),
        ]

        firefox_targets = [
            os.path.join(home, ".mozilla", "native-messaging-hosts"),
            os.path.join(home, ".librewolf", "native-messaging-hosts"),
        ]

        # Install for Chromium family
        for target_dir in chromium_targets:
            try:
                os.makedirs(target_dir, exist_ok=True)
                manifest_file = os.path.join(target_dir, f"{HOST_NAME}.json")
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(chrome_manifest, f, indent=2)
                print(f"[OK] Installed Chrome native host manifest: {manifest_file}")
                installed_count += 1
            except Exception as e:
                print(f"[SKIP] Failed to write {target_dir}: {e}")

        # Install for Firefox family
        for target_dir in firefox_targets:
            try:
                os.makedirs(target_dir, exist_ok=True)
                manifest_file = os.path.join(target_dir, f"{HOST_NAME}.json")
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(firefox_manifest, f, indent=2)
                print(f"[OK] Installed Firefox native host manifest: {manifest_file}")
                installed_count += 1
            except Exception as e:
                print(f"[SKIP] Failed to write {target_dir}: {e}")

    print(f"\nSuccessfully installed IDM Native Messaging Host to {installed_count} browser locations.")
    print(f"Host binary wrapper: {wrapper_path}")
    print(f"Allowed Chrome origins: {allowed_origins}")
    print("Allowed Firefox extensions: ['idm-linux@idm-linux.local']")


def main():
    parser = argparse.ArgumentParser(description="Install IDM Linux native messaging host manifests.")
    parser.add_argument(
        "--chrome-extension-id", "-e",
        action="append",
        dest="chrome_ids",
        help="Additional Chrome extension ID to allow in native messaging manifest."
    )
    args = parser.parse_args()
    install_manifests(custom_chrome_ids=args.chrome_ids)


if __name__ == "__main__":
    main()
