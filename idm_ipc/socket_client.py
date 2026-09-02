"""
Cross-Platform IPC Client for CLI, Native Messaging Host, and GUI
"""

import os
import threading
from typing import Any, Callable, Dict, Optional
from idm_ipc.protocol import decode_message, encode_message
from idm_ipc.transport import BaseClientTransport, create_client_transport


class IPCClient:
    def __init__(self, socket_path: Optional[str] = None, transport: Optional[BaseClientTransport] = None):
        self.socket_path = socket_path
        self.transport = transport or create_client_transport(socket_path)

    def is_server_running(self) -> bool:
        """Check if IDM daemon/GUI IPC is accessible."""
        if not self.transport.is_server_running():
            return False
        try:
            conn = self.transport.connect(timeout=2.0)
            conn.settimeout(2.0)
            conn.sendall(encode_message({"action": "ping"}))
            res = decode_message(conn)
            conn.close()
            return bool(res and res.get("pong"))
        except Exception:
            return False

    def send_request(self, payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
        """Send command to IPC server and wait for reply."""
        try:
            conn = self.transport.connect(timeout=timeout)
            conn.settimeout(timeout)
            conn.sendall(encode_message(payload))
            response = decode_message(conn)
            conn.close()
            return response or {"status": "error", "error": "No response from server"}
        except Exception as e:
            return {"status": "error", "error": f"IPC error: {e}"}

    def ping(self) -> Dict[str, Any]:
        return self.send_request({"action": "ping"})

    def subscribe_events(self, on_event: Callable[[Dict[str, Any]], None], stop_event: Optional[threading.Event] = None) -> threading.Thread:
        """Connect persistent subscriber socket and stream live notifications."""
        def _loop():
            conn = None
            try:
                conn = self.transport.connect(timeout=5.0)
                conn.sendall(encode_message({"action": "subscribe_events"}))
                resp = decode_message(conn)  # ack

                while stop_event is None or not stop_event.is_set():
                    msg = decode_message(conn)
                    if msg is None:
                        break
                    try:
                        on_event(msg)
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        return t
