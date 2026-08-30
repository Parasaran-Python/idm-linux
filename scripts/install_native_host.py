#!/usr/bin/env python3
"""
IDM Linux Multi-Browser Native Messaging Host Installer
Registers native messaging manifests for Chrome, Chromium, Brave, Edge, Opera, Vivaldi, Firefox, Librewolf.
"""

import json
import os
import stat
import sys

HOST_NAME = "com.idm.linux.native_host"


def get_repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_wrapper_script(repo_root: str) -> str:
    """Create executable shell wrapper ensuring correct Python interpreter and PYTHONPATH."""
    wrapper_path = os.path.join(repo_root, "scripts", "idm-native-host-wrapper.sh")
    py_exec = sys.executable or "/run/media/parasaran/Dev/SDK/python/install/bin/python3"
    
    script_content = f"""#!/bin/bash
export PYTHONPATH="/usr/lib/python3/dist-packages:/usr/local/lib/python3.14/dist-packages:{repo_root}:$PYTHONPATH"
exec "{py_exec}" -m idm_native_host.host "$@"
"""
    with open(wrapper_path, "w") as f:
        f.write(script_content)
    
    st = os.stat(wrapper_path)
    os.chmod(wrapper_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return wrapper_path


def install_manifests():
    repo_root = get_repo_root()
    wrapper_path = create_wrapper_script(repo_root)
    home = os.path.expanduser("~")

    # Chromium manifest
    chrome_manifest = {
        "name": HOST_NAME,
        "description": "IDM Linux Browser Integration Native Messaging Host",
        "path": wrapper_path,
        "type": "stdio",
        "allowed_origins": [
            "chrome-extension://*/*",
            "chrome-extension://idm-linux-extension-id/"
        ]
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

    installed_count = 0

    # Install for Chromium family
    for target_dir in chromium_targets:
        try:
            os.makedirs(target_dir, exist_ok=True)
            manifest_file = os.path.join(target_dir, f"{HOST_NAME}.json")
            with open(manifest_file, "w") as f:
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
            with open(manifest_file, "w") as f:
                json.dump(firefox_manifest, f, indent=2)
            print(f"[OK] Installed Firefox native host manifest: {manifest_file}")
            installed_count += 1
        except Exception as e:
            print(f"[SKIP] Failed to write {target_dir}: {e}")

    print(f"\nSuccessfully installed IDM Native Messaging Host to {installed_count} browser locations.")
    print(f"Host binary wrapper: {wrapper_path}")


if __name__ == "__main__":
    install_manifests()
