#!/usr/bin/env python3
"""
IDM Linux Browser Native Messaging Host (Chrome / Firefox Stdio Bridge)
"""

import json
import os
import shutil
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
    env["PYTHONPATH"] = f"{repo_root}{os.pathsep}{py_path}".strip(os.pathsep)

    popen_kwargs: Dict[str, Any] = {
        "env": env,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }

    if sys.platform == "win32":
        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags |= subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, "DETACHED_PROCESS"):
            creationflags |= subprocess.DETACHED_PROCESS
        popen_kwargs["creationflags"] = creationflags
    else:
        popen_kwargs["start_new_session"] = True
        if hasattr(os, "getuid"):
            uid = os.getuid()
            env.setdefault("DISPLAY", ":0")
            env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
            if os.path.exists(f"/run/user/{uid}/wayland-0"):
                env.setdefault("WAYLAND_DISPLAY", "wayland-0")
            xauth = os.path.expanduser("~/.Xauthority")
            if os.path.exists(xauth):
                env.setdefault("XAUTHORITY", xauth)

    is_frozen = getattr(sys, "frozen", False)
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))

    # If frozen (standalone build, e.g. PyInstaller), look for sibling binaries first
    if is_frozen:
        candidate_gui_names = (
            ["pv-idm-gui.exe", "pv-idm-gui", "idm-gui.exe", "idm-gui"]
            if sys.platform == "win32"
            else ["pv-idm-gui", "idm-gui"]
        )
        candidate_daemon_names = (
            ["pv-idm-daemon.exe", "pv-idm-daemon", "idm-daemon.exe", "idm-daemon"]
            if sys.platform == "win32"
            else ["pv-idm-daemon", "idm-daemon"]
        )

        candidate_gui_paths = [os.path.join(exe_dir, name) for name in candidate_gui_names]
        candidate_gui_paths.extend([shutil.which(name) for name in candidate_gui_names if shutil.which(name)])
        if sys.platform != "win32":
            candidate_gui_paths.append(os.path.expanduser("~/.local/bin/pv-idm-gui"))
            candidate_gui_paths.append(os.path.expanduser("~/.local/bin/idm-gui"))

        for gui_path in candidate_gui_paths:
            if gui_path and os.path.exists(gui_path):
                try:
                    subprocess.Popen([gui_path, "--minimized"], **popen_kwargs)
                    for _ in range(20):
                        time.sleep(0.15)
                        if client.is_server_running():
                            return True
                    break
                except Exception:
                    pass

        # Fallback to standalone daemon
        for daemon_name in candidate_daemon_names:
            daemon_path = os.path.join(exe_dir, daemon_name)
            if not os.path.exists(daemon_path):
                daemon_path = shutil.which(daemon_name)
            if daemon_path and os.path.exists(daemon_path):
                try:
                    subprocess.Popen([daemon_path], **popen_kwargs)
                    for _ in range(15):
                        time.sleep(0.15)
                        if client.is_server_running():
                            return True
                    break
                except Exception:
                    pass

        return False

    # 1. Try launching GUI app via python module
    try:
        cmd = [sys.executable, "-m", "idm_gui.app", "--minimized"]
        subprocess.Popen(cmd, **popen_kwargs)
        for _ in range(20):
            time.sleep(0.15)
            if client.is_server_running():
                return True
    except Exception:
        pass

    # 2. Fallback to installed gui binary if present
    candidate_gui_names = (
        ["pv-idm-gui.exe", "pv-idm-gui", "idm-gui.exe", "idm-gui"]
        if sys.platform == "win32"
        else ["pv-idm-gui", "idm-gui"]
    )
    for name in candidate_gui_names:
        candidate_gui = shutil.which(name)
        if not candidate_gui and sys.platform != "win32":
            user_path = os.path.expanduser(f"~/.local/bin/{name}")
            if os.path.exists(user_path):
                candidate_gui = user_path
        if candidate_gui and os.path.exists(candidate_gui):
            try:
                subprocess.Popen([candidate_gui, "--minimized"], **popen_kwargs)
                for _ in range(15):
                    time.sleep(0.15)
                    if client.is_server_running():
                        return True
            except Exception:
                pass

    # 3. Fallback to headless daemon directly
    try:
        cmd = [sys.executable, "-m", "idm_ipc.daemon"]
        subprocess.Popen(cmd, **popen_kwargs)
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
            "app": "PV-IDM",
            "version": idm_core.__version__,
            "engine_running": is_running
        }

    client = ipc_client or IPCClient()
    if not client.is_server_running():
        ensure_idm_running(client)

    # Forward to IDM IPC
    if action in ["open_gui", "show_gui"]:
        return client.send_request({"action": "show_gui"})
    elif action in ["add_download", "intercept", "download_video", "download", "download_url"]:
        forward_payload = dict(msg)
        if action in ["intercept", "download_video", "download", "download_url"]:
            forward_payload["action"] = "add_download"
        return client.send_request(forward_payload)
    else:
        return client.send_request(msg)


def main():
    if sys.platform == "win32":
        try:
            import msvcrt
            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        except Exception:
            pass

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
