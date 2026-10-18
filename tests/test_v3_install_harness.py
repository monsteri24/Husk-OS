"""Acceptance orchestration contracts; these tests never boot or install a VM."""
import importlib.util
import ast
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallHarnessTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'scripts/ci-test-v3-install.py'
        self.assertTrue(path.is_file(), 'The real disposable installation harness is missing')
        spec = importlib.util.spec_from_file_location('v3_install_harness', path)
        self.harness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.harness)

    def test_an_existing_disk_or_symlink_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            disk = directory / 'install-target.qcow2'
            disk.write_bytes(b'preserve-existing-data')
            with self.assertRaises(ValueError):
                self.harness.create_disposable_disk(directory)
            self.assertEqual(disk.read_bytes(), b'preserve-existing-data')
            disk.unlink()
            target = directory / 'other-data'; target.write_bytes(b'preserve-target')
            disk.symlink_to(target)
            with self.assertRaises(ValueError):
                self.harness.create_disposable_disk(directory)
            self.assertEqual(target.read_bytes(), b'preserve-target')

    @unittest.skipUnless(shutil.which('qemu-img'), 'qemu-img is needed for a real sparse-image check')
    def test_a_new_disk_is_qcow2_without_a_backing_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            disk = self.harness.create_disposable_disk(Path(temporary))
            self.assertEqual(disk.name, 'install-target.qcow2')
            self.assertTrue(disk.is_file())
            import json
            info = json.loads(subprocess.check_output(['qemu-img', 'info', '--output=json', str(disk)]))
            self.assertEqual(info['format'], 'qcow2')
            self.assertEqual(info['virtual-size'], 32 * 1024 ** 3)
            self.assertNotIn('backing-filename', info)

    def test_installed_boot_has_no_live_media_or_kernel_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            values = dict(artifacts=directory, disk=directory/'install-target.qcow2',
                          iso=directory/'live.iso', firmware_code=directory/'code.fd',
                          firmware_vars=directory/'vars.fd', kernel=directory/'vmlinuz-linux',
                          initrd=directory/'initramfs-linux.img', iso_label='HUSK_TEST', kvm=False)
            for key in ('disk', 'iso', 'firmware_code', 'firmware_vars', 'kernel', 'initrd'):
                values[key].touch()
            live = self.harness.make_qemu_command('live', **values)
            installed = self.harness.make_qemu_command('installed', **values)
            self.assertIn('-kernel', live)
            self.assertIn('systemd.debug_shell=1', live[live.index('-append') + 1])
            for argument in ('-cdrom', '-kernel', '-initrd', '-append'):
                self.assertNotIn(argument, installed)
            self.assertNotIn(str(values['iso']), installed)
            self.assertTrue(any('serial=HUSK-DISPOSABLE' in item for item in installed))
            with self.assertRaises(ValueError):
                self.harness.make_qemu_command('installed', **dict(values, disk=Path('/dev/vda')))

    def test_installed_evidence_requires_real_user_disk_session_and_version(self):
        valid = dict(phase='installed', uid=1001, user='huskcheck', live=False, uefi=True,
                     debug_shell=False, root_device='/dev/vda2', root_fstype='ext4',
                     optical_media=[], packages=['ownos-core','ownos-ui','ownos-desktop','linux','grub','sddm'],
                     session=dict(Type='wayland', Name='huskcheck', Remote='no'),
                     status=dict(version='v3-phase2', backend='wayland', live=False,
                                 bridge_connected=True, panel_mapped=True, desktop_surfaces=1))
        self.assertEqual(self.harness.validate_installed_report(valid, 'v3-phase2', 'huskcheck'), [])
        for changes in [dict(uid=0), dict(live=True), dict(uefi=False), dict(debug_shell=True),
                        dict(root_device='/dev/sda2'), dict(optical_media=['/dev/sr0']),
                        dict(user='live'), dict(session=dict(Type='tty',Name='huskcheck',Remote='no')),
                        dict(status=dict(valid['status'], version='system-2'))]:
            with self.subTest(changes=changes):
                self.assertTrue(self.harness.validate_installed_report(dict(valid, **changes),
                                                                      'v3-phase2', 'huskcheck'))

    def test_install_success_requires_explicit_confirmation_and_postponed_restart(self):
        events = [dict(event=name) for name in self.harness.REQUIRED_DRIVER_EVENTS]
        valid = dict(phase='installation', success=True, events=events, process_exit=0,
                     restart_postponed=True, offline=True, guard_target_accepted=True,
                     live_medium_rejected=True, target_checks={name:True for name in self.harness.REQUIRED_TARGET_CHECKS})
        self.assertEqual(self.harness.validate_install_report(valid), [])
        missing = [event for event in events if event['event'] != 'confirmation-click']
        self.assertTrue(self.harness.validate_install_report(dict(valid, events=missing)))
        self.assertTrue(self.harness.validate_install_report(dict(valid, restart_postponed=False)))
        self.assertTrue(self.harness.validate_install_report(dict(valid,
            target_checks=dict(valid['target_checks'], initramfs=False))))

    def test_embedded_guest_sources_compile_and_decode_real_proc_environment(self):
        for name in ('GUEST_SETUP','INSTALLED_PROBE'):
            source=getattr(self.harness,name)
            tree=ast.parse(source)
            compile(source,'<'+name+'>','exec')
            separators=[node.args[0].value for node in ast.walk(tree)
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and
                node.func.attr=='split' and node.args and isinstance(node.args[0],ast.Constant)
                and isinstance(node.args[0].value,bytes)]
            self.assertIn(b'\0',separators)

    def test_saved_text_redacts_generated_password_and_upstream_crypt_arguments(self):
        self.assertTrue(hasattr(self.harness,'redact_artifact_text'), 'Evidence redaction is missing')
        password='DisposableGeneratedSecret739'
        crypt='$y$j9T$testSalt123$testHash456abcdefghijklmnop'
        text='Create user huskcheck\npassword='+password+'\nusermod -p '+crypt+' huskcheck\n'
        safe=self.harness.redact_artifact_text(text,password)
        self.assertNotIn(password,safe)
        self.assertNotIn(crypt,safe)
        self.assertIn('Create user huskcheck',safe)


if __name__ == '__main__':
    unittest.main()
