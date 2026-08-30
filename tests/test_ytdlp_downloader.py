"""
Unit Tests for YTDLPDownloader & Video Platform Detection
"""

import unittest
from idm_core.ytdlp_downloader import YTDLPDownloader


class TestYTDLPDownloader(unittest.TestCase):
    def test_platform_url_detection(self):
        yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        vimeo_url = "https://vimeo.com/76979871"
        direct_url = "https://example.com/files/archive.zip"

        self.assertTrue(YTDLPDownloader.is_video_platform_url(yt_url))
        self.assertTrue(YTDLPDownloader.is_video_platform_url(vimeo_url))
        self.assertFalse(YTDLPDownloader.is_video_platform_url(direct_url))

    def test_parse_line_progress(self):
        downloader = YTDLPDownloader("test-id", "https://youtube.com/watch?v=123", "/tmp/out.mp4")
        
        progress_events = []
        downloader.on_progress = lambda did, stats: progress_events.append(stats)

        # Test sample progress line
        line = "[download]  50.0% of 100.00MiB at 5.00MiB/s ETA 00:10"
        downloader._parse_line(line)

        self.assertEqual(len(progress_events), 1)
        ev = progress_events[0]
        self.assertEqual(ev["status"], "downloading")
        self.assertEqual(ev["total_bytes"], 100 * 1024 * 1024)
        self.assertEqual(ev["downloaded_bytes"], 50 * 1024 * 1024)
        self.assertEqual(ev["eta"], 10)


    def test_extract_media_formats_mock(self):
        # Verify extract_media_formats parses JSON format dictionary correctly
        sample_json = {
            "formats": [
                {"height": 1080, "fps": 60, "tbr": 4000, "vcodec": "avc1", "acodec": "none", "filesize": 50000000},
                {"height": 720, "fps": 30, "tbr": 2000, "vcodec": "avc1", "acodec": "none", "filesize": 25000000},
                {"height": 360, "fps": 30, "tbr": 800, "vcodec": "avc1", "acodec": "mp4a", "filesize": 10000000},
                {"height": None, "vcodec": "none", "acodec": "opus", "filesize": 3000000}
            ]
        }
        import json
        from unittest.mock import patch, MagicMock

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = json.dumps(sample_json)

        with patch.object(YTDLPDownloader, "is_ytdlp_available", return_value=True), \
             patch("subprocess.run", return_value=mock_res):
            formats = YTDLPDownloader.extract_media_formats("https://example.com/video")
            self.assertTrue(len(formats) >= 3)
            # Should have 1080p, 720p, 360p, and audio
            qualities = [f["quality"] for f in formats]
            self.assertIn("1080", qualities)
            self.assertIn("720", qualities)
            self.assertIn("360", qualities)
            self.assertIn("audio", qualities)

    def test_format_selection_strings(self):
        dl_1080 = YTDLPDownloader("id1", "https://youtube.com/watch?v=1", "/tmp/v.mp4", quality="1080")
        self.assertEqual(dl_1080.quality, "1080")

        dl_audio = YTDLPDownloader("id2", "https://youtube.com/watch?v=1", "/tmp/v.mp3", quality="audio")
        self.assertEqual(dl_audio.quality, "audio")


if __name__ == "__main__":
    unittest.main()
