import tempfile
import unittest
from pathlib import Path


class FilesTests(unittest.TestCase):
    def setUp(self):
        try:
            from ownos import files
            self.files = files
        except ImportError:
            self.fail('File navigation behavior is missing')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)

    def test_new_folder_is_created_inside_current_directory(self):
        self.assertEqual(self.files.create_folder(self.path, 'New folder'), self.path / 'New folder')
        self.assertTrue((self.path / 'New folder').is_dir())

    def test_folder_name_cannot_escape_current_directory(self):
        for name in ['', '.', '..', '/tmp', '../escape', 'a/b', 'a\0b']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.files.create_folder(self.path, name)

    def test_listing_puts_folders_first_and_hides_hidden_files(self):
        (self.path / 'Z folder').mkdir(); (self.path / 'a.txt').touch(); (self.path / '.hidden').touch()
        self.assertEqual([p.name for p in self.files.list_folder(self.path)], ['Z folder', 'a.txt'])
