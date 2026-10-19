"""Inspect installed V3 payload fixtures without executing their programs."""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SHOW = ['welcome', 'keyboard', 'locale', 'partition', 'users', 'summary']
JOBS = ['partition', 'mount', 'unpackfs', 'machineid', 'fstab', 'locale',
        'keyboard', 'localecfg', 'users', 'owninstall', 'initcpio',
        'bootloader', 'huskflush', 'umount', 'husksync']
PYTHON_JOBS = {'mount', 'unpackfs', 'fstab', 'localecfg', 'bootloader',
               'owninstall', 'huskflush', 'husksync'}


class V3RootfsTests(unittest.TestCase):
    def setUp(self):
        try:
            self.validator = importlib.import_module('ownos.v3_rootfs').validate_v3_rootfs
        except ImportError as exc:
            self.fail('V3 installed-payload validation is missing: ' + str(exc))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'airootfs'
        self.root.mkdir()
        self.boot = self.root.parent / 'iso-boot'
        self.boot.mkdir()
        (self.boot / 'vmlinuz-linux').write_bytes(b'fixture kernel')
        (self.boot / 'initramfs-linux.img').write_bytes(b'fixture initramfs')
        for name in ('calamares', 'husk-install', 'pkexec', 'lsblk', 'findmnt',
                     'arch-chroot', 'mkinitcpio', 'grub-install', 'grub-mkconfig',
                     'efibootmgr', 'rsync', 'sync', 'pacman', 'pacman-key',
                     'passwd', 'systemctl', 'wpa_supplicant', 'nm-connection-editor',
                     'blueman-manager', 'bluetoothctl', 'xauth'):
            self.put('usr/bin/' + name, '#!/bin/sh\nexit 0\n', 0o755)
        for name in ('husk-install-guard', 'husk-installer-root'):
            self.put('usr/lib/ownos/' + name, '#!/bin/sh\nexit 0\n', 0o755)
        self.put('usr/lib/ownos/husk-installer-root', (ROOT/'bin/husk-installer-root').read_text(), 0o755)
        self.put('usr/lib/bluetooth/bluetoothd', '#!/bin/sh\nexit 0\n', 0o755)
        for name in ('installer_safety', 'installer_display', 'provisioning', 'live_password', 'network', 'bluetooth'):
            self.put('usr/lib/ownos/ownos/' + name + '.py', '# installed fixture module\n')
        for name in ('installer', 'network', 'bluetooth'):
            self.put('usr/lib/ownos/ownos/ui/' + name + '.py', '# installed GTK fixture module\n')
        for name in ('libcalamares.so', 'libcalamaresui.so', 'libnm.so.0'):
            self.put('usr/lib/' + name + '.1', 'shared library fixture')
            (self.root / 'usr/lib' / name).symlink_to(name + '.1')
        self.put('usr/lib/qt6/plugins/platforms/libqxcb.so', 'Qt platform fixture')
        self.put('usr/share/calamares/qml/calamares/slideshow/qmldir', 'module calamares.slideshow\n')
        self.put('usr/lib/girepository-1.0/NM-1.0.typelib', 'NM introspection fixture')
        self.put('etc/os-release', 'NAME="Husk OS"\nID=huskos\nVERSION_ID=v3-phase2\nBUILD_ID=v3-phase2\n')
        self.put('etc/locale.conf', 'LANG=en_US.UTF-8\n')
        self.put('etc/NetworkManager/conf.d/husk-network.conf', '[main]\ndns=default\nrc-manager=symlink\ndhcp=internal\n')
        self.put('etc/NetworkManager/conf.d/husk-wifi.conf', '[device]\nwifi.backend=wpa_supplicant\n')
        (self.root / 'etc/resolv.conf').symlink_to('/run/NetworkManager/resolv.conf')
        for name in ('NetworkManager', 'bluetooth'):
            self.put('usr/lib/systemd/system/' + name + '.service', '[Service]\nExecStart=/usr/bin/fixture\n')
            link = self.root / 'etc/systemd/system/multi-user.target.wants' / (name + '.service')
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to('/usr/lib/systemd/system/' + name + '.service')
        self.put_yaml('etc/calamares/settings.conf', {
            'modules-search': ['local'], 'branding': 'ownos', 'prompt-install': True,
            'dont-chroot': False, 'disable-cancel-during-exec': True,
            'hide-back-and-next-during-exec': True,
            'sequence': [{'show': SHOW}, {'exec': JOBS}, {'show': ['finishedq']}],
        })
        for name in set(SHOW + JOBS + ['finishedq']):
            directory = 'usr/lib/calamares/modules/' + name + '/'
            if name in PYTHON_JOBS:
                descriptor = {'name': name, 'type': 'job', 'interface': 'python', 'script': 'main.py'}
                self.put(directory + 'main.py', 'def run():\n    return None\n')
            else:
                module_type = 'viewmodule' if name in SHOW + ['finishedq'] else 'job'
                library = f'libcalamares_{module_type}_{name}.so'
                descriptor = {'name': name, 'type': module_type, 'interface': 'qtplugin', 'load': library}
                self.put(directory + library, 'installed plugin fixture')
            self.put_yaml(directory + 'module.desc', descriptor)
            self.put_yaml('etc/calamares/modules/' + name + '.conf', {})
        self.put_yaml('etc/calamares/modules/partition.conf', {
            'initialPartitioningChoice': 'none', 'allowManualPartitioning': False,
            'enableLuksAutomatedPartitioning': False, 'lvm': {'enable': False},
        })
        self.put_yaml('etc/calamares/modules/unpackfs.conf', {'unpack': [{
            'source': '/run/archiso/bootmnt/arch/x86_64/airootfs.sfs',
            'sourcefs': 'squashfs', 'destination': '',
        }]})
        self.put_yaml('etc/calamares/modules/bootloader.conf', {'efiBootLoader': 'grub', 'installEFIFallback': True})
        self.put_yaml('etc/calamares/modules/initcpio.conf', {'kernel': 'all', 'be_unsafe': False})
        self.put_yaml('etc/calamares/modules/finishedq.conf', {
            'restartNowMode': 'user-unchecked',
            'restartNowCommand': '/usr/bin/sync && /usr/bin/systemctl reboot',
        })
        self.put_yaml('etc/calamares/modules/welcome.conf', {'requirements': {'required': ['storage', 'ram', 'root']}})
        self.put_yaml('etc/calamares/modules/locale.conf', {'adjustLiveTimezone': False, 'geoip': {'style': 'none'}})
        self.put_yaml('etc/calamares/branding/ownos/branding.desc', {
            'componentName': 'ownos', 'strings': {'productName': 'Husk OS', 'version': 'V3 Phase 2'},
        })
        self.put('etc/calamares/husk.qss', 'QWidget { color: white; }')
        self.policy = self.put('usr/share/polkit-1/actions/org.ownos.install.policy', '''<policyconfig>
<action id="org.ownos.install"><defaults><allow_any>no</allow_any><allow_inactive>no</allow_inactive><allow_active>auth_admin</allow_active></defaults>
<annotate key="org.freedesktop.policykit.exec.path">/usr/lib/ownos/husk-installer-root</annotate>
<annotate key="org.freedesktop.policykit.exec.allow_gui">true</annotate></action></policyconfig>''')
        self.put('etc/polkit-1/rules.d/49-ownos-live.rules', '// Installed Live administrator identity rule\n')
        self.launcher = self.put('usr/share/applications/org.ownos.Install.desktop',
            '[Desktop Entry]\nType=Application\nName=Install Husk OS\nExec=/usr/bin/husk-install\nTryExec=/usr/bin/husk-install\nIcon=husk-install\nTerminal=false\n')
        icon = self.put('usr/share/icons/hicolor/128x128/apps/husk-install.png', 'replace with supplied icon')
        icon.write_bytes((ROOT / 'installer/husk-install.png').read_bytes())
        for package in ('ownos-core', 'ownos-ui', 'ownos-desktop', 'ownos-live', 'calamares',
                        'networkmanager', 'wpa_supplicant', 'bluez', 'bluez-utils', 'blueman', 'linux-firmware'):
            self.package(package, '3.3.14-2' if package == 'calamares' else '1-1')
        self.put('var/lib/pacman/local/ownos-live-1-1/files', '%FILES%\nusr/share/applications/org.ownos.Install.desktop\nusr/bin/husk-install\n')

    def put(self, relative, content, mode=0o644):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        path.chmod(mode)
        return path

    def put_yaml(self, relative, value):
        return self.put(relative, yaml.safe_dump(value))

    def package(self, name, version='1-1'):
        return self.put(f'var/lib/pacman/local/{name}-1-1/desc', f'%NAME%\n{name}\n\n%VERSION%\n{version}\n\n')

    def errors(self):
        return self.validator(self.root, boot=self.boot)

    def test_complete_installed_payload_resolves_guest_libraries_and_enabled_services(self):
        self.assertEqual(self.errors(), [])

    def test_missing_installer_plugin_or_python_job_is_an_error(self):
        for relative in ('usr/lib/calamares/modules/partition/libcalamares_viewmodule_partition.so',
                         'usr/lib/calamares/modules/owninstall/main.py'):
            with self.subTest(relative=relative):
                path = self.root / relative
                data = path.read_bytes()
                path.unlink()
                self.assertTrue(any(relative in message for message in self.errors()))
                path.write_bytes(data)

    def test_missing_qml_or_secure_display_support_is_an_error(self):
        for relative in ('usr/share/calamares/qml/calamares/slideshow/qmldir',
                         'usr/lib/ownos/ownos/installer_display.py', 'usr/bin/xauth'):
            with self.subTest(relative=relative):
                path = self.put(relative, 'present fixture', 0o755 if relative.endswith('/xauth') else 0o644)
                path.unlink()
                self.assertTrue(any(relative in message for message in self.errors()))

    def test_test_only_config_override_that_hides_installed_qml_is_rejected(self):
        self.put('usr/lib/ownos/husk-installer-root', '#!/bin/sh\nexec /usr/bin/calamares -c /etc/calamares\n', 0o755)
        self.assertTrue(any('data directories' in message for message in self.errors()))

    def test_installer_cannot_assume_a_generated_live_english_locale(self):
        wrapper=(ROOT/'bin/husk-installer-root').read_text().replace('C.UTF-8','en_US.UTF-8')
        self.put('usr/lib/ownos/husk-installer-root',wrapper,0o755)
        self.assertTrue(any('built-in English UTF-8' in message for message in self.errors()))

    def test_changed_nonempty_installer_icon_is_rejected(self):
        self.put('usr/share/icons/hicolor/128x128/apps/husk-install.png', 'different image bytes')
        self.assertTrue(any('icon' in message.lower() and 'checksum' in message.lower() for message in self.errors()))

    def test_resolved_stub_symlink_is_rejected_for_networkmanager_dns(self):
        resolver = self.root / 'etc/resolv.conf'
        resolver.unlink()
        resolver.symlink_to('/run/systemd/resolve/stub-resolv.conf')
        self.assertTrue(any('resolv.conf' in message for message in self.errors()))

    def test_missing_enabled_service_and_nm_typelib_fail(self):
        for relative in ('etc/systemd/system/multi-user.target.wants/bluetooth.service',
                         'usr/lib/girepository-1.0/NM-1.0.typelib'):
            with self.subTest(relative=relative):
                path = self.root / relative
                backup = path.readlink() if path.is_symlink() else path.read_bytes()
                path.unlink()
                self.assertTrue(any(relative in message for message in self.errors()))
                path.symlink_to(backup) if isinstance(backup, Path) else path.write_bytes(backup)

    def test_missing_firmware_package_is_not_hidden_by_a_misleading_directory_name(self):
        self.package('linux-firmware', '1-1').write_text('%NAME%\nbase\n\n%VERSION%\n1-1\n')
        self.assertTrue(any('linux-firmware' in message for message in self.errors()))

    def test_install_launcher_must_be_owned_by_the_removable_live_package(self):
        self.put('var/lib/pacman/local/ownos-live-1-1/files', '%FILES%\nusr/bin/husk-install\n')
        self.put('var/lib/pacman/local/ownos-ui-1-1/files', '%FILES%\nusr/share/applications/org.ownos.Install.desktop\n')
        self.assertTrue(any('Live-only launcher' in message for message in self.errors()))

    def test_unsafe_policy_and_nonexecutable_wrapper_fail(self):
        self.policy.write_text(self.policy.read_text().replace('auth_admin', 'yes'))
        (self.root / 'usr/lib/ownos/husk-installer-root').chmod(0o644)
        errors = self.errors()
        self.assertTrue(any('polkit' in message.lower() for message in errors))
        self.assertTrue(any('husk-installer-root' in message and 'executable' in message for message in errors))

    def test_missing_flush_job_and_internet_required_would_break_offline_installation(self):
        path = self.root / 'etc/calamares/settings.conf'
        settings = yaml.safe_load(path.read_text())
        settings['sequence'][1]['exec'].remove('huskflush')
        path.write_text(yaml.safe_dump(settings))
        self.put_yaml('etc/calamares/modules/welcome.conf', {'requirements': {'required': ['internet']}})
        errors = self.errors()
        self.assertTrue(any('job sequence' in message for message in errors))
        self.assertTrue(any('offline' in message.lower() for message in errors))

    def test_system2_identity_and_nonenglish_live_locale_are_rejected(self):
        self.put('etc/os-release', 'NAME="Husk OS"\nID=huskos\nVERSION_ID=system-2\n')
        self.put('etc/locale.conf', 'LANG=fi_FI.UTF-8\n')
        errors = self.errors()
        self.assertTrue(any('V3' in message and 'version' in message for message in errors))
        self.assertTrue(any('English' in message for message in errors))

    def test_standard_c_utf8_live_locale_is_english_but_category_overrides_are_checked(self):
        self.put('etc/locale.conf','LANG=C.UTF-8\n')
        self.assertEqual(self.errors(),[])
        self.put('etc/locale.conf','LANG=C.UTF-8\nLC_MESSAGES=fi_FI.UTF-8\n')
        self.assertTrue(any('English' in message for message in self.errors()))

    def test_host_symlink_cannot_supply_a_missing_installer_and_guest_code_never_runs(self):
        marker = Path(self.tmp.name) / 'executed'
        host_program = Path(self.tmp.name) / 'host-installer'
        host_program.write_text('#!/bin/sh\ntouch ' + str(marker) + '\n')
        host_program.chmod(0o755)
        executable = self.root / 'usr/bin/calamares'
        executable.unlink()
        executable.symlink_to(host_program)
        errors = self.errors()
        self.assertTrue(any('usr/bin/calamares' in message for message in errors))
        self.assertFalse(marker.exists())

    def test_command_reports_artifact_scope_and_missing_external_boot_payload(self):
        checker = ROOT / 'scripts/check-v3-rootfs.py'
        self.assertTrue(checker.is_file(), 'V3 artifact checker command is missing')
        result = subprocess.run([sys.executable, str(checker), str(self.root), '--boot', str(self.boot)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['proof_scope'], 'artifact-payloads-only')
        (self.boot / 'vmlinuz-linux').unlink()
        result = subprocess.run([sys.executable, str(checker), str(self.root), '--boot', str(self.boot)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(any('vmlinuz-linux' in message for message in json.loads(result.stdout)['problems']))


if __name__ == '__main__':
    unittest.main()
