"""Calamares target configuration; privileged commands always run in its chroot."""
import subprocess
import shutil
from pathlib import Path
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


def flush_target(root, run=None):
    """Report writeback errors with syncfs before normal, checked unmount."""
    root=validate_target(root)
    if run is None:
        def run(argv):
            subprocess.run(argv,check=True,capture_output=True,text=True,timeout=120)
    efi=safe_path(root,'boot/efi')
    if efi.is_mount(): run(['/usr/bin/sync','-f',str(efi)])
    run(['/usr/bin/sync','-f',str(root)])


def configure_cloned_target(root, run=None, kernel_source=None):
    """Install the verified Live payload offline, retaining its signed packages.

    Calamares has already mounted/copied the target and created the account.
    Never refresh repositories or upgrade the cloned filesystem mid-install.
    The running Live ISO supplies the kernel matching its module payload.
    Calamares's subsequent initcpio and bootloader jobs must still succeed.
    """
    root = validate_target(root)
    if run is None:
        def run(argv):
            return subprocess.run(['/usr/bin/arch-chroot',str(root),*argv],
                check=True,text=True,capture_output=True).stdout
    installed = set(run(['/usr/bin/pacman','-Qq']).splitlines())
    essential = {'ownos-core','ownos-ui','ownos-desktop','linux','networkmanager','bluez','sddm'}
    if essential - installed:
        raise ValueError('The cloned image is missing essential packages: ' + ', '.join(sorted(essential-installed)))
    kernel = Path(kernel_source) if kernel_source else Path('/run/archiso/bootmnt/arch/boot/x86_64/vmlinuz-linux')
    if not kernel.is_file() or kernel.is_symlink() or not kernel.stat().st_size:
        raise ValueError('The matching Live ISO kernel is missing; boot setup was stopped.')
    # Validate paths before any changes or chroot operations.
    for relative in CLEANUP:
        safe_path(root, str((root/relative).parent.relative_to(root)))
    target_kernel = safe_path(root,'boot/vmlinuz-linux')
    target_kernel.parent.mkdir(parents=True,exist_ok=True)
    if target_kernel.is_symlink(): target_kernel.unlink()
    shutil.copyfile(kernel,target_kernel)
    for relative in CLEANUP:
        target = root / relative
        if target.is_symlink() or target.is_file(): target.unlink()
    for relative in ('etc/mkinitcpio.conf.d/archiso.conf','etc/mkinitcpio.conf.d/archiso-session.conf'):
        target = safe_path(root,relative)
        if target.is_file(): target.unlink()
    write(root,'etc/mkinitcpio.conf','MODULES=()\nBINARIES=()\nFILES=()\nHOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck)\n')
    write(root,'etc/mkinitcpio.d/linux.preset', 'ALL_config="/etc/mkinitcpio.conf"\nALL_kver="/boot/vmlinuz-linux"\nPRESETS=(\'default\' \'fallback\')\ndefault_image="/boot/initramfs-linux.img"\nfallback_image="/boot/initramfs-linux-fallback.img"\nfallback_options="-S autodetect"\n')
    write(root,'etc/locale.conf','LANG=en_US.UTF-8\n')
    write(root,'etc/NetworkManager/conf.d/husk-network.conf',
        '[main]\ndns=default\nrc-manager=symlink\ndhcp=internal\n\n[device]\nwifi.backend=wpa_supplicant\n')
    resolver = root/'etc/resolv.conf'
    if resolver.is_symlink() or resolver.is_file(): resolver.unlink()
    resolver.symlink_to('/run/NetworkManager/resolv.conf')
    if any(line.startswith('live:') for line in safe_path(root,'etc/passwd').read_text().splitlines()):
        run(['/usr/bin/userdel','--remove','live'])
    run(['/usr/bin/passwd','--lock','root'])
    removals = [name for name in ('ownos-live','calamares','archinstall') if name in installed]
    if removals: run(['/usr/bin/pacman','-R','--noconfirm',*removals])
    run(['/usr/bin/pacman-key','--init'])
    run(['/usr/bin/pacman-key','--populate','archlinux','ownos'])
    for service in ('NetworkManager.service','bluetooth.service','sddm.service'):
        run(['/usr/bin/systemctl','enable',service])
    run(['/usr/bin/systemctl','set-default','graphical.target'])
    return installation_plan('own','mesa')


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
