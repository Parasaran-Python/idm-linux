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


if __name__ == "__main__":
    unittest.main()
