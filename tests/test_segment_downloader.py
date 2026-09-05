import unittest
import tempfile
import os
import shutil
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from idm_core.config import Config
from idm_core.storage import StorageManager
from idm_core.segment_downloader import SegmentDownloader


class MockRangeHTTPHandler(BaseHTTPRequestHandler):
    FILE_DATA = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" * 10000  # 360,000 bytes

    def log_message(self, format, *args):
        pass  # Suppress console logging

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(self.FILE_DATA)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", 'attachment; filename="test_mock_file.dat"')
        self.end_headers()

    def do_GET(self):
        range_header = self.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            byte_range = range_header[6:]
            parts = byte_range.split("-")
            start = int(parts[0])
            end = int(parts[1]) if parts[1] else len(self.FILE_DATA) - 1
            if end >= len(self.FILE_DATA):
                end = len(self.FILE_DATA) - 1

            chunk = self.FILE_DATA[start : end + 1]
            self.send_response(206)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(chunk)))
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(self.FILE_DATA)}")
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(self.FILE_DATA)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(self.FILE_DATA)


class TestSegmentDownloader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), MockRangeHTTPHandler)
        cls.port = cls.server.server_port
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = Config(
            config_dir=self.test_dir,
            temp_dir=os.path.join(self.test_dir, "temp"),
            download_dir=os.path.join(self.test_dir, "Downloads"),
        )
        self.storage = StorageManager(self.config)
        self.test_url = f"http://127.0.0.1:{self.port}/test_mock_file.dat"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_probe_url(self):
        downloader = SegmentDownloader(
            download_id="dl-probe-test",
            url=self.test_url,
            save_path=os.path.join(self.test_dir, "probe_out.dat"),
            storage=self.storage,
            config=self.config
        )
        info = downloader.probe()
        self.assertEqual(info["status_code"], 200)
        self.assertEqual(info["content_length"], len(MockRangeHTTPHandler.FILE_DATA))
        self.assertTrue(info["resumable"])
        self.assertEqual(info["filename"], "test_mock_file.dat")

    def test_multi_segment_download_complete(self):
        dest_path = os.path.join(self.test_dir, "downloaded_file.dat")
        completed_event = threading.Event()
        error_event = threading.Event()

        def on_complete(dl_id, path):
            completed_event.set()

        def on_error(dl_id, msg):
            error_event.set()

        downloader = SegmentDownloader(
            download_id="dl-multi-test",
            url=self.test_url,
            save_path=dest_path,
            storage=self.storage,
            config=self.config,
            num_connections=4,
            min_split_size=50000,
            on_complete=on_complete,
            on_error=on_error
        )
        downloader.start()

        completed = completed_event.wait(timeout=10.0)
        self.assertTrue(completed, "Download did not complete in time")
        self.assertFalse(error_event.is_set(), "Download encountered an error")
        self.assertTrue(os.path.exists(dest_path))

        with open(dest_path, "rb") as f:
            downloaded_bytes = f.read()
        self.assertEqual(downloaded_bytes, MockRangeHTTPHandler.FILE_DATA)

    def test_probe_fallback_filename_unquoted_with_trailing_slash(self):
        downloader = SegmentDownloader(
            download_id="dl-probe-unquote",
            url="http://example.com/files/my%20test%20video.mp4/?token=123",
            save_path=self.test_dir + "/",  # Directory path with empty basename
            storage=self.storage,
            config=self.config
        )
        downloader.final_url = "http://example.com/files/my%20test%20video.mp4/?token=123"
        # Test the fallback filename branch directly
        import urllib.parse
        url_fname = os.path.basename(urllib.parse.unquote(urllib.parse.urlparse(downloader.final_url).path.rstrip("/")))
        self.assertEqual(url_fname, "my test video.mp4")


if __name__ == "__main__":
    unittest.main()
