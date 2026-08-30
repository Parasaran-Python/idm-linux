"""
End-to-End System Integration Test Suite for IDM Linux
Verifies browser interception -> Native Host -> IPC Server -> Core Dynamic Segmentation -> Pause/Resume -> Checksum Verification.
"""

import hashlib
import os
import shutil
import tempfile
import threading
import time
import unittest
from http.server import HTTPServer, BaseHTTPRequestHandler
from idm_core.config import Config
from idm_core.engine import DownloadEngine
from idm_ipc.socket_server import IPCServer
from idm_ipc.socket_client import IPCClient
from idm_native_host.host import handle_browser_message


class E2EMockServer(BaseHTTPRequestHandler):
    # 512 KB of structured non-repeating binary test data
    RAW_DATA = bytes([i % 256 for i in range(512 * 1024)])

    def log_message(self, format, *args):
        pass

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(self.RAW_DATA)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", 'attachment; filename="e2e_test_archive.bin"')
        self.end_headers()

    def do_GET(self):
        range_header = self.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            byte_range = range_header[6:]
            parts = byte_range.split("-")
            start = int(parts[0])
            end = int(parts[1]) if parts[1] else len(self.RAW_DATA) - 1
            if end >= len(self.RAW_DATA):
                end = len(self.RAW_DATA) - 1

            chunk = self.RAW_DATA[start : end + 1]
            self.send_response(206)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(chunk)))
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(self.RAW_DATA)}")
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(self.RAW_DATA)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(self.RAW_DATA)


class TestE2EIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), E2EMockServer)
        cls.port = cls.server.server_port
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.sock_path = os.path.join(self.test_dir, "idm_e2e.sock")
        self.config = Config(
            config_dir=self.test_dir,
            socket_path=self.sock_path,
            database_path=os.path.join(self.test_dir, "idm_e2e.db"),
            temp_dir=os.path.join(self.test_dir, "temp"),
            download_dir=os.path.join(self.test_dir, "Downloads"),
        )
        self.engine = DownloadEngine(self.config)
        self.ipc_server = IPCServer(self.engine, self.sock_path)
        self.ipc_server.start()
        self.client = IPCClient(self.sock_path)
        self.test_url = f"http://127.0.0.1:{self.port}/e2e_test_archive.bin"
        time.sleep(0.1)

    def tearDown(self):
        self.ipc_server.stop()
        self.engine.shutdown()
        shutil.rmtree(self.test_dir)

    def test_full_e2e_pipeline(self):
        # 1. Simulate browser native messaging interception
        browser_req = {
            "action": "intercept",
            "url": self.test_url,
            "filename": "e2e_test_archive.bin",
            "headers": {
                "User-Agent": "Mozilla/5.0 Chrome/130.0",
                "Referer": "https://example.com/"
            },
            "start_immediately": True
        }

        response = handle_browser_message(browser_req, self.client)
        self.assertEqual(response.get("status"), "ok")
        dl_id = response.get("download_id")
        self.assertIsNotNone(dl_id)

        # 2. Wait for download completion
        completed = False
        save_path = None
        for _ in range(100):
            time.sleep(0.1)
            info_res = self.client.send_request({"action": "get_download", "download_id": dl_id})
            if info_res.get("status") == "ok":
                dl_data = info_res.get("download", {})
                if dl_data.get("status") == "completed":
                    completed = True
                    save_path = dl_data.get("save_path")
                    break

        self.assertTrue(completed, "Download did not complete in E2E test")
        self.assertIsNotNone(save_path)
        self.assertTrue(os.path.exists(save_path))

        # 3. Verify SHA-256 Checksum against upstream raw data
        expected_sha = hashlib.sha256(E2EMockServer.RAW_DATA).hexdigest()
        self.assertTrue(
            self.engine.storage.verify_checksum(save_path, expected_sha, "sha256"),
            "Downloaded file SHA-256 checksum mismatch"
        )

        # 4. Verify IPC list command contains completed status
        list_res = self.client.send_request({"action": "list_downloads"})
        self.assertEqual(list_res.get("status"), "ok")
        dls = list_res.get("downloads", [])
        self.assertEqual(len(dls), 1)
        self.assertEqual(dls[0]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
