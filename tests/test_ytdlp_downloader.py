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

    def test_probe_media_info_mock(self):
        sample_json = {
            "title": "Sample Video Title",
            "ext": "mp4",
            "duration": 120,
            "formats": [
                {"height": 1080, "fps": 60, "tbr": 4000, "vcodec": "avc1", "acodec": "none", "filesize": 50000000},
                {"height": 720, "fps": 30, "tbr": 2000, "vcodec": "avc1", "acodec": "none", "filesize": 25000000},
                {"height": None, "vcodec": "none", "acodec": "opus", "filesize": 5000000}
            ]
        }
        import json
        from unittest.mock import patch, MagicMock

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = json.dumps(sample_json)

        with patch.object(YTDLPDownloader, "is_ytdlp_available", return_value=True), \
             patch("subprocess.run", return_value=mock_res):
            info = YTDLPDownloader.probe_media_info("https://example.com/video", quality="1080")
            self.assertEqual(info["title"], "Sample Video Title")
            self.assertEqual(info["filename"], "Sample Video Title.mp4")
            # 50MB video + 5MB audio = 55MB
            self.assertEqual(info["filesize"], 55000000)

    def test_multistream_progress_tracking(self):
        downloader = YTDLPDownloader("multi-test", "https://youtube.com/watch?v=123", "/tmp/out.mp4")
        progress_events = []
        downloader.on_progress = lambda did, stats: progress_events.append(stats)

        # Video stream: 370 MiB
        downloader._parse_line("[download] Destination: /tmp/out.f399.mp4")
        downloader._parse_line("[download]  50.0% of 370.00MiB at 10.00MiB/s ETA 00:18")
        self.assertEqual(downloader.downloaded_bytes, int(185.0 * 1024 * 1024))
        self.assertEqual(downloader.total_bytes, int(370.0 * 1024 * 1024))

        downloader._parse_line("[download] 100.0% of 370.00MiB at 10.00MiB/s ETA 00:00")
        self.assertEqual(downloader.downloaded_bytes, int(370.0 * 1024 * 1024))
        self.assertEqual(downloader.total_bytes, int(370.0 * 1024 * 1024))

        # Audio stream: 26 MiB transition
        downloader._parse_line("[download] Destination: /tmp/out.f140.m4a")
        downloader._parse_line("[download]   0.0% of 26.00MiB at 2.00MiB/s ETA 00:13")
        # Should retain video downloaded bytes without dropping to 0
        self.assertEqual(downloader.downloaded_bytes, int(370.0 * 1024 * 1024))
        self.assertEqual(downloader.total_bytes, int(396.0 * 1024 * 1024))

        downloader._parse_line("[download]  50.0% of 26.00MiB at 2.00MiB/s ETA 00:06")
        self.assertEqual(downloader.downloaded_bytes, int((370.0 + 13.0) * 1024 * 1024))
        self.assertEqual(downloader.total_bytes, int(396.0 * 1024 * 1024))

        downloader._parse_line("[download] 100.0% of 26.00MiB at 2.00MiB/s ETA 00:00")
        self.assertEqual(downloader.downloaded_bytes, int(396.0 * 1024 * 1024))
        self.assertEqual(downloader.total_bytes, int(396.0 * 1024 * 1024))

    def test_codec_priority_selection(self):
        # When both AV01 (370MB) and AVC1 (664MB) exist for 1080p, prefer AV01 matching yt-dlp
        sample_json = {
            "formats": [
                {"height": 1080, "fps": 30, "tbr": 4500, "vcodec": "avc1.640028", "acodec": "none", "filesize": 664000000},
                {"height": 1080, "fps": 30, "tbr": 3000, "vcodec": "vp09.00.40", "acodec": "none", "filesize": 450000000},
                {"height": 1080, "fps": 30, "tbr": 2500, "vcodec": "av01.0.08M.08", "acodec": "none", "filesize": 370000000},
                {"height": None, "vcodec": "none", "acodec": "opus", "filesize": 26000000}
            ]
        }
        import json
        from unittest.mock import patch, MagicMock

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = json.dumps(sample_json)

        with patch.object(YTDLPDownloader, "is_ytdlp_available", return_value=True), \
             patch("subprocess.run", return_value=mock_res):
            formats = YTDLPDownloader.extract_media_formats("https://youtube.com/watch?v=123")
            fmt_1080 = next(f for f in formats if f["quality"] == "1080")
            # Chosen video size should be 370MB + 26MB audio = 396MB (not 664MB + 26MB = 690MB)
            self.assertEqual(fmt_1080["filesize"], 370000000 + 26000000)

    def test_quality_string_normalization(self):
        sample_json = {
            "title": "Normalized Video",
            "ext": "mp4",
            "formats": [
                {"height": 1080, "fps": 30, "tbr": 2500, "vcodec": "av01", "acodec": "none", "filesize": 370000000},
                {"height": 720, "fps": 30, "tbr": 1200, "vcodec": "av01", "acodec": "none", "filesize": 150000000},
                {"height": None, "vcodec": "none", "acodec": "opus", "filesize": 26000000}
            ]
        }
        import json
        from unittest.mock import patch, MagicMock

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = json.dumps(sample_json)

        with patch.object(YTDLPDownloader, "is_ytdlp_available", return_value=True), \
             patch("subprocess.run", return_value=mock_res):
            # Test "1080p", "1080P", "1080" all match 370MB + 26MB = 396MB
            info_p = YTDLPDownloader.probe_media_info("https://youtube.com/watch?v=123", quality="1080p")
            info_plain = YTDLPDownloader.probe_media_info("https://youtube.com/watch?v=123", quality="1080")
            info_audio = YTDLPDownloader.probe_media_info("https://youtube.com/watch?v=123", quality="audio")

            self.assertEqual(info_p["filesize"], 396000000)
            self.assertEqual(info_plain["filesize"], 396000000)
            self.assertEqual(info_audio["filesize"], 26000000)


if __name__ == "__main__":
    unittest.main()
