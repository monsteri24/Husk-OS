"""QEMU acceptance runner that attaches only an explicitly named virtual disk."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def validate_disk(path):
    path = Path(path).absolute()
    if path.is_symlink() or path.resolve() != path or path.suffix != '.qcow2':
        raise ValueError('VM disk must be a regular non-symlink .qcow2 file path')
    if ',' in str(path) or '\n' in str(path) or path.is_relative_to('/dev'):
        raise ValueError('Physical devices and QEMU option separators are not accepted')
    if path.exists() and not path.is_file(): raise ValueError('VM disk is not a regular file')
    return path


def qemu_command(iso, disk, code, variables, kvm=False):
    disk = validate_disk(disk)
    for path in (code, variables):
        if ',' in str(path) or '\n' in str(path): raise ValueError('Invalid firmware path')
    return ['qemu-system-x86_64', '-machine', 'q35', '-accel', 'kvm' if kvm else 'tcg',
            '-cpu', 'host' if kvm else 'max', '-m', '4096', '-smp', '4',
            '-drive', 'if=pflash,format=raw,readonly=on,file=' + str(code),
            '-drive', 'if=pflash,format=raw,file=' + str(variables),
            '-drive', 'file=' + str(disk) + ',if=virtio,format=qcow2',
            '-device', 'virtio-vga', '-device', 'qemu-xhci', '-device', 'usb-tablet',
            '-nic', 'user,model=virtio-net-pci', *(['-cdrom', str(iso), '-boot', 'd'] if iso else [])]


def validate_image_info(info):
    if not isinstance(info, dict) or info.get('format') != 'qcow2' or info.get('backing-filename'):
        raise ValueError('Only standalone qcow2 disks without a backing file are accepted')
    specific = info.get('format-specific', {})
    if not isinstance(specific, dict) or not isinstance(specific.get('data', {}), dict):
        raise ValueError('Malformed qcow2 format metadata')
    details = specific.get('data', {})
    if 'data-file' in details or details.get('data-file-raw'):
        raise ValueError('qcow2 external data files are not accepted')


def validate_vars_file(path):
    path = Path(path)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('Firmware variables must be a regular non-symlink file')
    return path


def find_firmware():
    for code, variables in [('/usr/share/edk2/x64/OVMF_CODE.4m.fd','/usr/share/edk2/x64/OVMF_VARS.4m.fd'),
                            ('/usr/share/edk2/x64/OVMF_CODE.fd','/usr/share/edk2/x64/OVMF_VARS.fd'),
                            ('/usr/share/OVMF/OVMF_CODE_4M.fd','/usr/share/OVMF/OVMF_VARS_4M.fd')]:
        if Path(code).is_file() and Path(variables).is_file(): return Path(code), Path(variables)
    return None, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--iso', type=Path)
    parser.add_argument('--disk', type=Path, default=Path('out/huskos-test.qcow2'))
    parser.add_argument('--create-disk', action='store_true', help='Create a NEW 64 GiB qcow2; never overwrite')
    parser.add_argument('--firmware-code', type=Path)
    parser.add_argument('--firmware-vars', type=Path)
    args = parser.parse_args()
    code, variable_template = find_firmware()
    code = args.firmware_code or code; variable_template = args.firmware_vars or variable_template
    missing = [name for name in ('qemu-system-x86_64', 'qemu-img') if not shutil.which(name)]
    if code is None or variable_template is None or not code.is_file() or not variable_template.is_file():
        missing.append('OVMF UEFI firmware (edk2-ovmf)')
    if missing:
        print('Missing: ' + ', '.join(missing), file=sys.stderr); return 1
    if args.check:
        print('QEMU and OVMF found. No disk was created or attached.'); return 0
    disk = validate_disk(args.disk)
    if args.iso and (args.iso.is_symlink() or not args.iso.is_file() or args.iso.suffix != '.iso'):
        raise ValueError('ISO must be an existing regular .iso file')
    if not disk.exists():
        if not args.create_disk: raise ValueError('Disk missing; pass --create-disk to create a new virtual disk')
        disk.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['qemu-img', 'create', '-f', 'qcow2', str(disk), '64G'], check=True)
    elif args.create_disk:
        raise ValueError('Disk already exists. Remove --create-disk to reuse it.')
    info = subprocess.run(['qemu-img', 'info', '--output=json', str(disk)], check=True, capture_output=True, text=True)
    import json
    validate_image_info(json.loads(info.stdout))
    variables = validate_vars_file(disk.with_suffix('.vars.fd'))
    if not variables.exists(): shutil.copyfile(variable_template, variables)
    command = qemu_command(args.iso, disk, code, variables, os.access('/dev/kvm', os.R_OK | os.W_OK))
    return subprocess.call(command)


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print('Husk OS VM:', exc, file=sys.stderr); raise SystemExit(1)
