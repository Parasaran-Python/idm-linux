#!/usr/bin/env python3
"""
IDM Linux Browser Native Messaging Host (Chrome / Firefox Stdio Bridge)
"""

import json
import os
import struct
import subprocess
import sys
import time
from typing import Any, Dict, Optional
import idm_core
from idm_ipc.socket_client import IPCClient

HOST_NAME = "com.idm.linux.native_host"


def read_native_message(stream=None) -> Optional[Dict[str, Any]]:
    """Read a 32-bit little-endian length-prefixed JSON message from stream (default: sys.stdin.buffer)."""
    inp = stream or sys.stdin.buffer
    raw_len = inp.read(4)
    if not raw_len or len(raw_len) < 4:
        return None
    msg_len = struct.unpack("<I", raw_len)[0]
    if msg_len == 0 or msg_len > 16 * 1024 * 1024:
        return None
    data = inp.read(msg_len)
    if len(data) < msg_len:
        return None
    return json.loads(data.decode("utf-8"))


def send_native_message(payload: Dict[str, Any], stream=None):
    """Write a 32-bit little-endian length-prefixed JSON message to stream (default: sys.stdout.buffer)."""
    out = stream or sys.stdout.buffer
    json_bytes = json.dumps(payload).encode("utf-8")
    header = struct.pack("<I", len(json_bytes))
    out.write(header + json_bytes)
    out.flush()


def ensure_idm_running(client: IPCClient) -> bool:
    """Check if IDM daemon or GUI is running; if not, spawn GUI/daemon in background."""
    if client.is_server_running():
        return True

    env = os.environ.copy()
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    py_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"/usr/lib/python3/dist-packages:{repo_root}:{py_path}".strip(":")

    uid = os.getuid()
    env.setdefault("DISPLAY", ":0")
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    if os.path.exists(f"/run/user/{uid}/wayland-0"):
        env.setdefault("WAYLAND_DISPLAY", "wayland-0")
    xauth = os.path.expanduser("~/.Xauthority")
    if os.path.exists(xauth):
        env.setdefault("XAUTHORITY", xauth)

    # 1. Try launching GUI app via python module
    try:
        cmd = [sys.executable, "-m", "idm_gui.app", "--minimized"]
        subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        for _ in range(20):
            time.sleep(0.15)
            if client.is_server_running():
                return True
    except Exception:
        pass

    # 2. Fallback to installed idm-gui binary if present
    installed_gui = os.path.expanduser("~/.local/bin/idm-gui")
    if os.path.exists(installed_gui):
        try:
            subprocess.Popen(
                [installed_gui, "--minimized"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            for _ in range(15):
                time.sleep(0.15)
                if client.is_server_running():
                    return True
        except Exception:
            pass

    # 3. Fallback to headless daemon directly
    try:
        cmd = [sys.executable, "-m", "idm_ipc.daemon"]
        subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        for _ in range(15):
            time.sleep(0.15)
            if client.is_server_running():
                return True
    except Exception:
        pass

    return False


def handle_browser_message(msg: Dict[str, Any], ipc_client: Optional[IPCClient] = None) -> Dict[str, Any]:
    """Process message received from browser extension and dispatch to IPC."""
    action = msg.get("action", "")
    if action == "ping":
        is_running = ipc_client.is_server_running() if ipc_client else False
        return {
            "status": "ok",
            "pong": True,
            "app": "IDM Linux",
            "version": idm_core.__version__,
            "engine_running": is_running
        }

    client = ipc_client or IPCClient()
    if not client.is_server_running():
        ensure_idm_running(client)

    # Forward to IDM IPC
    if action in ["open_gui", "show_gui"]:
        return client.send_request({"action": "show_gui"})
    elif action in ["add_download", "intercept", "download_video"]:
        forward_payload = dict(msg)
        if action in ["intercept", "download_video"]:
            forward_payload["action"] = "add_download"
        return client.send_request(forward_payload)
    else:
        return client.send_request(msg)


def main():
    client = IPCClient()
    while True:
        try:
            msg = read_native_message()
            if msg is None:
                break
            response = handle_browser_message(msg, client)
            send_native_message(response)
        except (KeyboardInterrupt, BrokenPipeError):
            break
        except Exception as e:
            try:
                send_native_message({"status": "error", "error": str(e)})
            except Exception:
                pass


if __name__ == "__main__":
    main()
