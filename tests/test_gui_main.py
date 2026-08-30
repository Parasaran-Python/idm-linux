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
        self.assertEqual(window.windowTitle(), "IDM Linux - Internet Download Manager")
        self.assertIsNotNone(window.table)
        self.assertIsNotNone(window.category_tree)
        window.close()

    def test_tray_icon(self):
        window = MainWindow()
        tray = IDMTrayIcon(window)
        self.assertIsNotNone(tray)
        window.close()


if __name__ == "__main__":
    unittest.main()
