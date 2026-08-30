import unittest
import tempfile
import os
import shutil
import hashlib
from idm_core.config import Config
from idm_core.storage import StorageManager


class TestStorageManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = Config(
            config_dir=self.test_dir,
            temp_dir=os.path.join(self.test_dir, "temp"),
            download_dir=os.path.join(self.test_dir, "Downloads"),
        )
        self.storage = StorageManager(self.config)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_prepare_download_file(self):
        dest_path = os.path.join(self.test_dir, "Downloads", "test_file.bin")
        self.storage.prepare_download_file(dest_path, 1024 * 1024)
        self.assertTrue(os.path.exists(dest_path))
        self.assertEqual(os.path.getsize(dest_path), 1024 * 1024)

    def test_segment_write_and_merge(self):
        download_id = "dl-test123"
        part1_data = b"Hello, "
        part2_data = b"World! This is "
        part3_data = b"IDM Linux Segment Downloader."
        full_data = part1_data + part2_data + part3_data

        p1_path = self.storage.get_temp_segment_path(download_id, 0)
        p2_path = self.storage.get_temp_segment_path(download_id, 1)
        p3_path = self.storage.get_temp_segment_path(download_id, 2)

        self.storage.write_segment_chunk(p1_path, 0, part1_data)
        self.storage.write_segment_chunk(p2_path, 0, part2_data)
        self.storage.write_segment_chunk(p3_path, 0, part3_data)

        dest_path = os.path.join(self.test_dir, "Downloads", "merged.txt")
        merged = self.storage.merge_segments(
            download_id,
            [p1_path, p2_path, p3_path],
            dest_path,
            total_bytes=len(full_data)
        )
        self.assertTrue(merged)
        self.assertTrue(os.path.exists(dest_path))
        with open(dest_path, "rb") as f:
            self.assertEqual(f.read(), full_data)

        # Check temporary cleanup
        self.storage.cleanup_temp(download_id)
        self.assertFalse(os.path.exists(os.path.dirname(p1_path)))

    def test_verify_checksum(self):
        dest_path = os.path.join(self.test_dir, "checksum_test.dat")
        content = b"Verifiable content for hash calculation."
        with open(dest_path, "wb") as f:
            f.write(content)

        expected_sha256 = hashlib.sha256(content).hexdigest()
        expected_md5 = hashlib.md5(content).hexdigest()

        self.assertTrue(self.storage.verify_checksum(dest_path, expected_sha256, "sha256"))
        self.assertTrue(self.storage.verify_checksum(dest_path, expected_md5, "md5"))
        self.assertFalse(self.storage.verify_checksum(dest_path, "wronghash", "sha256"))


if __name__ == "__main__":
    unittest.main()
