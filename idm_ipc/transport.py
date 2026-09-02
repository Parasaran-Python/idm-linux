"""
Cross-Platform IPC Transport Layer
Provides abstract transport interfaces and implementations for:
- Unix Domain Sockets (Linux / macOS / Windows 10+ Winsock)
- Windows Named Pipes (\\.\\pipe\\idm_ipc_socket via ctypes win32 API)
- Localhost TCP Sockets (cross-platform loopback fallback)
"""

import abc
import os
import re
import socket
import sys
import threading
import time
from typing import Optional, Tuple
from idm_core.platform import get_default_ipc_endpoint, is_windows


class BaseConnection(abc.ABC):
    """Abstract byte-stream connection interface (compatible with socket-like recv/sendall/close)."""

    @abc.abstractmethod
    def recv(self, bufsize: int) -> bytes:
        """Receive up to bufsize bytes. Returns empty bytes on EOF/disconnect."""
        pass

    @abc.abstractmethod
    def sendall(self, data: bytes):
        """Send all bytes in buffer."""
        pass

    @abc.abstractmethod
    def close(self):
        """Close connection."""
        pass

    @abc.abstractmethod
    def settimeout(self, timeout: Optional[float]):
        """Set timeout in seconds for blocking socket operations."""
        pass


class SocketConnection(BaseConnection):
    """Connection wrapper around a standard Python socket."""

    def __init__(self, sock: socket.socket):
        self._sock = sock

    def recv(self, bufsize: int) -> bytes:
        try:
            return self._sock.recv(bufsize)
        except (socket.timeout, TimeoutError):
            raise
        except Exception:
            return b""

    def sendall(self, data: bytes):
        self._sock.sendall(data)

    def close(self):
        try:
            self._sock.close()
        except Exception:
            pass

    def settimeout(self, timeout: Optional[float]):
        self._sock.settimeout(timeout)


class BaseServerTransport(abc.ABC):
    """Abstract server transport interface."""

    @abc.abstractmethod
    def start(self):
        """Bind and start listening."""
        pass

    @abc.abstractmethod
    def accept(self) -> Optional[BaseConnection]:
        """Accept an incoming client connection. Returns None if server stopped."""
        pass

    @abc.abstractmethod
    def stop(self):
        """Close server and perform cleanup."""
        pass


class BaseClientTransport(abc.ABC):
    """Abstract client transport interface."""

    @abc.abstractmethod
    def connect(self, timeout: float = 10.0) -> BaseConnection:
        """Connect to the server transport. Raises ConnectionError on failure."""
        pass

    @abc.abstractmethod
    def is_server_running(self) -> bool:
        """Check if server transport is listening and accessible."""
        pass


# =====================================================================
# 1. Unix Domain Socket Transport (Linux / macOS / Windows Winsock)
# =====================================================================

class UnixSocketServerTransport(BaseServerTransport):
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self._server_sock: Optional[socket.socket] = None
        self._running = False

    def start(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.socket_path)), exist_ok=True)
        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
            except Exception:
                pass

        self._running = True
        self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_sock.bind(self.socket_path)
        self._server_sock.listen(16)

    def accept(self) -> Optional[BaseConnection]:
        if not self._server_sock or not self._running:
            return None
        try:
            client_sock, _ = self._server_sock.accept()
            return SocketConnection(client_sock)
        except Exception:
            return None

    def stop(self):
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
            except Exception:
                pass


class UnixSocketClientTransport(BaseClientTransport):
    def __init__(self, socket_path: str):
        self.socket_path = socket_path

    def connect(self, timeout: float = 10.0) -> BaseConnection:
        if not os.path.exists(self.socket_path):
            raise ConnectionRefusedError(f"Socket file not found: {self.socket_path}")
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(self.socket_path)
        return SocketConnection(s)

    def is_server_running(self) -> bool:
        if not os.path.exists(self.socket_path):
            return False
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(1.5)
                s.connect(self.socket_path)
                return True
        except Exception:
            return False


# =====================================================================
# 2. Localhost TCP Transport (Universal Fallback)
# =====================================================================

