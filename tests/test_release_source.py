"""Protect source command links when uploading Git trees via APIs."""
import unittest
from pathlib import Path


class CommandLinksTests(unittest.TestCase):
    def test_source_commands_resolve_to_the_shared_cli(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('own-control', 'own-files', 'own-game', 'own-install-app',
                     'own-shell', 'own-toggle-notifications', 'own-toggle-start'):
            with self.subTest(command=name):
                path = root / 'bin' / name
                self.assertTrue(path.is_symlink())
                self.assertEqual(path.readlink(), Path('own.py'))
                self.assertTrue(path.is_file())
