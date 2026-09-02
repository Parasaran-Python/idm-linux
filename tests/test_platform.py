import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from idm_core.platform import (
    get_binary_name,
    get_config_dir,
    get_database_path,
    get_default_ipc_endpoint,
    get_download_dir,
    get_platform_name,
    get_temp_dir,
    is_linux,
    is_macos,
    is_windows,
    move_to_trash,
    open_path,
    resolve_binary,
    reveal_in_file_manager,
    setup_windows_app_id,
    system_power_action,
)


class TestPlatformAbstraction(unittest.TestCase):
    def test_os_detection(self):
        self.assertIsInstance(is_windows(), bool)
        self.assertIsInstance(is_linux(), bool)
        self.assertIsInstance(is_macos(), bool)
        self.assertIn(get_platform_name(), ["windows", "linux", "macos"])

    def test_get_config_dir_custom(self):
        custom = "/custom/path/idm"
        self.assertEqual(get_config_dir(custom), os.path.abspath(custom))

    def test_get_config_dir_simulated_windows(self):
        with patch("idm_core.platform.is_windows", return_value=True), \
             patch.dict(os.environ, {"APPDATA": "C:\\Users\\Test\\AppData\\Roaming"}):
            cfg = get_config_dir()
            self.assertEqual(cfg, os.path.join("C:\\Users\\Test\\AppData\\Roaming", "idm-linux"))

    def test_get_download_dir_simulated_windows(self):
        with patch("idm_core.platform.is_windows", return_value=True), \
             patch.dict(os.environ, {"USERPROFILE": "C:\\Users\\Test"}):
            dl_dir = get_download_dir()
            self.assertTrue(dl_dir.endswith("Downloads"))

    def test_get_default_ipc_endpoint(self):
        with patch("idm_core.platform.is_windows", return_value=True):
            ep = get_default_ipc_endpoint()
            self.assertEqual(ep, r"\\.\pipe\idm_ipc_socket")

        with patch("idm_core.platform.is_windows", return_value=False):
            ep = get_default_ipc_endpoint("/tmp/test_dir")
            self.assertEqual(ep, os.path.join("/tmp/test_dir", "idm.sock"))

    def test_get_temp_and_db_paths(self):
        base = "/tmp/idm_test"
        self.assertEqual(get_temp_dir(base), os.path.join(base, "temp"))
        self.assertEqual(get_database_path(base), os.path.join(base, "idm.db"))

    def test_get_binary_name(self):
        with patch("idm_core.platform.is_windows", return_value=True):
            self.assertEqual(get_binary_name("ffmpeg"), "ffmpeg.exe")
            self.assertEqual(get_binary_name("yt-dlp.exe"), "yt-dlp.exe")

        with patch("idm_core.platform.is_windows", return_value=False):
            self.assertEqual(get_binary_name("ffmpeg"), "ffmpeg")

    def test_resolve_binary(self):
        py = resolve_binary("python3")
        self.assertIsNotNone(py)
        self.assertTrue(os.path.exists(py))

    def test_system_power_action(self):
        with patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            self.assertTrue(system_power_action("shutdown"))
            mock_run.assert_called()

        with patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            self.assertTrue(system_power_action("sleep"))
            mock_run.assert_called()

        self.assertFalse(system_power_action("unknown_action"))

    def test_move_to_trash(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"trash test")
            temp_path = f.name
        self.assertTrue(os.path.exists(temp_path))

        res = move_to_trash(temp_path)
        self.assertTrue(res)
        self.assertFalse(os.path.exists(temp_path))

    def test_setup_windows_app_id(self):
        # Should execute without throwing on any OS
        setup_windows_app_id()


if __name__ == "__main__":
    unittest.main()
