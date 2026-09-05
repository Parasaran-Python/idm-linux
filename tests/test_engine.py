import unittest
import tempfile
import os
import shutil
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from idm_core.config import Config
from idm_core.engine import DownloadEngine


class MockDownloadServer(BaseHTTPRequestHandler):
    TEST_DATA = b"IDM Linux Full Engine Integration Test Content 1234567890" * 100

    def log_message(self, format, *args):
        pass

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(self.TEST_DATA)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", 'attachment; filename="package.zip"')
        self.end_headers()

    def do_GET(self):
        range_header = self.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            byte_range = range_header[6:]
            parts = byte_range.split("-")
            start = int(parts[0])
            end = int(parts[1]) if parts[1] else len(self.TEST_DATA) - 1
            if end >= len(self.TEST_DATA):
                end = len(self.TEST_DATA) - 1
            chunk = self.TEST_DATA[start : end + 1]
            self.send_response(206)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(chunk)))
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(self.TEST_DATA)}")
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(self.TEST_DATA)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(self.TEST_DATA)


class TestDownloadEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), MockDownloadServer)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = Config(
            config_dir=self.test_dir,
            database_path=os.path.join(self.test_dir, "engine_test.db"),
            temp_dir=os.path.join(self.test_dir, "temp"),
            download_dir=os.path.join(self.test_dir, "Downloads"),
        )
        self.engine = DownloadEngine(self.config)
        self.test_url = f"http://127.0.0.1:{self.port}/package.zip"

    def tearDown(self):
        self.engine.shutdown()
        shutil.rmtree(self.test_dir)

    def test_add_and_download_flow(self):
        completed_event = threading.Event()

        def on_complete(event_data):
            if event_data.get("download_id") == dl_id:
                completed_event.set()

        self.engine.register_listener("download_complete", on_complete)

        dl_id = self.engine.add_download(
            url=self.test_url,
            start_immediately=True
        )
        self.assertIsNotNone(dl_id)
        
        info = self.engine.get_download_info(dl_id)
        self.assertEqual(info["category"], "Compressed")
        self.assertEqual(info["filename"], "package.zip")

        completed = completed_event.wait(timeout=10.0)
        self.assertTrue(completed)

        final_info = self.engine.get_download_info(dl_id)
        self.assertEqual(final_info["status"], "completed")
        self.assertTrue(os.path.exists(final_info["save_path"]))

        with open(final_info["save_path"], "rb") as f:
            data = f.read()
        self.assertEqual(data, MockDownloadServer.TEST_DATA)

    def test_queue_concurrency(self):
        q_id = self.engine.database.create_queue("TestQueue", max_concurrent=1)
        dl1 = self.engine.add_download(self.test_url, queue_id=q_id, start_immediately=False)
        dl2 = self.engine.add_download(self.test_url, queue_id=q_id, start_immediately=False)

        self.engine.start_queue(q_id)
        # Check that queue is active
        queue_state = self.engine.queue_manager.get_queue_state(q_id)
        self.assertTrue(queue_state["is_active"])
        self.engine.stop_queue(q_id)

    def test_direct_mp4_download_routes_to_segment_downloader_even_with_quality(self):
        from idm_core.segment_downloader import SegmentDownloader
        from idm_core.ytdlp_downloader import YTDLPDownloader

        mp4_url = f"http://127.0.0.1:{self.port}/get_file/video_720p.mp4/?token=abc"
        dl_id = self.engine.add_download(
            url=mp4_url,
            headers={"quality": "best"},
            start_immediately=False
        )

        with unittest.mock.patch.object(YTDLPDownloader, "is_ytdlp_available", return_value=True):
            self.engine.start_download(dl_id)
            active = self.engine.active_downloaders.get(dl_id)
            self.assertIsInstance(active, SegmentDownloader)
            self.assertNotIsInstance(active, YTDLPDownloader)

    def test_ytdlp_downloader_fallback_to_segment_downloader(self):
        from idm_core.segment_downloader import SegmentDownloader
        from idm_core.ytdlp_downloader import YTDLPDownloader

        url = f"http://127.0.0.1:{self.port}/package.zip"
        dl_id = self.engine.add_download(url=url, start_immediately=False)

        fake_ytdlp = YTDLPDownloader(dl_id, url, os.path.join(self.test_dir, "pkg.zip"))
        self.engine.active_downloaders[dl_id] = fake_ytdlp

        self.engine._on_error_callback(dl_id, "ERROR: The extracted extension ('php') is unusual")

        active = self.engine.active_downloaders.get(dl_id)
        self.assertIsInstance(active, SegmentDownloader)

    def test_ytdlp_downloader_fallback_does_not_revive_paused_download(self):
        from idm_core.ytdlp_downloader import YTDLPDownloader

        url = f"http://127.0.0.1:{self.port}/package.zip"
        dl_id = self.engine.add_download(url=url, start_immediately=False)

        fake_ytdlp = YTDLPDownloader(dl_id, url, os.path.join(self.test_dir, "pkg.zip"))
        self.engine.active_downloaders[dl_id] = fake_ytdlp

        # Simulate user pausing before error callback runs
        self.engine.database.update_download(dl_id, status="paused")

        self.engine._on_error_callback(dl_id, "ERROR: connection closed")

        # Must not have revived the download in active_downloaders
        active = self.engine.active_downloaders.get(dl_id)
        self.assertIsNone(active)

    def test_start_download_with_null_headers(self):
        from idm_core.segment_downloader import SegmentDownloader

        url = f"http://127.0.0.1:{self.port}/package.zip"
        dl_id = self.engine.add_download(url=url, start_immediately=False)

        # Manually set headers to None in record
        with unittest.mock.patch.object(self.engine.database, "get_download") as mock_get:
            mock_get.return_value = {
                "id": dl_id,
                "url": url,
                "save_path": os.path.join(self.test_dir, "pkg.zip"),
                "headers": None,
                "connections_count": 4,
                "total_bytes": 0,
            }
            # Should not raise AttributeError: 'NoneType' object has no attribute 'get'
            self.engine.start_download(dl_id)
            active = self.engine.active_downloaders.get(dl_id)
            self.assertIsInstance(active, SegmentDownloader)

    def test_ytdlp_downloader_fallback_handles_start_exception(self):
        from idm_core.segment_downloader import SegmentDownloader
        from idm_core.ytdlp_downloader import YTDLPDownloader

        url = f"http://127.0.0.1:{self.port}/package.zip"
        dl_id = self.engine.add_download(url=url, start_immediately=False)

        fake_ytdlp = YTDLPDownloader(dl_id, url, os.path.join(self.test_dir, "pkg.zip"))
        self.engine.active_downloaders[dl_id] = fake_ytdlp

        with unittest.mock.patch.object(SegmentDownloader, "start", side_effect=RuntimeError("Spawn failed")):
            self.engine._on_error_callback(dl_id, "YTDLP failed")

        active = self.engine.active_downloaders.get(dl_id)
        self.assertIsNone(active)
        rec = self.engine.database.get_download(dl_id)
        self.assertEqual(rec["status"], "error")
        self.assertIn("Spawn failed", rec["error_msg"])


if __name__ == "__main__":
    unittest.main()

