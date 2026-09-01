import json
import os
import unittest


class TestExtensionManifests(unittest.TestCase):
    def setUp(self):
        self.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.extension_dir = os.path.join(self.repo_root, "extension")

    def test_chrome_manifest_mv3_compliance(self):
        manifest_path = os.path.join(self.extension_dir, "manifest.json")
        self.assertTrue(os.path.exists(manifest_path), "manifest.json must exist")

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data.get("manifest_version"), 3, "Chrome manifest must be MV3")
        self.assertIn("background", data)
        self.assertIn("service_worker", data["background"])
        self.assertNotIn("scripts", data["background"], "MV3 background must not declare 'scripts'")
        self.assertNotIn("browser_specific_settings", data, "Gecko settings should not be in Chrome manifest")

        # Verify background service worker file exists
        sw_file = os.path.join(self.extension_dir, data["background"]["service_worker"])
        self.assertTrue(os.path.exists(sw_file), f"Service worker file missing: {sw_file}")

        # Verify action popup and icons
        if "action" in data:
            popup_html = data["action"].get("default_popup")
            if popup_html:
                self.assertTrue(os.path.exists(os.path.join(self.extension_dir, popup_html)))

        # Verify all icons exist
        if "icons" in data:
            for size, icon_rel_path in data["icons"].items():
                self.assertTrue(
                    os.path.exists(os.path.join(self.extension_dir, icon_rel_path)),
                    f"Icon {size} missing at {icon_rel_path}",
                )

        # Verify content scripts exist
        if "content_scripts" in data:
            for cs in data["content_scripts"]:
                for js_path in cs.get("js", []):
                    self.assertTrue(os.path.exists(os.path.join(self.extension_dir, js_path)))
                for css_path in cs.get("css", []):
                    self.assertTrue(os.path.exists(os.path.join(self.extension_dir, css_path)))

    def test_firefox_manifest_compliance(self):
        manifest_path = os.path.join(self.extension_dir, "manifest.firefox.json")
        self.assertTrue(os.path.exists(manifest_path), "manifest.firefox.json must exist")

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data.get("manifest_version"), 2)
        self.assertIn("background", data)
        self.assertIn("scripts", data["background"])
        self.assertIn("browser_specific_settings", data)
        self.assertIn("gecko", data["browser_specific_settings"])


if __name__ == "__main__":
    unittest.main()
