import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
from idm_core.config import Config
from idm_core.engine import DownloadEngine
from idm_ipc.protocol import decode_message, encode_message
from idm_ipc.socket_client import IPCClient
from idm_ipc.socket_server import IPCServer
from idm_ipc.transport import (
    NamedPipeClientTransport,
    NamedPipeServerTransport,
    TCPClientTransport,
    TCPServerTransport,
    UnixSocketClientTransport,
    UnixSocketServerTransport,
    create_client_transport,
    create_server_transport,
)


class TestIPCTransport(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "Requires AF_UNIX socket support")
    def test_unix_socket_transport(self):
        sock_path = os.path.join(self.test_dir, "test_unix.sock")
        server_transport = UnixSocketServerTransport(sock_path)
        client_transport = UnixSocketClientTransport(sock_path)

        self.assertFalse(client_transport.is_server_running())
        server_transport.start()
        self.assertTrue(client_transport.is_server_running())

        # Test connection & framing
        stop_accept = threading.Event()

        def accept_worker():
            while not stop_accept.is_set():
                try:
                    conn = server_transport.accept()
                    if not conn:
                        break
                    msg = decode_message(conn)
                    if msg and msg.get("ping"):
                        conn.sendall(encode_message({"pong": True}))
                    conn.close()
                except Exception:
                    break

        t = threading.Thread(target=accept_worker, daemon=True)
        t.start()

        client_conn = client_transport.connect(timeout=2.0)
        client_conn.sendall(encode_message({"ping": True}))
        reply = decode_message(client_conn)

        self.assertIsNotNone(reply)
        self.assertTrue(reply.get("pong"))

        client_conn.close()
        stop_accept.set()
        server_transport.stop()

    def test_tcp_transport(self):
        server_transport = TCPServerTransport(host="127.0.0.1", port=0)
        server_transport.start()
        assigned_port = server_transport.port
        self.assertGreater(assigned_port, 0)

        client_transport = TCPClientTransport(host="127.0.0.1", port=assigned_port)
        self.assertTrue(client_transport.is_server_running())

        stop_accept = threading.Event()

        def accept_worker():
            while not stop_accept.is_set():
                try:
                    conn = server_transport.accept()
                    if not conn:
                        break
                    msg = decode_message(conn)
                    if msg and msg.get("hello"):
                        conn.sendall(encode_message({"world": True}))
                    conn.close()
                except Exception:
                    break

        t = threading.Thread(target=accept_worker, daemon=True)
        t.start()

        client_conn = client_transport.connect(timeout=2.0)
        client_conn.sendall(encode_message({"hello": True}))
        reply = decode_message(client_conn)

        self.assertIsNotNone(reply)
        self.assertTrue(reply.get("world"))

        client_conn.close()
        stop_accept.set()
        server_transport.stop()

    def test_transport_factories(self):
        if hasattr(socket, "AF_UNIX"):
            st_unix = create_server_transport("/tmp/test_factory.sock")
            self.assertIsInstance(st_unix, UnixSocketServerTransport)
            ct_unix = create_client_transport("/tmp/test_factory.sock")
            self.assertIsInstance(ct_unix, UnixSocketClientTransport)

        st_tcp = create_server_transport("tcp://127.0.0.1:9876")
        self.assertIsInstance(st_tcp, TCPServerTransport)
        ct_tcp = create_client_transport("tcp://127.0.0.1:9876")
        self.assertIsInstance(ct_tcp, TCPClientTransport)

        from unittest.mock import patch
        with patch("idm_ipc.transport.is_windows", return_value=True):
            st_pipe = create_server_transport(r"\\.\pipe\idm_ipc_socket")
            self.assertIsInstance(st_pipe, NamedPipeServerTransport)
            ct_pipe = create_client_transport(r"\\.\pipe\idm_ipc_socket")
            self.assertIsInstance(ct_pipe, NamedPipeClientTransport)

            st_pipe_def = create_server_transport()
            self.assertIsInstance(st_pipe_def, NamedPipeServerTransport)
            ct_pipe_def = create_client_transport()
            self.assertIsInstance(ct_pipe_def, NamedPipeClientTransport)

    def test_named_pipe_not_running(self):
        ct_pipe = NamedPipeClientTransport(r"\\.\pipe\nonexistent_pipe_12345")
        self.assertFalse(ct_pipe.is_server_running())
        with self.assertRaises(ConnectionRefusedError):
            ct_pipe.connect(timeout=0.1)

    def test_ipc_server_and_client_over_tcp_transport(self):
        server_transport = TCPServerTransport(host="127.0.0.1", port=0)
        config = Config(
            config_dir=self.test_dir,
            database_path=os.path.join(self.test_dir, "tcp_test.db"),
            temp_dir=os.path.join(self.test_dir, "temp"),
            download_dir=os.path.join(self.test_dir, "Downloads"),
        )
        engine = DownloadEngine(config)
        server = IPCServer(engine, transport=server_transport)
        server.start()

        port = server_transport.port
        client_transport = TCPClientTransport(host="127.0.0.1", port=port)
        client = IPCClient(transport=client_transport)
        self.assertTrue(client.is_server_running())

        pong = client.ping()
        self.assertTrue(pong.get("pong"))

        server.stop()
        engine.shutdown()

    @unittest.skipUnless(sys.platform == "win32", "Requires Windows Named Pipe support")
    def test_named_pipe_server_and_client_roundtrip(self):
        pipe_name = rf"\\.\pipe\idm_test_roundtrip_{os.getpid()}"
        server_transport = NamedPipeServerTransport(pipe_name)
        client_transport = NamedPipeClientTransport(pipe_name)

        server_transport.start()

        stop_accept = threading.Event()

        def accept_worker():
            while not stop_accept.is_set():
                try:
                    conn = server_transport.accept()
                    if not conn:
                        break
                    msg = decode_message(conn)
                    if msg and msg.get("ping"):
                        conn.sendall(encode_message({"pong": True}))
                    conn.close()
                except Exception:
                    break

        t = threading.Thread(target=accept_worker, daemon=True)
        t.start()

        running = False
        for _ in range(50):
            if client_transport.is_server_running():
                running = True
                break
            time.sleep(0.05)
        self.assertTrue(running)

        client_conn = client_transport.connect(timeout=3.0)
        client_conn.sendall(encode_message({"ping": True}))
        reply = decode_message(client_conn)

        self.assertIsNotNone(reply)
        self.assertTrue(reply.get("pong"))

        client_conn.close()
        stop_accept.set()
        server_transport.stop()
        t.join(timeout=2.0)


if __name__ == "__main__":
    unittest.main()
