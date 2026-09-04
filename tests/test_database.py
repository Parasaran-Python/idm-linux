import unittest
import tempfile
import os
import shutil
from idm_core.config import Config
from idm_core.database import Database


class TestConfigAndDatabase(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_idm.db")
        self.config = Config(
            config_dir=self.test_dir,
            database_path=self.db_path,
            download_dir=os.path.join(self.test_dir, "Downloads"),
            temp_dir=os.path.join(self.test_dir, "temp"),
        )
        self.db = Database(self.db_path)
        self.db.init_db()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)

    def test_add_and_get_download(self):
        download_id = self.db.add_download(
            url="https://example.com/archive.zip",
            filename="archive.zip",
            save_path=os.path.join(self.test_dir, "archive.zip"),
            total_bytes=1048576,
            category="Compressed",
            connections_count=8,
            headers={"User-Agent": "PV-IDM/1.0"},
        )
        self.assertTrue(download_id.startswith("dl-"))

        dl = self.db.get_download(download_id)
        self.assertIsNotNone(dl)
        self.assertEqual(dl["url"], "https://example.com/archive.zip")
        self.assertEqual(dl["filename"], "archive.zip")
        self.assertEqual(dl["total_bytes"], 1048576)
        self.assertEqual(dl["status"], "queued")
        self.assertEqual(dl["category"], "Compressed")
        self.assertEqual(dl["connections_count"], 8)
        self.assertEqual(dl["headers"]["User-Agent"], "PV-IDM/1.0")

    def test_update_download(self):
        download_id = self.db.add_download(
            url="https://example.com/video.mp4",
            filename="video.mp4",
            save_path=os.path.join(self.test_dir, "video.mp4"),
            total_bytes=5000000,
            category="Video",
        )
        self.db.update_download(
            download_id,
            status="downloading",
            downloaded_bytes=2500000,
            speed=1250000,
        )
        dl = self.db.get_download(download_id)
        self.assertEqual(dl["status"], "downloading")
        self.assertEqual(dl["downloaded_bytes"], 2500000)
        self.assertEqual(dl["speed"], 1250000)

    def test_list_downloads_filters(self):
        dl1 = self.db.add_download("https://ex.com/1.zip", "1.zip", "/path/1.zip", category="Compressed")
        dl2 = self.db.add_download("https://ex.com/2.mp4", "2.mp4", "/path/2.mp4", category="Video")
        self.db.update_download(dl2, status="completed")

        all_dls = self.db.list_downloads()
        self.assertEqual(len(all_dls), 2)

        compressed = self.db.list_downloads(category="Compressed")
        self.assertEqual(len(compressed), 1)
        self.assertEqual(compressed[0]["id"], dl1)

        completed = self.db.list_downloads(status="completed")
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]["id"], dl2)

    def test_delete_download(self):
        dl1 = self.db.add_download("https://ex.com/delete.me", "delete.me", "/path/delete.me")
        self.assertIsNotNone(self.db.get_download(dl1))
        deleted = self.db.delete_download(dl1)
        self.assertTrue(deleted)
        self.assertIsNone(self.db.get_download(dl1))

    def test_segments_storage(self):
        dl_id = self.db.add_download("https://ex.com/split.bin", "split.bin", "/path/split.bin", total_bytes=4000)
        segments = [
            {"index": 0, "start_byte": 0, "current_byte": 500, "end_byte": 999, "status": "downloading", "temp_path": "/tmp/seg0"},
            {"index": 1, "start_byte": 1000, "current_byte": 1000, "end_byte": 1999, "status": "queued", "temp_path": "/tmp/seg1"},
            {"index": 2, "start_byte": 2000, "current_byte": 2000, "end_byte": 2999, "status": "queued", "temp_path": "/tmp/seg2"},
            {"index": 3, "start_byte": 3000, "current_byte": 3000, "end_byte": 3999, "status": "queued", "temp_path": "/tmp/seg3"},
        ]
        self.db.save_segments(dl_id, segments)

        loaded_segs = self.db.get_segments(dl_id)
        self.assertEqual(len(loaded_segs), 4)
        self.assertEqual(loaded_segs[0]["current_byte"], 500)
        self.assertEqual(loaded_segs[0]["end_byte"], 999)

        # Update a single segment
        self.db.update_segment(dl_id, 0, current_byte=800, status="downloading")
        updated_segs = self.db.get_segments(dl_id)
        self.assertEqual(updated_segs[0]["current_byte"], 800)

    def test_settings_kv(self):
        self.assertEqual(self.db.get_setting("max_connections", 8), 8)
        self.db.set_setting("max_connections", 16)
        self.assertEqual(self.db.get_setting("max_connections", 8), 16)

        self.db.set_setting("theme", "dark")
        self.assertEqual(self.db.get_setting("theme"), "dark")


if __name__ == "__main__":
    unittest.main()
