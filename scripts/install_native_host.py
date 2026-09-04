#!/usr/bin/env python3
"""
IDM Linux Multi-Browser Native Messaging Host Installer
Registers native messaging manifests for Chrome, Chromium, Brave, Edge, Opera, Vivaldi, Firefox, Librewolf.
"""

import argparse
import os
import sys
from typing import List, Optional

# Ensure repository root is on sys.path so idm_core is importable
_script_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.dirname(_script_dir)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from idm_core.platform import (
    NATIVE_HOST_NAME as HOST_NAME,
    derive_chrome_extension_id,
    get_default_chrome_extension_ids,
    is_native_messaging_host_registered,
    register_native_messaging_host,
    resolve_native_host_binary,
    unregister_native_messaging_host,
)


def get_repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_wrapper_script(repo_root: Optional[str] = None, binary_path: Optional[str] = None) -> str:
    """Resolve native host binary or create executable wrapper."""
    root = repo_root or get_repo_root()
    resolved = resolve_native_host_binary(binary_path, root)
    if resolved:
        return resolved

    _, _, host_path = register_native_messaging_host(binary_path=binary_path, repo_root=root)
    return host_path


def install_manifests(
    custom_chrome_ids: Optional[List[str]] = None,
    binary_path: Optional[str] = None,
    repo_root: Optional[str] = None
) -> bool:
    """Install native messaging host manifests into browser locations."""
    root = repo_root or get_repo_root()
    success, count, host_path = register_native_messaging_host(
        binary_path=binary_path,
        custom_chrome_ids=custom_chrome_ids,
        repo_root=root
    )

    chrome_ids = get_default_chrome_extension_ids(root)
    if custom_chrome_ids:
        for cid in custom_chrome_ids:
            clean_id = (cid or "").strip()
            if clean_id and clean_id not in chrome_ids:
                chrome_ids.append(clean_id)
    allowed_origins = [f"chrome-extension://{cid}/" for cid in chrome_ids]

    if success:
        print(f"\nSuccessfully installed PV-IDM Native Messaging Host to {count} browser locations.")
        print(f"Host binary wrapper: {host_path}")
        print(f"Allowed Chrome origins: {allowed_origins}")
        print("Allowed Firefox extensions: ['pv-idm@pv-idm.local', 'idm-linux@idm-linux.local']")
    else:
        print("\n[WARNING] Failed to register native messaging host manifests.")
    return success


# Aliases for convenient import
register_native_host = register_native_messaging_host
unregister_native_host = unregister_native_messaging_host
is_native_host_registered = is_native_messaging_host_registered


def main():
    parser = argparse.ArgumentParser(description="Install PV-IDM native messaging host manifests.")
    parser.add_argument(
        "--chrome-extension-id", "-e",
        action="append",
        dest="chrome_ids",
        help="Additional Chrome extension ID to allow in native messaging manifest."
    )
    parser.add_argument(
        "--binary-path", "-b",
        dest="binary_path",
        help="Explicit path to idm-native-host executable."
    )
    parser.add_argument(
        "--uninstall", "-u",
        action="store_true",
        help="Unregister and remove native messaging host manifests."
    )
    args = parser.parse_args()

    if args.uninstall:
        ok = unregister_native_messaging_host()
        if ok:
            print("[OK] Successfully uninstalled IDM native messaging host manifests.")
        else:
            print("[INFO] No IDM native messaging host manifests were found to remove.")
        return

    install_manifests(custom_chrome_ids=args.chrome_ids, binary_path=args.binary_path)


if __name__ == "__main__":
    main()
