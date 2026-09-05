import unittest
import sys
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from idm_core.config import Config
from idm_gui.main_window import MainWindow
from idm_gui.tray import IDMTrayIcon

app = QApplication.instance() or QApplication(sys.argv)


class TestGUIMain(unittest.TestCase):
    def test_main_window_creation(self):
        window = MainWindow()
        self.assertIsNotNone(window)
        self.assertEqual(window.windowTitle(), "PV-IDM - Internet Download Manager")
        self.assertIsNotNone(window.table)
        self.assertIsNotNone(window.category_tree)
        window.close()

    def test_tray_icon(self):
        window = MainWindow()
        tray = IDMTrayIcon(window)
        self.assertIsNotNone(tray)
        self.assertEqual(tray.toolTip(), "PV-IDM - Internet Download Manager")
        self.assertFalse(tray.icon().isNull())
        window.close()

    def test_icon_resolution(self):
        from idm_gui.tray import create_tray_icon_pixmap, create_app_icon, find_icon_file
        icon_path = find_icon_file("icon32.png")
        self.assertIsNotNone(icon_path)
        self.assertTrue(os.path.exists(icon_path))

        pm = create_tray_icon_pixmap()
        self.assertFalse(pm.isNull())
        self.assertGreater(pm.width(), 0)
        self.assertGreater(pm.height(), 0)

        app_icon = create_app_icon()
        self.assertFalse(app_icon.isNull())


if __name__ == "__main__":
    unittest.main()
