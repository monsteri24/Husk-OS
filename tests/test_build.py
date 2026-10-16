import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ProfileTests(unittest.TestCase):
    def setUp(self):
        try:
            from ownos import build
            self.build = build
        except ImportError as exc:
            self.fail('Archiso integration is missing: ' + str(exc))
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.releng = self.root / 'releng'; self.releng.mkdir()
        (self.releng / 'airootfs/etc').mkdir(parents=True)
        (self.releng / 'profiledef.sh').write_text("iso_name='archlinux'\ninstall_dir='arch'\nbootmodes=('bios.syslinux' 'uefi.systemd-boot')\nfile_permissions=()\n")
        (self.releng / 'packages.x86_64').write_text('base\nlinux\narchlinux-keyring\n')
        (self.releng / 'bootstrap_packages.x86_64').write_text('base\n')
        self.repo = self.root / 'repo'; self.repo.mkdir()
        for name in ['ownos.db.tar.gz','ownos.db.tar.gz.sig','ownos-core-0.1.0-1-any.pkg.tar.zst',
                     'ownos-core-0.1.0-1-any.pkg.tar.zst.sig']:
            (self.repo / name).write_text('synthetic fixture; not an authenticated package')
        self.key = self.root / 'ownos.gpg'; self.key.write_bytes(b'fixture')

    def generate(self, output=None, **options):
        return self.build.generate_profile(self.releng, self.repo, self.key,
                                           output or self.root / 'profile', Path(__file__).resolve().parents[1], **options)

    def test_first_boot_keeps_desktop_and_64_bit_mesa_without_gaming_additions(self):
        from ownos.installer import GAME_PACKAGES, MESA_PACKAGES
        from ownos.identity import VERSION
        out = self.generate(first_boot=True)
        packages = (out / 'packages.x86_64').read_text().splitlines()
        self.assertTrue(set(self.build.LIVE).issubset(packages))
        self.assertTrue({p for p in MESA_PACKAGES if not p.startswith('lib32-')}.issubset(packages))
        self.assertFalse(set(GAME_PACKAGES).intersection(packages))
        self.assertFalse(any(p.startswith('lib32-') for p in packages))
        metadata = json.loads((out / 'husk-profile.json').read_text())
        self.assertEqual(metadata['edition'], 'first-boot')
        self.assertEqual(metadata['version'], VERSION)
        definition = (out / 'profiledef.sh').read_text()
        self.assertIn('airootfs_image_type="squashfs"', definition)
        self.assertIn('airootfs_image_tool_options=(-comp zstd -Xcompression-level 3 -b 1M -processors 2)', definition)
        self.assertEqual(self.build.validate_profile(out), [])

    def test_default_profile_keeps_gaming_and_upstream_compression(self):
        from ownos.installer import GAME_PACKAGES, MESA_PACKAGES
        with (self.releng / 'profiledef.sh').open('a') as stream:
            stream.write('airootfs_image_tool_options=(-comp zstd -Xcompression-level 15)\n')
        out = self.generate()
        self.assertTrue(set(GAME_PACKAGES + MESA_PACKAGES).issubset((out / 'packages.x86_64').read_text().splitlines()))
        self.assertEqual(json.loads((out / 'husk-profile.json').read_text())['edition'], 'gaming')
        self.assertNotIn('-processors 2', (out / 'profiledef.sh').read_text())

    def test_first_boot_validation_still_requires_mesa_and_rejects_gaming_additions(self):
        out = self.generate(first_boot=True)
        packages = out / 'packages.x86_64'
        packages.write_text(packages.read_text().replace('vulkan-radeon\n', '') + 'steam\nlib32-mesa\n')
        problems = self.build.validate_profile(out)
        self.assertTrue(any('vulkan-radeon' in problem for problem in problems))
        self.assertTrue(any('steam' in problem for problem in problems))
        self.assertTrue(any('lib32-mesa' in problem for problem in problems))

    def test_profile_preserves_upstream_boot_modes_and_bootstrap(self):
        out = self.generate()
        text = (out / 'profiledef.sh').read_text()
        self.assertIn("bootmodes=('bios.syslinux' 'uefi.systemd-boot')", text)
        self.assertEqual((out / 'bootstrap_packages.x86_64').read_text(), 'base\n')
        self.assertIn('ownos-desktop', (out / 'packages.x86_64').read_text())
        self.assertIn('steam-devices', (out / 'packages.x86_64').read_text())

    def test_generated_repositories_require_package_and_local_database_signatures(self):
        out = self.generate()
        for p in [out / 'pacman.conf', out / 'airootfs/etc/pacman.conf']:
            text = p.read_text()
            self.assertIn('SigLevel = Required DatabaseRequired', text)
            self.assertIn('[multilib]', text)
            self.assertNotIn('TrustAll', text)
            self.assertNotIn('SigLevel = Never', text)
        self.assertIn('file:///opt/ownos/repo', (out / 'airootfs/etc/pacman.conf').read_text())

    def test_unsigned_package_or_database_is_rejected(self):
        (self.repo / 'ownos.db.tar.gz.sig').unlink()
        with self.assertRaises(ValueError): self.generate()

    def test_output_never_overwrites_existing_work(self):
        output = self.root / 'profile'; output.mkdir()
        (output / 'important.txt').write_text('keep')
        with self.assertRaises(ValueError): self.generate(output)
        self.assertEqual((output / 'important.txt').read_text(), 'keep')

    def test_symlink_build_output_is_rejected(self):
        link = self.root / 'link'; link.symlink_to(self.root / 'elsewhere')
        with self.assertRaises(ValueError): self.generate(link)

    def test_live_root_autologin_is_removed(self):
        directory = self.releng / 'airootfs/etc/systemd/system/getty@tty1.service.d'
        directory.mkdir(parents=True); (directory / 'autologin.conf').write_text('root')
        out = self.generate()
        self.assertFalse((out / 'airootfs/etc/systemd/system/getty@tty1.service.d/autologin.conf').exists())
        self.assertEqual((out / 'airootfs/etc/os-release').read_text().split('ID=')[1].splitlines()[0], 'huskos')

    def test_live_setup_is_required_before_sddm(self):
        out=self.generate()
        path=out/'airootfs/etc/systemd/system/sddm.service.d/husk-live.conf'
        self.assertTrue(path.is_file())
        text=path.read_text()
        self.assertIn('Requires=ownos-live-setup.service',text)
        self.assertIn('After=ownos-live-setup.service',text)

    def test_live_console_is_available_independently_of_display_manager(self):
        out = self.generate()
        root = out / 'airootfs'
        text = (root / 'etc/systemd/system/getty@tty2.service.d/husk-live.conf').read_text()
        self.assertIn('Requires=ownos-live-setup.service', text)
        self.assertIn('After=ownos-live-setup.service', text)
        self.assertIn('--autologin live', text)
        self.assertNotIn('sddm', text.lower())
        self.assertEqual((root / 'etc/systemd/system/getty.target.wants/getty@tty2.service').readlink(), Path('/usr/lib/systemd/system/getty@.service'))
        sddm = (root / 'etc/sddm.conf.d/ownos-live.conf').read_text()
        for line in ('DisplayServer=x11', 'SessionDir=/usr/share/wayland-sessions',
                     'SessionLogFile=.local/share/sddm/wayland-session.log', 'Relogin=false'):
            self.assertIn(line, sddm)

    def test_clock_sync_and_duplicate_keyring_initializer_do_not_block_live_startup(self):
        units = self.releng / 'airootfs/etc/systemd/system'
        for directory, name in [('sysinit.target.wants', 'systemd-time-wait-sync.service'),
                                ('multi-user.target.wants', 'systemd-time-wait-sync.service'),
                                ('multi-user.target.wants', 'pacman-init.service'),
                                ('sysinit.target.wants', 'systemd-timesyncd.service')]:
            (units / directory).mkdir(parents=True, exist_ok=True)
            (units / directory / name).symlink_to('/usr/lib/systemd/system/' + name)
        out = self.generate()
        units = out / 'airootfs/etc/systemd/system'
        for relative in ('sysinit.target.wants/systemd-time-wait-sync.service',
                         'multi-user.target.wants/systemd-time-wait-sync.service',
                         'multi-user.target.wants/pacman-init.service'):
            self.assertFalse((units / relative).is_symlink())
        self.assertTrue((units / 'sysinit.target.wants/systemd-timesyncd.service').is_symlink())

    def test_keyring_uses_live_only_tmpfs_before_initialization(self):
        out = self.generate()
        units = out / 'airootfs/etc/systemd/system'
        mount = (units / 'etc-pacman.d-gnupg.mount').read_text()
        for line in ('ConditionPathExists=/run/archiso', 'What=tmpfs', 'Where=/etc/pacman.d/gnupg',
                     'Type=tmpfs', 'mode=0755', 'noswap'):
            self.assertIn(line, mount)
        keyring = (units / 'ownos-live-keyring.service').read_text()
        self.assertIn('Requires=etc-pacman.d-gnupg.mount', keyring)
        self.assertIn('After=etc-pacman.d-gnupg.mount', keyring)

    def test_inherited_absolute_release_symlink_is_replaced_without_modifying_host_target(self):
        external = self.root / 'external-release'
        external.write_text('keep this host file')
        (self.releng / 'airootfs/etc/os-release').symlink_to(external)
        out = self.generate()
        self.assertFalse((out / 'airootfs/etc/os-release').is_symlink())
        self.assertEqual(external.read_text(), 'keep this host file')

    def test_actual_boot_templates_have_husk_labels_and_unchanged_kernel_paths(self):
        efi=self.releng/'efiboot/loader/entries';efi.mkdir(parents=True)
        (efi/'01-archiso.conf').write_text('title Arch Linux install medium\nlinux /arch/vmlinuz-linux\noptions archisobasedir=arch\n')
        bios=self.releng/'syslinux';bios.mkdir()
        (bios/'archiso.cfg').write_text('MENU LABEL Arch Linux install medium\nKERNEL /arch/vmlinuz-linux\n')
        grub=self.releng/'grub';grub.mkdir()
        (grub/'grub.cfg').write_text('menuentry "Arch Linux install medium" {\n linux /arch/vmlinuz-linux archisobasedir=arch\n}\n')
        out=self.generate()
        for path in [out/'efiboot/loader/entries/01-archiso.conf',out/'syslinux/archiso.cfg',out/'grub/grub.cfg']:
            self.assertIn('Husk OS live',path.read_text())
            self.assertIn('/arch/vmlinuz-linux',path.read_text())

    def test_profile_check_catches_missing_live_package_and_setup(self):
        out=self.generate()
        self.assertEqual(self.build.validate_profile(out),[])
        packages=out/'packages.x86_64'
        packages.write_text(packages.read_text().replace('ownos-desktop\n',''))
        (out/'airootfs/etc/systemd/system/ownos-live-setup.service').unlink()
        problems=self.build.validate_profile(out)
        self.assertTrue(any('ownos-desktop' in text for text in problems))
        self.assertTrue(any('setup' in text.lower() for text in problems))

    def test_competing_network_socket_is_removed_from_live_profile(self):
        path=self.releng/'airootfs/etc/systemd/system/sockets.target.wants'
        path.mkdir(parents=True)
        (path/'systemd-networkd.socket').symlink_to('/usr/lib/systemd/system/systemd-networkd.socket')
        out=self.generate()
        self.assertFalse((out/'airootfs/etc/systemd/system/sockets.target.wants/systemd-networkd.socket').is_symlink())

    def test_first_live_profile_does_not_require_graphical_installer(self):
        out=self.generate()
        packages=(out/'packages.x86_64').read_text().splitlines()
        self.assertNotIn('calamares',packages)
        for name in ['bluez','bluez-utils','blueman','upower','power-profiles-daemon','pipewire-alsa','pavucontrol','intel-ucode','amd-ucode']:
            self.assertIn(name,packages)
        units=out/'airootfs/etc/systemd/system/multi-user.target.wants'
        self.assertTrue((units/'bluetooth.service').is_symlink())
        self.assertTrue((units/'power-profiles-daemon.service').is_symlink())

    def test_optional_installer_can_be_included_explicitly(self):
        out=self.build.generate_profile(self.releng,self.repo,self.key,self.root/'profile',Path(__file__).resolve().parents[1],with_installer=True)
        self.assertIn('calamares',(out/'packages.x86_64').read_text().splitlines())

    def test_missing_kernel_or_display_service_is_not_a_valid_live_profile(self):
        out=self.generate()
        packages=out/'packages.x86_64'
        packages.write_text(packages.read_text().replace('linux\n',''))
        (out/'airootfs/etc/systemd/system/multi-user.target.wants/NetworkManager.service').unlink()
        errors=self.build.validate_profile(out)
        self.assertTrue(any('linux' in e for e in errors))
        self.assertTrue(any('NetworkManager' in e for e in errors))

    def test_preflight_reports_missing_tools_without_running_them(self):
        problems = self.build.preflight(available=lambda _: None, os_id='ubuntu')
        self.assertTrue(any('Arch' in p for p in problems))
        self.assertTrue(any('mkarchiso' in p for p in problems))


