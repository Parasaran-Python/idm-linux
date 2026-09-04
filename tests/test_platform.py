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
    derive_chrome_extension_id,
    get_default_chrome_extension_ids,
    resolve_native_host_binary,
    is_native_messaging_host_registered,
    register_native_messaging_host,
    unregister_native_messaging_host,
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
            self.assertEqual(cfg, os.path.join("C:\\Users\\Test\\AppData\\Roaming", "pv-idm"))

    def test_get_config_dir_legacy_fallback(self):
        with patch("os.path.exists", side_effect=lambda p: p.endswith("idm-linux")):
            cfg = get_config_dir()
            self.assertTrue(cfg.endswith("idm-linux"))

    def test_get_config_dir_legacy_fallback_when_target_empty(self):
        # Target exists (e.g. created by native host registration), but legacy has idm.db
        def mock_exists(p):
            if "idm-linux" in p:
                return True
            if p.endswith("pv-idm"):
                return True
            return False

        with patch("os.path.exists", side_effect=mock_exists):
            cfg = get_config_dir()
            self.assertTrue(cfg.endswith("idm-linux"))

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
        with patch("idm_core.platform.is_windows", return_value=False), \
             patch("idm_core.platform.is_macos", return_value=False), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            self.assertTrue(system_power_action("shutdown"))
            mock_run.assert_called()

        with patch("idm_core.platform.is_windows", return_value=False), \
             patch("idm_core.platform.is_macos", return_value=False), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            self.assertTrue(system_power_action("sleep"))
            mock_run.assert_called()

        with patch("idm_core.platform.is_windows", return_value=True), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            self.assertTrue(system_power_action("shutdown"))
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

    def test_show_desktop_notification(self):
        from idm_core.platform import show_desktop_notification
        with patch("subprocess.Popen") as mock_popen, \
             patch("shutil.which", return_value="/usr/bin/notify-send"):
            res = show_desktop_notification("Test Title", "Test Message")
            self.assertTrue(res)
            mock_popen.assert_called()

    def test_derive_chrome_extension_id(self):
        sample_key = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoA6YmseHHQDbr/A/lPOhNqOZOfF5C0VmA/Sa3mHtL4UUGx+uyDK3Plpw4v8NlTETh5HqmR2cPxoFRWV0uUcb+X38gFEvF7HXdAkhS5FN3di5xSmiQdPvBA/IpppuHDx1OeAR7y7vmMCcmynvvJlaOPYtjl4K664GL4rn7oF8alM1p0HVrH6Q4zGo/0PkPkua1rKkIUSFZFsEJ5c46h4FHFdWjhcH/tdYQBwBirtHskFEzFn5/1k9j+JkahJygMvEKt79GQt1o7CXzWrjaXRLPQp9/cJFc/eH1/wroDxPKogC60wdU7JB7O+4/5Lmz56M4691f3YyrQLj2xy7SOVH+wIDAQAB"
        ext_id = derive_chrome_extension_id(sample_key)
        self.assertEqual(len(ext_id), 32)
        self.assertTrue(all("a" <= c <= "p" for c in ext_id))

    def test_get_default_chrome_extension_ids(self):
        ids = get_default_chrome_extension_ids()
        self.assertIsInstance(ids, list)
        self.assertGreater(len(ids), 0)

    def test_resolve_native_host_binary_explicit(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_bin = f.name
        try:
            resolved = resolve_native_host_binary(temp_bin)
            self.assertEqual(os.path.normpath(resolved), os.path.normpath(temp_bin))
        finally:
            if os.path.exists(temp_bin):
                os.remove(temp_bin)

    def test_resolve_native_host_binary_pv_idm(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pv_host = os.path.join(tmp_dir, "pv-idm-native-host")
            with open(pv_host, "w") as f:
                f.write("#!/bin/sh\n")
            os.chmod(pv_host, 0o755)
            with patch("shutil.which", side_effect=lambda name: pv_host if name == "pv-idm-native-host" else None):
                resolved = resolve_native_host_binary()
                self.assertEqual(resolved, os.path.abspath(pv_host))

    def test_is_native_messaging_host_registered(self):
        res = is_native_messaging_host_registered()
        self.assertIsInstance(res, bool)


if __name__ == "__main__":
    unittest.main()
