import unittest
from idm_core.category_manager import CategoryManager


class TestCategoryManager(unittest.TestCase):
    def setUp(self):
        self.cat_mgr = CategoryManager()

    def test_filename_categorization(self):
        self.assertEqual(self.cat_mgr.get_category_for_filename("archive.tar.gz"), "Compressed")
        self.assertEqual(self.cat_mgr.get_category_for_filename("setup.exe"), "Programs")
        self.assertEqual(self.cat_mgr.get_category_for_filename("song.flac"), "Music")
        self.assertEqual(self.cat_mgr.get_category_for_filename("movie.mkv"), "Video")
        self.assertEqual(self.cat_mgr.get_category_for_filename("paper.pdf"), "Documents")
        self.assertEqual(self.cat_mgr.get_category_for_filename("unknown.xyz123"), "General")

    def test_mime_categorization(self):
        self.assertEqual(self.cat_mgr.get_category_for_mime("video/mp4"), "Video")
        self.assertEqual(self.cat_mgr.get_category_for_mime("audio/mpeg"), "Music")
        self.assertEqual(self.cat_mgr.get_category_for_mime("application/zip"), "Compressed")
        self.assertEqual(self.cat_mgr.get_category_for_mime("application/pdf"), "Documents")
        self.assertEqual(self.cat_mgr.get_category_for_mime("application/x-executable"), "Programs")


if __name__ == "__main__":
    unittest.main()