class TCPServerTransport(BaseServerTransport):
    def __init__(self, host: str = "127.0.0.1", port: int = 0, port_file: Optional[str] = None):
        self.host = host
        self.port = port
        self.port_file = port_file
        self._server_sock: Optional[socket.socket] = None
        self._running = False

    def start(self):
        self._running = True
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self.port = self._server_sock.getsockname()[1]
        self._server_sock.listen(16)

        if self.port_file:
            os.makedirs(os.path.dirname(os.path.abspath(self.port_file)), exist_ok=True)
            with open(self.port_file, "w", encoding="utf-8") as f:
                f.write(f"{self.host}:{self.port}")

    def accept(self) -> Optional[BaseConnection]:
        if not self._server_sock or not self._running:
            return None
        try:
            client_sock, _ = self._server_sock.accept()
            return SocketConnection(client_sock)
        except Exception:
            return None

    def stop(self):
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

        if self.port_file and os.path.exists(self.port_file):
            try:
                os.remove(self.port_file)
            except Exception:
                pass


class TCPClientTransport(BaseClientTransport):
    def __init__(self, host: str = "127.0.0.1", port: int = 0, port_file: Optional[str] = None):
        self.host = host
        self.port = port
        self.port_file = port_file

    def _resolve_target(self) -> Tuple[str, int]:
        if self.port > 0:
            return self.host, self.port
        if self.port_file and os.path.exists(self.port_file):
            try:
                with open(self.port_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                h, p = content.split(":")
                return h, int(p)
            except Exception:
                pass
        raise ConnectionRefusedError("Could not resolve TCP port or port file")

    def connect(self, timeout: float = 10.0) -> BaseConnection:
        h, p = self._resolve_target()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((h, p))
        return SocketConnection(s)

    def is_server_running(self) -> bool:
        try:
            h, p = self._resolve_target()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.5)
                s.connect((h, p))
                return True
        except Exception:
            return False


# =====================================================================
# 3. Windows Named Pipe Transport (via ctypes Win32 API)
# =====================================================================

_win32_initialized = False


def _setup_win32_named_pipes():
    global _win32_initialized
    if _win32_initialized or not is_windows():
        return
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32

        k32.CreateNamedPipeW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID
        ]
        k32.CreateNamedPipeW.restype = wintypes.HANDLE

        k32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
        k32.ConnectNamedPipe.restype = wintypes.BOOL

        k32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
        k32.WaitNamedPipeW.restype = wintypes.BOOL

        k32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
        ]
        k32.CreateFileW.restype = wintypes.HANDLE

        k32.ReadFile.argtypes = [
            wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID
        ]
        k32.ReadFile.restype = wintypes.BOOL

        k32.WriteFile.argtypes = [
            wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID
        ]
        k32.WriteFile.restype = wintypes.BOOL

        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        k32.CloseHandle.restype = wintypes.BOOL

        k32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
        k32.DisconnectNamedPipe.restype = wintypes.BOOL

        _win32_initialized = True
    except Exception:
        pass


def _is_invalid_handle(handle) -> bool:
    if handle is None or handle == 0:
        return True
    try:
        import ctypes
        val = ctypes.c_void_p(handle).value
        return val is None or val in (-1, 0xFFFFFFFFFFFFFFFF, 0xFFFFFFFF)
    except Exception:
        return handle in (-1, 0)


def get_windows_pipe_name(endpoint_or_path: str) -> str:
    if endpoint_or_path.startswith(r"\\.\pipe"):
        return endpoint_or_path
    base = os.path.basename(endpoint_or_path) or "idm_ipc_socket"
    safe = re.sub(r'[^a-zA-Z0-9_-]', '_', base)
    return rf"\\.\pipe\idm_{safe}"


