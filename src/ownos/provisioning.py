"""Calamares target configuration; privileged commands always run in its chroot."""
import subprocess
from ownos.installer import installation_plan, validate_target
from ownos.build import safe_path, write

CLEANUP = ('etc/sddm.conf.d/ownos-live.conf',
           'etc/profile.d/husk-live-session.sh',
           'etc/systemd/system/getty@tty1.service.d/husk-live.conf',
           'etc/systemd/system/getty.target.wants/getty@tty1.service',
           'etc/systemd/system/sddm.service.d/husk-live.conf',
           'etc/polkit-1/rules.d/49-ownos-live.rules',
           'etc/systemd/system/ownos-live-setup.service',
           'etc/systemd/system/ownos-live-keyring.service',
           'etc/systemd/system/etc-pacman.d-gnupg.mount',
           'etc/systemd/system/multi-user.target.wants/ownos-live-keyring.service',
           'etc/systemd/system/multi-user.target.wants/ownos-live-setup.service',
           'etc/systemd/system/getty@tty1.service.d/autologin.conf',
           'etc/systemd/system/getty@tty2.service.d/husk-live.conf',
           'etc/systemd/system/getty.target.wants/getty@tty2.service',
           'etc/systemd/system/display-manager.service')


def configure_target(root, desktop, graphics, run=None):
    plan = installation_plan(desktop, graphics)
    root = validate_target(root)
    # Validate file edits before running any package transaction. Final symlinks
    # to systemd units are unlinked themselves; their parents must stay in root.
    targets = []
    for relative in CLEANUP:
        target = root / relative
        safe_path(root, str(target.parent.relative_to(root)))
        targets.append(target)
    if run is None:
        def run(argv):
            result = subprocess.run(['/usr/bin/arch-chroot', str(root), *argv],
                                    check=True, text=True, capture_output=True)
            return result.stdout
    run(['/usr/bin/pacman-key', '--init'])
    run(['/usr/bin/pacman-key', '--populate', 'archlinux', 'ownos'])
    run(['/usr/bin/pacman', '-Syu', '--needed', '--noconfirm', *plan.packages])
    installed = set(run(['/usr/bin/pacman', '-Qq']).splitlines())
    removals = [p for p in plan.remove if p in installed]
    if removals:
        run(['/usr/bin/pacman', '-Rns', '--noconfirm', *removals])
    for target in targets:
        if target.is_symlink() or target.is_file(): target.unlink()
    if any(line.split(':')[0] == 'live' for line in safe_path(root, 'etc/passwd').read_text().splitlines()):
        run(['/usr/bin/userdel', '--remove', 'live'])
    run(['/usr/bin/passwd', '--lock', 'root'])
    # Releng's live initramfs hooks/presets must never survive installation.
    for relative in ('etc/mkinitcpio.conf.d/archiso.conf', 'etc/mkinitcpio.conf.d/archiso-session.conf'):
        target = safe_path(root, relative)
        if target.exists(): target.unlink()
    write(root, 'etc/mkinitcpio.conf', 'MODULES=()\nBINARIES=()\nFILES=()\nHOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck)\n')
    write(root, 'etc/mkinitcpio.d/linux.preset', '''ALL_config="/etc/mkinitcpio.conf"
ALL_kver="/boot/vmlinuz-linux"
PRESETS=('default' 'fallback')
default_image="/boot/initramfs-linux.img"
fallback_image="/boot/initramfs-linux-fallback.img"
fallback_options="-S autodetect"
''')
    # Reinstall from the already fully upgraded sync database to restore kernel
    # payloads that the live profile may have relocated. No database refresh.
    run(['/usr/bin/pacman', '-S', '--noconfirm', 'linux'])
    run(['/usr/bin/systemctl', 'enable', 'NetworkManager.service'])
    if plan.display_manager:
        run(['/usr/bin/systemctl', 'enable', plan.display_manager + '.service'])
        run(['/usr/bin/systemctl', 'set-default', 'graphical.target'])
    else:
        run(['/usr/bin/systemctl', 'set-default', 'multi-user.target'])
    branding = safe_path(root, 'usr/share/ownos/os-release')
    if branding.is_file():
        release = root / 'etc/os-release'
        safe_path(root, 'etc')
        if release.is_symlink(): release.unlink()
        release.write_text(branding.read_text())
    return plan
