"""
Unix Domain Socket IPC Client for CLI, Native Messaging Host, and GUI
"""

import os
import socket
import threading
from typing import Any, Callable, Dict, Optional
from idm_ipc.protocol import decode_message, encode_message


class IPCClient:
    def __init__(self, socket_path: Optional[str] = None):
        self.socket_path = socket_path or os.path.expanduser("~/.config/idm-linux/idm.sock")

    def is_server_running(self) -> bool:
        """Check if IDM daemon/GUI IPC socket is accessible."""
        if not os.path.exists(self.socket_path):
            return False
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect(self.socket_path)
                s.sendall(encode_message({"action": "ping"}))
                res = decode_message(s)
                return bool(res and res.get("pong"))
        except Exception:
            return False

    def send_request(self, payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
        """Send command to IPC server and wait for reply."""
        if not os.path.exists(self.socket_path):
            return {"status": "error", "error": "IDM daemon is not running"}

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect(self.socket_path)
                s.sendall(encode_message(payload))
                response = decode_message(s)
                return response or {"status": "error", "error": "No response from server"}
        except Exception as e:
            return {"status": "error", "error": f"IPC error: {e}"}

    def ping(self) -> Dict[str, Any]:
        return self.send_request({"action": "ping"})

    def subscribe_events(self, on_event: Callable[[Dict[str, Any]], None], stop_event: Optional[threading.Event] = None) -> threading.Thread:
        """Connect persistent subscriber socket and stream live notifications."""
        def _loop():
            s = None
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(self.socket_path)
                s.sendall(encode_message({"action": "subscribe_events"}))
                resp = decode_message(s)  # ack

                while stop_event is None or not stop_event.is_set():
                    msg = decode_message(s)
                    if msg is None:
                        break
                    try:
                        on_event(msg)
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                if s:
                    try:
                        s.close()
                    except Exception:
                        pass

        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        return t