class NamedPipeConnection(BaseConnection):
    def __init__(self, handle, is_server: bool = False):
        self.handle = handle
        self.is_server = is_server
        self._timeout: Optional[float] = None
        self._closed = False
        self._lock = threading.Lock()

    def recv(self, bufsize: int) -> bytes:
        if self._closed or _is_invalid_handle(self.handle):
            return b""
        try:
            import ctypes
            from ctypes import wintypes

            buf = ctypes.create_string_buffer(bufsize)
            bytes_read = wintypes.DWORD(0)

            ret = ctypes.windll.kernel32.ReadFile(
                self.handle,
                buf,
                bufsize,
                ctypes.byref(bytes_read),
                None
            )
            if ret and bytes_read.value > 0:
                return bytes(buf.raw[:bytes_read.value])
            return b""
        except Exception:
            return b""

    def sendall(self, data: bytes):
        if self._closed or _is_invalid_handle(self.handle):
            raise ConnectionResetError("Named pipe is closed")
        try:
            import ctypes
            from ctypes import wintypes

            total = len(data)
            written = 0
            while written < total:
                chunk = data[written:written + 65536]
                bytes_written = wintypes.DWORD(0)
                ret = ctypes.windll.kernel32.WriteFile(
                    self.handle,
                    chunk,
                    len(chunk),
                    ctypes.byref(bytes_written),
                    None
                )
                if not ret or bytes_written.value == 0:
                    raise ConnectionResetError("WriteFile failed on Named Pipe")
                written += bytes_written.value
            ctypes.windll.kernel32.FlushFileBuffers(self.handle)
        except Exception as e:
            raise ConnectionResetError(f"Named Pipe send failed: {e}")

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if not _is_invalid_handle(self.handle):
                try:
                    import ctypes
                    if self.is_server:
                        ctypes.windll.kernel32.DisconnectNamedPipe(self.handle)
                    ctypes.windll.kernel32.CloseHandle(self.handle)
                except Exception:
                    pass
                self.handle = None

    def settimeout(self, timeout: Optional[float]):
        self._timeout = timeout


class NamedPipeServerTransport(BaseServerTransport):
    def __init__(self, pipe_name: str = r"\\.\pipe\idm_ipc_socket"):
        self.pipe_name = pipe_name
        self._running = False
        self._lock = threading.Lock()

    def start(self):
        self._running = True

    def accept(self) -> Optional[BaseConnection]:
        if not self._running:
            return None

        h_pipe = None
        try:
            import ctypes
            from ctypes import wintypes
            _setup_win32_named_pipes()

            # Win32 Named Pipe Constants
            PIPE_ACCESS_DUPLEX = 0x00000003
            PIPE_TYPE_BYTE = 0x00000000
            PIPE_READMODE_BYTE = 0x00000000
            PIPE_WAIT = 0x00000000
            PIPE_UNLIMITED_INSTANCES = 255
            BUF_SIZE = 65536

            h_pipe = ctypes.windll.kernel32.CreateNamedPipeW(
                self.pipe_name,
                PIPE_ACCESS_DUPLEX,
                PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
                PIPE_UNLIMITED_INSTANCES,
                BUF_SIZE,
                BUF_SIZE,
                0,
                None
            )

            if _is_invalid_handle(h_pipe):
                return None

            # ConnectNamedPipe returns TRUE or FALSE with ERROR_PIPE_CONNECTED
            connected = ctypes.windll.kernel32.ConnectNamedPipe(h_pipe, None)
            if not self._running:
                ctypes.windll.kernel32.CloseHandle(h_pipe)
                return None

            if not connected:
                err = ctypes.windll.kernel32.GetLastError()
                ERROR_PIPE_CONNECTED = 535
                ERROR_NO_DATA = 232  # Client closed pipe before data was sent
                if err == ERROR_NO_DATA:
                    try:
                        ctypes.windll.kernel32.DisconnectNamedPipe(h_pipe)
                    except Exception:
                        pass
                    ctypes.windll.kernel32.CloseHandle(h_pipe)
                    return None
                elif err != ERROR_PIPE_CONNECTED:
                    ctypes.windll.kernel32.CloseHandle(h_pipe)
                    return None

            return NamedPipeConnection(h_pipe, is_server=True)
        except Exception:
            if h_pipe and not _is_invalid_handle(h_pipe):
                try:
                    ctypes.windll.kernel32.CloseHandle(h_pipe)
                except Exception:
                    pass
            return None

    def stop(self):
        self._running = False
        # Unblock pending ConnectNamedPipe so accept() thread can exit
        try:
            import ctypes
            _setup_win32_named_pipes()
            if ctypes.windll.kernel32.WaitNamedPipeW(self.pipe_name, 50):
                h = ctypes.windll.kernel32.CreateFileW(
                    self.pipe_name, 0, 0, None, 3, 0, None
                )
                if not _is_invalid_handle(h):
                    ctypes.windll.kernel32.CloseHandle(h)
        except Exception:
            pass