class InstallerIntegrationTests(unittest.TestCase):
    def setUp(self):
        try:
            from ownos import provisioning
            self.provision = provisioning
        except ImportError as exc:
            self.fail('Installer execution/cleanup is missing: ' + str(exc))
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'etc/sddm.conf.d').mkdir(parents=True)
        (self.root / 'etc/sddm.conf.d/ownos-live.conf').write_text('autologin')
        (self.root / 'etc/shadow').write_text('root::1:0:99999:7:::\nlive::1:0:99999:7:::\n')
        (self.root / 'etc/passwd').write_text('root:x:0:0:root:/root:/bin/bash\nlive:x:1000:1000:Live:/home/live:/bin/bash\n')

    def run_install(self, desktop):
        commands = []
        def run(argv):
            commands.append(argv)
            return 'ownos-live\ncalamares\narchinstall\nownos-desktop\nsddm\n'
        with patch('ownos.provisioning.validate_target', return_value=self.root):
            self.provision.configure_target(str(self.root), desktop, 'mesa', run=run)
        return commands

    def test_each_desktop_cleans_live_login_and_uses_full_upgrade(self):
        for desktop, manager in [('own','sddm'),('kde','sddm'),('gnome','gdm'),('minimal',None)]:
            with self.subTest(desktop=desktop):
                (self.root / 'etc/sddm.conf.d/ownos-live.conf').write_text('autologin')
                dropin=self.root/'etc/systemd/system/sddm.service.d/husk-live.conf'
                dropin.parent.mkdir(parents=True,exist_ok=True);dropin.write_text('Requires=ownos-live-setup.service')
                for relative in ('etc/systemd/system/etc-pacman.d-gnupg.mount',
                                 'etc/systemd/system/getty@tty2.service.d/husk-live.conf'):
                    live_file = self.root / relative
                    live_file.parent.mkdir(parents=True, exist_ok=True)
                    live_file.write_text('live only')
                tty = self.root / 'etc/systemd/system/getty.target.wants/getty@tty2.service'
                tty.parent.mkdir(parents=True, exist_ok=True)
                tty.symlink_to('/usr/lib/systemd/system/getty@.service')
                commands = self.run_install(desktop)
                self.assertFalse((self.root / 'etc/sddm.conf.d/ownos-live.conf').exists())
                self.assertFalse(dropin.exists())
                self.assertFalse((self.root / 'etc/systemd/system/etc-pacman.d-gnupg.mount').exists())
                self.assertFalse((self.root / 'etc/systemd/system/getty@tty2.service.d/husk-live.conf').exists())
                self.assertFalse(tty.is_symlink())
                self.assertIn(['/usr/bin/passwd','--lock','root'], commands)
                self.assertTrue(any(c[:3] == ['/usr/bin/pacman','-Syu','--needed'] for c in commands))
                if manager: self.assertIn(['/usr/bin/systemctl','enable',manager+'.service'], commands)
                else: self.assertIn(['/usr/bin/systemctl','set-default','multi-user.target'], commands)
                self.assertNotIn('ownos-live.conf', json.dumps(commands))

    def test_hostile_choice_cannot_run_a_command(self):
        commands = []
        with patch('ownos.provisioning.validate_target', return_value=self.root), self.assertRaises(ValueError):
            self.provision.configure_target(str(self.root), 'own;reboot', 'mesa', run=lambda argv: commands.append(argv))
        self.assertEqual(commands, [])

    def test_installed_system_uses_regular_kernel_presets(self):
        (self.root / 'etc/mkinitcpio.conf.d').mkdir()
        (self.root / 'etc/mkinitcpio.conf.d/archiso.conf').write_text('HOOKS=(archiso)')
        self.run_install('minimal')
        self.assertFalse((self.root / 'etc/mkinitcpio.conf.d/archiso.conf').exists())
        self.assertIn("PRESETS=('default' 'fallback')", (self.root / 'etc/mkinitcpio.d/linux.preset').read_text())
        self.assertNotIn('archiso', (self.root / 'etc/mkinitcpio.conf').read_text())

    def test_cleanup_refuses_path_through_symlink_to_host(self):
        external = self.root / 'external'; external.mkdir()
        (external / 'ownos-live.conf').write_text('keep')
        (self.root / 'etc/sddm.conf.d/ownos-live.conf').unlink()
        (self.root / 'etc/sddm.conf.d').rmdir()
        (self.root / 'etc/sddm.conf.d').symlink_to(external)
        outside = Path(self.tmp.name + '-outside')
        # An actual escape, rather than an internal symlink.
        outside.mkdir(); self.addCleanup(outside.rmdir)
        (self.root / 'etc/sddm.conf.d').unlink()
        (self.root / 'etc/sddm.conf.d').symlink_to(outside)
        with patch('ownos.provisioning.validate_target', return_value=self.root), self.assertRaises(ValueError):
            self.provision.configure_target(str(self.root), 'kde', 'mesa', run=lambda _: '')


if __name__ == '__main__': unittest.main()
