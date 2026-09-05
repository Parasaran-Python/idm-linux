"""
Unit Tests for YTDLPDownloader & Video Platform Detection
"""

import unittest
import unittest.mock
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

    def test_premuxed_vs_adaptive_separate_pairing(self):
        # Format 22 is 720p with audio (20MB), while Format 136 is 720p video-only (25MB) + Format 251 audio (5MB) = 30MB
        # yt-dlp prefers separate adaptive streams for higher quality
        sample_json = {
            "formats": [
                {"format_id": "22", "height": 720, "fps": 30, "tbr": 1200, "vcodec": "avc1", "acodec": "mp4a", "filesize": 20000000},
                {"format_id": "136", "height": 720, "fps": 30, "tbr": 2000, "vcodec": "avc1", "acodec": "none", "filesize": 25000000},
                {"format_id": "251", "height": None, "vcodec": "none", "acodec": "opus", "filesize": 5000000}
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
            fmt_720 = next(f for f in formats if f["quality"] == "720")
            # Should prefer the 25MB video + 5MB audio = 30MB stream pair
            self.assertEqual(fmt_720["filesize"], 30000000)

    def test_multistream_progress_refines_to_exact_stream_sum(self):
        # Initial estimate was 400 MiB, but actual streams are 370 MiB video + 26 MiB audio = 396 MiB
        init_est = int(400.0 * 1024 * 1024)
        downloader = YTDLPDownloader("multi-refine", "https://youtube.com/watch?v=123", "/tmp/out.mp4", total_bytes=init_est)

        # Stream 1: Video (370 MiB)
        downloader._parse_line("[download] Destination: /tmp/out.f399.mp4")
        downloader._parse_line("[download]  50.0% of 370.00MiB at 10.00MiB/s ETA 00:18")
        # While stream 1 is downloading, total_bytes should maintain the multi-stream estimate
        self.assertEqual(downloader.downloaded_bytes, int(185.0 * 1024 * 1024))
        self.assertEqual(downloader.total_bytes, init_est)

        downloader._parse_line("[download] 100.0% of 370.00MiB at 10.00MiB/s ETA 00:00")
        self.assertEqual(downloader.downloaded_bytes, int(370.0 * 1024 * 1024))

        # Stream 2: Audio (26 MiB)
        downloader._parse_line("[download] Destination: /tmp/out.f140.m4a")
        downloader._parse_line("[download]  50.0% of 26.00MiB at 2.00MiB/s ETA 00:06")
        # Once both streams are active/known, total_bytes should accurately refine to 370 + 26 = 396 MiB
        self.assertEqual(downloader.downloaded_bytes, int((370.0 + 13.0) * 1024 * 1024))
        self.assertEqual(downloader.total_bytes, int(396.0 * 1024 * 1024))

        downloader._parse_line("[download] 100.0% of 26.00MiB at 2.00MiB/s ETA 00:00")
        self.assertEqual(downloader.downloaded_bytes, int(396.0 * 1024 * 1024))
        self.assertEqual(downloader.total_bytes, int(396.0 * 1024 * 1024))

    def test_ytdlp_downloader_resolves_total_bytes_if_zero(self):
        downloader = YTDLPDownloader("probe-test", "https://youtube.com/watch?v=123", "/tmp/out.mp4", quality="1080", total_bytes=0)
        sample_info = {
            "title": "Probed Video",
            "filename": "Probed Video.mp4",
            "filesize": 55000000,
            "duration": 120
        }
        with unittest.mock.patch.object(YTDLPDownloader, "is_ytdlp_available", return_value=True), \
             unittest.mock.patch.object(YTDLPDownloader, "probe_media_info", return_value=sample_info):
            downloader._resolve_initial_size_if_needed()
            self.assertEqual(downloader.total_bytes, 55000000)


    def test_acodec_priority_prefers_aac_over_opus(self):
        aac_score = YTDLPDownloader._get_acodec_priority("mp4a.40.2")
        opus_score = YTDLPDownloader._get_acodec_priority("opus")
        self.assertGreater(aac_score, opus_score, "AAC/mp4a must have higher priority than Opus for universal MP4 container compatibility")

    def test_extract_formats_selects_aac_over_opus(self):
        sample_json = {
            "formats": [
                {"height": 1080, "fps": 30, "tbr": 2500, "vcodec": "av01.0.08M.08", "acodec": "none", "filesize": 370000000},
                {"height": None, "vcodec": "none", "acodec": "opus", "filesize": 26000000},
                {"height": None, "vcodec": "none", "acodec": "mp4a.40.2", "filesize": 30000000}
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
            # Should prefer the 30MB AAC audio over 26MB Opus audio: 370MB + 30MB = 400MB
            self.assertEqual(fmt_1080["filesize"], 370000000 + 30000000)

    def test_run_ytdlp_command_args_with_ffmpeg(self):
        from unittest.mock import patch, MagicMock
        downloader = YTDLPDownloader("cmd-test", "https://youtube.com/watch?v=123", "/tmp/out.mp4", quality="1080")

        mock_proc = MagicMock()
        mock_proc.stdout = []
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        with patch("idm_core.ytdlp_downloader.resolve_binary") as mock_res_bin, \
             patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            def fake_resolve(bin_name):
                if bin_name == "ffmpeg":
                    return "/usr/bin/ffmpeg"
                return "/usr/bin/yt-dlp"
            mock_res_bin.side_effect = fake_resolve

            downloader._run_ytdlp()

            self.assertTrue(mock_popen.called)
            cmd = mock_popen.call_args[0][0]
            # Must prefer AAC in format selection
            cmd_str = " ".join(cmd)
            self.assertIn("bestaudio[ext=m4a]", cmd_str)
            self.assertIn("-S", cmd)
            s_idx = cmd.index("-S")
            self.assertIn("acodec:m4a", cmd[s_idx + 1])
            self.assertIn("--postprocessor-args", cmd)
            pp_idx = cmd.index("--postprocessor-args")
            self.assertIn("Merger:-c:v copy -c:a aac", cmd[pp_idx + 1])

    def test_run_ytdlp_command_args_without_ffmpeg(self):
        from unittest.mock import patch, MagicMock
        downloader = YTDLPDownloader("no-ffmpeg-test", "https://youtube.com/watch?v=123", "/tmp/out.mp4", quality="1080")

        mock_proc = MagicMock()
        mock_proc.stdout = []
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        with patch("idm_core.ytdlp_downloader.resolve_binary") as mock_res_bin, \
             patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            def fake_resolve(bin_name):
                if bin_name == "ffmpeg":
                    return None
                return "/usr/bin/yt-dlp"
            mock_res_bin.side_effect = fake_resolve

            downloader._run_ytdlp()

            self.assertTrue(mock_popen.called)
            cmd = mock_popen.call_args[0][0]
            cmd_str = " ".join(cmd)
            # Without ffmpeg, must NOT ask for separate video+audio streams which cannot be merged
            self.assertNotIn("bestvideo+", cmd_str)
            self.assertIn("best[height<=1080]/best", cmd_str)
            self.assertNotIn("--merge-output-format", cmd_str)

    def test_run_ytdlp_command_args_for_audio_with_ffmpeg(self):
        from unittest.mock import patch, MagicMock
        downloader = YTDLPDownloader("audio-test", "https://youtube.com/watch?v=123", "/tmp/song.mp3", quality="audio")

        mock_proc = MagicMock()
        mock_proc.stdout = []
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        with patch("idm_core.ytdlp_downloader.resolve_binary") as mock_res_bin, \
             patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            def fake_resolve(bin_name):
                if bin_name == "ffmpeg":
                    return "/usr/bin/ffmpeg"
                return "/usr/bin/yt-dlp"
            mock_res_bin.side_effect = fake_resolve

            downloader._run_ytdlp()

            self.assertTrue(mock_popen.called)
            cmd = mock_popen.call_args[0][0]
            cmd_str = " ".join(cmd)
            self.assertIn("--audio-format mp3", cmd_str)
            self.assertIn("--ffmpeg-location", cmd)
            self.assertIn("/usr/bin/ffmpeg", cmd)
            self.assertNotIn("--merge-output-format", cmd_str)

    def test_run_ytdlp_command_args_for_webm_with_ffmpeg(self):
        from unittest.mock import patch, MagicMock
        downloader = YTDLPDownloader("webm-test", "https://youtube.com/watch?v=123", "/tmp/out.webm", quality="1080")

        mock_proc = MagicMock()
        mock_proc.stdout = []
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        with patch("idm_core.ytdlp_downloader.resolve_binary") as mock_res_bin, \
             patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            def fake_resolve(bin_name):
                if bin_name == "ffmpeg":
                    return "/usr/bin/ffmpeg"
                return "/usr/bin/yt-dlp"
            mock_res_bin.side_effect = fake_resolve

            downloader._run_ytdlp()

            self.assertTrue(mock_popen.called)
            cmd = mock_popen.call_args[0][0]
            cmd_str = " ".join(cmd)
            self.assertNotIn("acodec:m4a", cmd_str)
            self.assertNotIn("--merge-output-format", cmd_str)
            self.assertNotIn("Merger:-c:a aac", cmd_str)


if __name__ == "__main__":
    unittest.main()