class NamedPipeClientTransport(BaseClientTransport):
    def __init__(self, pipe_name: str = r"\\.\pipe\idm_ipc_socket"):
        self.pipe_name = pipe_name

    def connect(self, timeout: float = 10.0) -> BaseConnection:
        try:
            import ctypes
            from ctypes import wintypes
            _setup_win32_named_pipes()

            GENERIC_READ = 0x80000000
            GENERIC_WRITE = 0x40000000
            OPEN_EXISTING = 3

            # Wait for pipe if busy
            timeout_ms = max(50, int(timeout * 1000))
            ctypes.windll.kernel32.WaitNamedPipeW(self.pipe_name, timeout_ms)

            h_pipe = ctypes.windll.kernel32.CreateFileW(
                self.pipe_name,
                GENERIC_READ | GENERIC_WRITE,
                0,
                None,
                OPEN_EXISTING,
                0,
                None
            )

            if _is_invalid_handle(h_pipe):
                raise ConnectionRefusedError(f"Could not open named pipe: {self.pipe_name}")

            return NamedPipeConnection(h_pipe, is_server=False)
        except Exception as e:
            raise ConnectionRefusedError(f"Failed to connect to Named Pipe {self.pipe_name}: {e}")

    def is_server_running(self) -> bool:
        try:
            import ctypes
            _setup_win32_named_pipes()
            res = ctypes.windll.kernel32.WaitNamedPipeW(self.pipe_name, 100)
            if res:
                return True
            err = ctypes.windll.kernel32.GetLastError()
            ERROR_PIPE_BUSY = 231
            ERROR_ALREADY_EXISTS = 183
            if err in (ERROR_PIPE_BUSY, ERROR_ALREADY_EXISTS):
                return True
            return False
        except Exception:
            return False


# =====================================================================
# Factory Functions
# =====================================================================

def create_server_transport(endpoint: Optional[str] = None, config_dir: Optional[str] = None) -> BaseServerTransport:
    """Create optimal server transport based on endpoint or operating system."""
    ep = endpoint or get_default_ipc_endpoint(config_dir)

    if ep.startswith(r"\\.\pipe"):
        if is_windows():
            return NamedPipeServerTransport(ep)
        # Fallback for non-windows mock/tests
        return TCPServerTransport()

    if ep.startswith("tcp://"):
        parts = ep[6:].split(":")
        h = parts[0] or "127.0.0.1"
        p = int(parts[1]) if len(parts) > 1 else 0
        return TCPServerTransport(host=h, port=p)

    if is_windows():
        return NamedPipeServerTransport(get_windows_pipe_name(ep))

    return UnixSocketServerTransport(ep)


def create_client_transport(endpoint: Optional[str] = None, config_dir: Optional[str] = None) -> BaseClientTransport:
    """Create optimal client transport based on endpoint or operating system."""
    ep = endpoint or get_default_ipc_endpoint(config_dir)

    if ep.startswith(r"\\.\pipe"):
        if is_windows():
            return NamedPipeClientTransport(ep)
        return TCPClientTransport()

    if ep.startswith("tcp://"):
        parts = ep[6:].split(":")
        h = parts[0] or "127.0.0.1"
        p = int(parts[1]) if len(parts) > 1 else 0
        return TCPClientTransport(host=h, port=p)

    if is_windows():
        return NamedPipeClientTransport(get_windows_pipe_name(ep))

    return UnixSocketClientTransport(ep)
