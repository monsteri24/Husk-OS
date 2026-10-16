import tempfile
import json
import subprocess
import sys
import unittest
from pathlib import Path

from ownos.rootfs import guest_path, validate_rootfs


class RootfsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'airootfs'
        self.root.mkdir()
        for name in ('usr/bin/own-session', 'usr/bin/labwc', 'usr/bin/foot',
                     'usr/bin/own-toplevel', 'usr/lib/ownos/own.py',
                     'usr/lib/ownos/live-setup', 'usr/lib/ownos/live-keyring'):
            self.put(name, '#!/bin/sh\nexit 0\n', 0o755)
        (self.root / 'usr/bin/husk-session').symlink_to('/usr/bin/own-session')
        (self.root / 'usr/bin/husk-desktop').symlink_to('../lib/ownos/own.py')
        self.put('boot/vmlinuz-linux', 'kernel payload')
        self.put('usr/lib/modules/6.18.1-arch1-1/modules.dep', 'kernel/drivers/test.ko.zst:\n')
        self.put('usr/lib/modules/6.18.1-arch1-1/kernel/drivers/test.ko.zst', 'module payload')
        self.put('usr/lib/firmware/amdgpu/test.bin.zst', 'firmware payload')
        self.put('usr/share/wayland-sessions/ownos-wayland.desktop', '[Desktop Entry]\nExec=/usr/bin/husk-session\n')
        self.put('etc/ownos/labwc/rc.xml', '<labwc_config/>\n')
        self.put('etc/ownos/labwc/environment', 'XDG_SESSION_TYPE=wayland\n')
        self.put('etc/ownos/labwc/autostart', '#!/bin/sh\nhusk-desktop &\n', 0o755)
        self.put('usr/lib/libgtk-3.so.0.2400.49', 'GTK payload')
        (self.root / 'usr/lib/libgtk-3.so.0').symlink_to('libgtk-3.so.0.2400.49')
        self.put('usr/lib/libgtk-layer-shell.so.0', 'layer shell payload')
        self.put('usr/lib/girepository-1.0/Gtk-3.0.typelib', 'GTK typelib')
        self.put('usr/lib/girepository-1.0/GtkLayerShell-0.1.typelib', 'layer shell typelib')
        self.put('usr/lib/python3.14/site-packages/gi/__init__.py', '# PyGObject\n')
        self.put('usr/lib/ownos/ownos/ui/shell.py', '# Husk Desktop\n')

    def put(self, name, content, mode=0o644):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(mode)
        return path

    def test_complete_payload_resolves_guest_absolute_and_relative_symlinks(self):
        self.assertEqual(validate_rootfs(self.root), [])
        self.assertEqual(guest_path(self.root, 'usr/bin/husk-session'), self.root / 'usr/bin/own-session')
        self.assertEqual(guest_path(self.root, '/usr/bin/husk-desktop'), self.root / 'usr/lib/ownos/own.py')

    def test_kernel_can_live_in_its_module_directory(self):
        (self.root / 'boot/vmlinuz-linux').unlink()
        self.put('usr/lib/modules/6.18.1-arch1-1/vmlinuz', 'kernel payload')
        self.assertEqual(validate_rootfs(self.root), [])

    def test_post_mkarchiso_check_uses_relocated_boot_payload(self):
        (self.root / 'boot/vmlinuz-linux').unlink()
        boot = self.root.parent / 'boot'
        boot.mkdir()
        (boot / 'vmlinuz-linux').write_text('relocated kernel payload')
        (boot / 'initramfs-linux.img').write_text('relocated initramfs payload')
        self.assertEqual(validate_rootfs(self.root, boot=boot), [])
        (boot / 'initramfs-linux.img').unlink()
        self.assertTrue(any('initramfs' in error for error in validate_rootfs(self.root, boot=boot)))

    def test_command_emits_json_and_returns_failure_for_missing_payload(self):
        checker = Path(__file__).resolve().parents[1] / 'scripts/check-rootfs.py'
        result = subprocess.run([sys.executable, str(checker), str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'PASS')
        (self.root / 'usr/bin/own-toplevel').unlink()
        result = subprocess.run([sys.executable, str(checker), str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(any('own-toplevel' in error for error in json.loads(result.stdout)['problems']))

    def test_kernel_modules_and_firmware_need_actual_payload(self):
        (self.root / 'boot/vmlinuz-linux').unlink()
        (self.root / 'usr/lib/modules/6.18.1-arch1-1/kernel/drivers/test.ko.zst').unlink()
        (self.root / 'usr/lib/firmware/amdgpu/test.bin.zst').unlink()
        errors = validate_rootfs(self.root)
        for required in ('kernel image', 'kernel modules', 'firmware'):
            self.assertTrue(any(required in error.lower() for error in errors), errors)

    def test_session_binaries_must_be_executable_and_gtk_must_be_installed(self):
        (self.root / 'usr/bin/labwc').chmod(0o644)
        (self.root / 'usr/lib/libgtk-3.so.0.2400.49').unlink()
        errors = validate_rootfs(self.root)
        self.assertTrue(any('labwc' in error and 'executable' in error for error in errors), errors)
        self.assertTrue(any('libgtk-3.so.0' in error for error in errors), errors)

    def test_an_absolute_link_to_a_real_host_file_is_not_accepted(self):
        external = Path(self.tmp.name) / 'host-session'
        external.write_text('host executable')
        external.chmod(0o755)
        session = self.root / 'usr/bin/husk-session'
        session.unlink()
        session.symlink_to(external)
        errors = validate_rootfs(self.root)
        self.assertTrue(any('husk-session' in error for error in errors), errors)
        self.assertEqual(external.read_text(), 'host executable')

    def test_parent_directory_links_also_resolve_inside_guest(self):
        (self.root / 'bin').symlink_to('/usr/bin')
        self.assertEqual(guest_path(self.root, '/bin/husk-session'), self.root / 'usr/bin/own-session')

    def test_escaping_relative_links_and_link_loops_are_reported(self):
        session = self.root / 'usr/bin/husk-session'
        session.unlink()
        session.symlink_to('../../../../host-session')
        self.assertTrue(any('husk-session' in error for error in validate_rootfs(self.root)))
        session.unlink()
        session.symlink_to('husk-session')
        self.assertTrue(any('husk-session' in error for error in validate_rootfs(self.root)))


if __name__ == '__main__':
    unittest.main()
