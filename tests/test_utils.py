import unittest
from idm_core.utils import (
    is_youtube_url,
    infer_youtube_filename,
    normalize_youtube_videoplayback_url,
)


class TestYouTubeUtils(unittest.TestCase):
    def test_is_youtube_url(self):
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=123"))
        self.assertTrue(is_youtube_url("https://youtu.be/123"))
        self.assertTrue(is_youtube_url("https://m.youtube.com/shorts/xyz"))
        self.assertFalse(is_youtube_url("https://example.com/watch"))
        self.assertFalse(is_youtube_url(""))
        self.assertFalse(is_youtube_url(None))

    def test_infer_youtube_filename(self):
        self.assertEqual(infer_youtube_filename("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "dQw4w9WgXcQ.mp4")
        self.assertEqual(infer_youtube_filename("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ.mp4")
        self.assertEqual(infer_youtube_filename("https://www.youtube.com/shorts/dQw4w9WgXcQ"), "dQw4w9WgXcQ.mp4")
        self.assertEqual(infer_youtube_filename("https://www.youtube.com/live/dQw4w9WgXcQ"), "dQw4w9WgXcQ.mp4")
        self.assertEqual(infer_youtube_filename("https://www.youtube.com/embed/dQw4w9WgXcQ"), "dQw4w9WgXcQ.mp4")
        self.assertEqual(infer_youtube_filename("https://youtu.be/"), "video.mp4")
        self.assertEqual(infer_youtube_filename("https://youtu.be"), "video.mp4")
        self.assertEqual(infer_youtube_filename("https://www.youtube.com/watch"), "video.mp4")
        self.assertEqual(infer_youtube_filename(""), "video.mp4")

    def test_normalize_youtube_videoplayback_url(self):
        raw_dash = "https://rr1---sn-4g5ednsl.googlevideo.com/videoplayback?expire=12345"
        headers_watch = {"Referer": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
        norm_url, fn = normalize_youtube_videoplayback_url(raw_dash, headers_watch)
        self.assertEqual(norm_url, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(fn, "dQw4w9WgXcQ.mp4")

        # Case-insensitive headers (e.g. referer lowercase or page_url)
        headers_lower = {"referer": "https://youtu.be/dQw4w9WgXcQ"}
        norm_url2, fn2 = normalize_youtube_videoplayback_url(raw_dash, headers_lower)
        self.assertEqual(norm_url2, "https://youtu.be/dQw4w9WgXcQ")
        self.assertEqual(fn2, "dQw4w9WgXcQ.mp4")

        headers_page_url = {"page_url": "https://www.youtube.com/shorts/dQw4w9WgXcQ"}
        norm_url3, fn3 = normalize_youtube_videoplayback_url(raw_dash, headers_page_url)
        self.assertEqual(norm_url3, "https://www.youtube.com/shorts/dQw4w9WgXcQ")
        self.assertEqual(fn3, "dQw4w9WgXcQ.mp4")

        # Bare origin should not normalize
        headers_bare = {"Referer": "https://www.youtube.com/"}
        norm_url4, fn4 = normalize_youtube_videoplayback_url(raw_dash, headers_bare)
        self.assertEqual(norm_url4, raw_dash)
        self.assertIsNone(fn4)

        # Non-youtube referer should not normalize
        headers_non_yt = {"Referer": "https://example.com/watch?v=123"}
        norm_url5, fn5 = normalize_youtube_videoplayback_url(raw_dash, headers_non_yt)
        self.assertEqual(norm_url5, raw_dash)
        self.assertIsNone(fn5)


if __name__ == "__main__":
    unittest.main()
