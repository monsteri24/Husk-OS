"""Desktop file operations preserve user contents and virtual icon policy."""
import errno
import os
import tempfile
import unittest
from pathlib import Path

from ownos import files


class DesktopFileOperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_new_file_is_empty_and_never_overwrites_existing_contents(self):
        self.assertTrue(hasattr(files, 'create_file'), 'Desktop New File is missing')
        path = files.create_file(self.root, 'notes.txt')
        self.assertEqual(path.read_bytes(), b'')
        path.write_text('keep')
        with self.assertRaises(FileExistsError):
            files.create_file(self.root, 'notes.txt')
        self.assertEqual(path.read_text(), 'keep')

    def test_new_file_and_rename_reject_names_outside_the_directory(self):
        self.assertTrue(hasattr(files, 'create_file'), 'Desktop New File is missing')
        self.assertTrue(hasattr(files, 'rename_entry'), 'Desktop Rename is missing')
        source = self.root / 'original'; source.touch()
        for name in ('', '.', '..', '../escape', '/tmp/escape', 'bad\0name', 'é' * 128):
            with self.subTest(name=name):
                with self.assertRaises(ValueError): files.create_file(self.root, name)
                with self.assertRaises(ValueError): files.rename_entry(source, name)
        self.assertTrue(source.is_file())

    def test_rename_preserves_file_contents_and_refuses_a_collision(self):
        self.assertTrue(hasattr(files, 'rename_entry'), 'Desktop Rename is missing')
        source = self.root / 'old'; source.write_text('source')
        occupied = self.root / 'occupied'; occupied.write_text('destination')
        with self.assertRaises(FileExistsError): files.rename_entry(source, 'occupied')
        self.assertEqual(occupied.read_text(), 'destination')
        renamed = files.rename_entry(source, 'new')
        self.assertEqual(renamed.read_text(), 'source')
        self.assertFalse(source.exists())

    def test_paste_copies_files_and_directories_without_overwriting(self):
        self.assertTrue(hasattr(files, 'paste_entries'), 'Desktop Paste is missing')
        source = self.root / 'source'; source.mkdir()
        (source / 'notes.txt').write_text('preserved')
        (source / 'folder').mkdir(); (source / 'folder' / 'nested').write_text('nested')
        target = self.root / 'Desktop'; target.mkdir()
        copied = files.paste_entries(target, [source / 'notes.txt', source / 'folder'])
        self.assertEqual([p.name for p in copied], ['notes.txt', 'folder'])
        self.assertEqual((target / 'folder' / 'nested').read_text(), 'nested')
        self.assertEqual((source / 'notes.txt').read_text(), 'preserved')
        with self.assertRaises(FileExistsError): files.paste_entries(target, [source / 'notes.txt'])
        self.assertEqual((target / 'notes.txt').read_text(), 'preserved')

    def test_paste_cut_moves_a_file_and_rejects_recursive_directory_copy(self):
        self.assertTrue(hasattr(files, 'paste_entries'), 'Desktop Paste is missing')
        source = self.root / 'source'; source.mkdir()
        child = source / 'child'; child.mkdir()
        with self.assertRaises(ValueError): files.paste_entries(child, [source])
        note = self.root / 'note'; note.write_text('move')
        files.paste_entries(child, [note], cut=True)
        self.assertFalse(note.exists())
        self.assertEqual((child / 'note').read_text(), 'move')

    def test_cut_preserves_writes_from_an_application_with_the_file_open(self):
        note = self.root / 'note'; note.write_text('before')
        target = self.root / 'Desktop'; target.mkdir()
        with note.open('a') as writer:
            files.paste_entries(target, [note], cut=True)
            writer.write(' after')
        self.assertEqual((target / 'note').read_text(), 'before after')

    def test_cross_filesystem_cut_refuses_without_removing_the_original(self):
        if not os.access('/dev/shm', os.W_OK): self.skipTest('No temporary second filesystem')
        with tempfile.TemporaryDirectory(dir='/dev/shm') as directory:
            target = Path(directory)
            if target.stat().st_dev == self.root.stat().st_dev: self.skipTest('Temporary locations share a filesystem')
            note = self.root / 'note'; note.write_text('preserve')
            with self.assertRaises(OSError) as raised:
                files.paste_entries(target, [note], cut=True)
            self.assertEqual(raised.exception.errno, errno.EXDEV)
            self.assertEqual(note.read_text(), 'preserve')
            self.assertFalse((target / 'note').exists())

    def test_clipboard_only_accepts_local_file_uris_and_gnome_file_lists(self):
        self.assertTrue(hasattr(files, 'parse_file_clipboard'), 'Desktop file clipboard parser is missing')
        note = self.root / 'a b.txt'; note.touch()
        parsed = files.parse_file_clipboard('# copied files\r\n' + note.as_uri() + '\r\n')
        self.assertEqual(parsed, (False, [note]))
        self.assertEqual(files.parse_file_clipboard('cut\n' + note.as_uri(), gnome=True), (True, [note]))
        for data in ('', 'plain text', 'https://example.com/file', 'file://remote/tmp/note',
                     'file:///tmp/a\nhttps://example.com/file', 'file:///tmp/a%00b', 'file://[invalid/tmp/a'):
            with self.subTest(data=data): self.assertIsNone(files.parse_file_clipboard(data))


class DesktopEntryPolicyTests(unittest.TestCase):
    def setUp(self):
        try:
            from ownos import desktop_files
        except ImportError:
            self.fail('Desktop virtual entry policy is missing')
        self.desktop_files = desktop_files

    def test_virtual_entries_remain_protected_and_show_full_regular_names(self):
        desktop_files = self.desktop_files
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory); desktop = home / 'Desktop'; desktop.mkdir()
            (desktop / 'notes.txt').touch(); (desktop / '.hidden').touch()
            entries = desktop_files.desktop_entries(desktop, home=home, live=False)
            self.assertEqual([entry.label for entry in entries], ['Home', 'Trash', 'notes.txt'])
            self.assertTrue(all(entry.protected for entry in entries[:2]))
            self.assertFalse(entries[-1].protected)

    def test_hiding_trash_only_filters_the_virtual_icon(self):
        desktop_files = self.desktop_files
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory); desktop = home / 'Desktop'; desktop.mkdir()
            file = desktop / 'Trash'; file.write_text('ordinary user file')
            entries = desktop_files.desktop_entries(desktop, home=home, show_trash=False, live=False)
            self.assertEqual([(entry.kind, entry.label) for entry in entries], [('home', 'Home'), ('file', 'Trash')])
            self.assertEqual(file.read_text(), 'ordinary user file')

    def test_live_installer_is_a_protected_virtual_action(self):
        desktop_files = self.desktop_files
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entries = desktop_files.desktop_entries(root, home=root, live=True)
            installer = next(entry for entry in entries if entry.kind == 'installer')
            self.assertEqual(installer.label, 'Install Husk OS')
            self.assertEqual(installer.icon, 'husk-install')
            self.assertTrue(installer.protected)
            self.assertIsNone(installer.path)
            self.assertFalse(list(root.iterdir()))

    def test_installer_requires_both_live_environment_and_executable(self):
        desktop_files = self.desktop_files
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); live = root / 'archiso'; installer = root / 'husk-install'
            installer.write_text('#!/bin/sh\n')
            installer.chmod(0o755)
            self.assertFalse(desktop_files.live_installer_available(live, installer))
            live.mkdir()
            self.assertTrue(desktop_files.live_installer_available(live, installer))
            installer.chmod(0o644)
            self.assertFalse(desktop_files.live_installer_available(live, installer))


if __name__ == '__main__': unittest.main()
