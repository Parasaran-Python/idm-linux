import unittest
import tempfile
import os
import shutil
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from idm_core.config import Config
from idm_core.storage import StorageManager
from idm_core.stream_downloader import StreamDownloader, HLSParser


class MockStreamHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


class TestStreamDownloader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_dir = tempfile.mkdtemp()
        
        # Create mock .ts chunks
        cls.ts1 = b"MOCK_TS_PACKET_HEADER_1" * 100
        cls.ts2 = b"MOCK_TS_PACKET_HEADER_2" * 100
        cls.ts3 = b"MOCK_TS_PACKET_HEADER_3" * 100

        with open(os.path.join(cls.server_dir, "seg1.ts"), "wb") as f:
            f.write(cls.ts1)
        with open(os.path.join(cls.server_dir, "seg2.ts"), "wb") as f:
            f.write(cls.ts2)
        with open(os.path.join(cls.server_dir, "seg3.ts"), "wb") as f:
            f.write(cls.ts3)

        # Create mock playlist.m3u8
        m3u8_content = (
            "#EXTM3U\n"
            "#EXT-X-VERSION:3\n"
            "#EXT-X-TARGETDURATION:10\n"
            "#EXTINF:10.0,\n"
            "seg1.ts\n"
            "#EXTINF:10.0,\n"
            "seg2.ts\n"
            "#EXTINF:10.0,\n"
            "seg3.ts\n"
            "#EXT-X-ENDLIST\n"
        )
        with open(os.path.join(cls.server_dir, "playlist.m3u8"), "w") as f:
            f.write(m3u8_content)

        class Handler(MockStreamHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=cls.server_dir, **kwargs)

        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.server_dir)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = Config(
            config_dir=self.test_dir,
            temp_dir=os.path.join(self.test_dir, "temp"),
            download_dir=os.path.join(self.test_dir, "Downloads"),
        )
        self.storage = StorageManager(self.config)
        self.m3u8_url = f"http://127.0.0.1:{self.port}/playlist.m3u8"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_hls_parser(self):
        parser = HLSParser(self.m3u8_url)
        segments = parser.parse()
        self.assertEqual(len(segments), 3)
        self.assertTrue(segments[0].endswith("seg1.ts"))
        self.assertTrue(segments[1].endswith("seg2.ts"))
        self.assertTrue(segments[2].endswith("seg3.ts"))

    def test_probe_stream_info(self):
        info = HLSParser.probe_stream_info(self.m3u8_url)
        self.assertEqual(info["duration"], 30.0)
        self.assertTrue(info["filesize"] > 0)

    def test_stream_downloader_download(self):
        dest_path = os.path.join(self.test_dir, "Downloads", "video.ts")
        completed_event = threading.Event()

        def on_complete(dl_id, path):
            completed_event.set()

        downloader = StreamDownloader(
            download_id="dl-stream-test",
            url=self.m3u8_url,
            save_path=dest_path,
            storage=self.storage,
            config=self.config,
            on_complete=on_complete
        )
        downloader.start()

        completed = completed_event.wait(timeout=10.0)
        self.assertTrue(completed)
        self.assertTrue(os.path.exists(dest_path))
        with open(dest_path, "rb") as f:
            data = f.read()
        self.assertEqual(data, self.ts1 + self.ts2 + self.ts3)


if __name__ == "__main__":
    unittest.main()
