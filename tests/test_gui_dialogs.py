import unittest
import sys
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from idm_gui.dialogs.download_info_dialog import DownloadInfoDialog
from idm_gui.dialogs.download_progress_dialog import DownloadProgressDialog
from idm_gui.dialogs.queue_scheduler_dialog import QueueSchedulerDialog
from idm_gui.dialogs.options_dialog import OptionsDialog
from idm_gui.dialogs.batch_download_dialog import BatchDownloadDialog

app = QApplication.instance() or QApplication(sys.argv)


class TestGUIDialogs(unittest.TestCase):
    def test_download_info_dialog(self):
        dialog = DownloadInfoDialog(
            url="https://example.com/file.zip",
            filename="file.zip",
            save_path="/tmp/file.zip",
            category="Compressed"
        )
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.url_edit.text(), "https://example.com/file.zip")
        self.assertEqual(dialog.category_combo.currentText(), "Compressed")

    def test_download_progress_dialog(self):
        dialog = DownloadProgressDialog(download_id="dl-test-dialog", filename="test.bin")
        self.assertIsNotNone(dialog)
        dialog.update_progress({
            "status": "downloading",
            "downloaded_bytes": 500000,
            "total_bytes": 1000000,
            "speed": 250000,
            "eta": 2,
            "resumable": True
        })
        self.assertEqual(dialog.status_label.text(), "Downloading")

    def test_queue_scheduler_dialog(self):
        dialog = QueueSchedulerDialog()
        self.assertIsNotNone(dialog)

    def test_options_dialog(self):
        dialog = OptionsDialog()
        self.assertIsNotNone(dialog)
        self.assertGreaterEqual(dialog.connections_spin.value(), 1)

    def test_batch_download_dialog(self):
        dialog = BatchDownloadDialog()
        self.assertIsNotNone(dialog)
        dialog.text_edit.setPlainText("https://ex.com/1.zip\nhttps://ex.com/2.zip")
        urls = dialog.get_urls()
        self.assertEqual(len(urls), 2)

    def test_probe_worker_normalizes_videoplayback_url(self):
        from idm_gui.dialogs.download_info_dialog import ProbeWorker
        from idm_core.utils import normalize_youtube_videoplayback_url
        worker = ProbeWorker(
            url="https://rr1---sn-4g5ednsl.googlevideo.com/videoplayback?expire=12345",
            headers={"Referer": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
        )
        worker.url, _ = normalize_youtube_videoplayback_url(worker.url, worker.headers)
        self.assertEqual(worker.url, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        # Non-youtube referer should not normalize
        worker2 = ProbeWorker(
            url="https://rr1---sn-4g5ednsl.googlevideo.com/videoplayback?expire=12345",
            headers={"Referer": "https://example.com/watch?v=123"}
        )
        worker2.url, _ = normalize_youtube_videoplayback_url(worker2.url, worker2.headers)
        self.assertEqual(worker2.url, "https://rr1---sn-4g5ednsl.googlevideo.com/videoplayback?expire=12345")

    def test_download_info_dialog_normalizes_videoplayback_url(self):
        dialog = DownloadInfoDialog(
            url="https://rr1---sn-4g5ednsl.googlevideo.com/videoplayback?expire=12345",
            headers={"Referer": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            category="General"
        )
        self.assertEqual(dialog.url_edit.text(), "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        
        # Test category auto-update in _on_probed
        dialog._on_probed(10485760, "MyVideo.mp4")
        self.assertEqual(dialog.category_combo.currentText(), "Video")
        self.assertIn("MyVideo.mp4", dialog.save_edit.text())


if __name__ == "__main__":
    unittest.main()
