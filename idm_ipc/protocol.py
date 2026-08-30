"""
Binary Framing Protocol for Unix Domain Socket IPC
"""

import json
import struct
from typing import Any, Dict, Optional


def encode_message(data: Dict[str, Any]) -> bytes:
    """Encode dictionary into length-prefixed binary packet."""
    json_bytes = json.dumps(data).encode("utf-8")
    header = struct.pack("!I", len(json_bytes))
    return header + json_bytes


def read_exact(sock, num_bytes: int) -> Optional[bytes]:
    """Read exactly num_bytes from socket or return None on disconnect."""
    buf = bytearray()
    while len(buf) < num_bytes:
        chunk = sock.recv(num_bytes - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def decode_message(sock) -> Optional[Dict[str, Any]]:
    """Read and decode a single length-prefixed packet from socket."""
    header = read_exact(sock, 4)
    if not header:
        return None
    length = struct.unpack("!I", header)[0]
    if length > 16 * 1024 * 1024:  # 16 MB sanity safety limit
        raise ValueError(f"Packet too large: {length} bytes")
    
    payload = read_exact(sock, length)
    if not payload:
        return None
    return json.loads(payload.decode("utf-8"))
