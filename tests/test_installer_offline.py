import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ownos import provisioning


class OfflineTargetTests(unittest.TestCase):
    def test_flush_targets_each_real_filesystem_and_propagates_io_error(self):
        self.assertTrue(hasattr(provisioning,'flush_target'),'Checked filesystem synchronization is missing')
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'boot/efi').mkdir(parents=True)
            calls=[]
            with patch.object(provisioning,'validate_target',return_value=root), patch.object(Path,'is_mount',return_value=True):
                provisioning.flush_target(root,run=lambda argv:calls.append(argv))
                self.assertEqual(calls,[['/usr/bin/sync','-f',str(root/'boot/efi')],['/usr/bin/sync','-f',str(root)]])
                with self.assertRaises(subprocess.CalledProcessError):
                    provisioning.flush_target(root,run=lambda argv:(_ for _ in ()).throw(subprocess.CalledProcessError(1,argv)))

    def test_cloned_target_has_kernel_and_services_without_network_transaction(self):
        self.assertTrue(hasattr(provisioning,'configure_cloned_target'), 'Offline cloned-image setup is missing')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'target'; root.mkdir()
            (root/'etc').mkdir(); (root/'etc/passwd').write_text('live:x:1000:1000::/home/live:/bin/bash\n')
            kernel = Path(tmp)/'kernel'; kernel.write_bytes(b'disposable-kernel-fixture')
            calls=[]
            def run(argv):
                calls.append(argv)
                if argv == ['/usr/bin/pacman','-Qq']: return 'ownos-core\nownos-ui\nownos-desktop\nlinux\nnetworkmanager\nbluez\nsddm\ncalamares\nownos-live\n'
                return ''
            with patch.object(provisioning,'validate_target',return_value=root):
                provisioning.configure_cloned_target(root,run=run,kernel_source=kernel,
                    keyboard={'layout':'ch','variant':'fr'})
            self.assertEqual((root/'boot/vmlinuz-linux').read_bytes(),kernel.read_bytes())
            self.assertTrue((root/'etc/resolv.conf').is_symlink())
            self.assertEqual(str((root/'etc/resolv.conf').readlink()),'/run/NetworkManager/resolv.conf')
            self.assertIn(['/usr/bin/systemctl','enable','bluetooth.service'],calls)
            self.assertIn(['/usr/bin/systemctl','enable','sddm.service'],calls)
            self.assertFalse(any(a[0] == '/usr/bin/pacman' and any(x.startswith('-S') for x in a) for a in calls))
            self.assertIn('LANG=en_US.UTF-8',(root/'etc/locale.conf').read_text())
            self.assertIn('filesystems fsck',(root/'etc/mkinitcpio.conf').read_text())
            import json
            keyboard = root/'etc/ownos/keyboard.json'
            self.assertEqual(json.loads(keyboard.read_text()), {'layout':'ch','variant':'fr'})
            self.assertEqual(keyboard.stat().st_mode & 0o777, 0o644)

    def test_invalid_keyboard_fails_before_any_target_edit_or_chroot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); calls=[]
            with patch.object(provisioning,'validate_target',return_value=root):
                with self.assertRaises(ValueError):
                    provisioning.configure_cloned_target(root,run=lambda argv:calls.append(argv),
                        keyboard={'layout':'us\nHOME=/bad','variant':''})
            self.assertEqual(calls,[])
            self.assertEqual(list(root.iterdir()),[])


if __name__ == '__main__': unittest.main()
