"""Read-only target guard for the pinned Calamares/KPMCore backend.

This module never mounts, partitions, formats or writes block devices.
The caller must run in the actual Live environment. A failed inventory
protects all disks rather than guessing which device contains the Live ISO.
"""
import hashlib
import json
import re
import subprocess


def _nodes(node):
    yield node
    children = node.get('children', [])
    if not isinstance(children, list): raise ValueError('Invalid block-device children')
    for child in children:
        if not isinstance(child, dict): raise ValueError('Invalid block-device record')
        yield from _nodes(child)


def inventory(data, live_major_minor):
    if not re.fullmatch(r'[0-9]+:[0-9]+', live_major_minor or ''):
        raise ValueError('The Live installation medium could not be identified. No disks are available.')
    disks = data.get('blockdevices') if isinstance(data, dict) else None
    if not isinstance(disks, list): raise ValueError('Invalid block-device inventory')
    matches = [d for d in disks if any(n.get('maj:min') == live_major_minor for n in _nodes(d))]
    if len(matches) != 1:
        raise ValueError('Ambiguous Live installation medium. No disks are available.')
    source = matches[0]
    allowed = []
    for device in disks:
        name = device.get('name', '')
        if device is source or device.get('type') != 'disk': continue
        if not re.fullmatch(r'/dev/[a-zA-Z0-9._-]+', name): continue
        if device.get('ro') not in (False, 0) or device.get('rm') not in (False, 0): continue
        size = device.get('size')
        if type(size) is not int or size < 25 * 1024**3: continue
        sequence = device.get('disk-seq')
        if type(sequence) is not int or sequence <= 0: continue
        unsafe = False
        for node in _nodes(device):
            mounts = node.get('mountpoints') or []
            if not isinstance(mounts, list) or any(m for m in mounts): unsafe = True
            if node.get('fstype') in ('iso9660', 'linux_raid_member', 'LVM2_member', 'crypto_LUKS'): unsafe = True
            if node.get('type') not in ('disk', 'part'): unsafe = True
        if not unsafe: allowed.append(device)
    return allowed


def fingerprint(device):
    # Include topology, serial/WWN, size, mount state and filesystem metadata.
    # The snapshot is captured before KPMCore plans changes in memory.
    return hashlib.sha256(json.dumps(device, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def verify(data, live_major_minor, target, expected):
    candidates = [d for d in inventory(data, live_major_minor) if d['name'] == target]
    if len(candidates) != 1 or fingerprint(candidates[0]) != expected:
        raise ValueError('The installation drive changed or is no longer safe. Return to drive selection.')
    return True


def read_inventory():
    result = subprocess.run(['/usr/bin/lsblk', '--json', '--bytes', '--paths', '--output',
        'NAME,TYPE,SIZE,RO,RM,TRAN,MODEL,SERIAL,WWN,MAJ:MIN,DISK-SEQ,FSTYPE,LABEL,MOUNTPOINTS,PKNAME'],
        check=True, capture_output=True, text=True, timeout=15)
    if len(result.stdout) > 2 * 1024**2: raise ValueError('Block-device inventory is too large')
    source = subprocess.run(['/usr/bin/findmnt','--noheadings','--output','MAJ:MIN',
        '--target','/run/archiso/bootmnt'], check=True, capture_output=True, text=True, timeout=10).stdout.strip()
    return json.loads(result.stdout), source


def main(argv=None):
    import argparse
    import sys
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inventory','snapshot','verify'))
    parser.add_argument('device', nargs='?')
    parser.add_argument('fingerprint', nargs='?')
    args = parser.parse_args(argv)
    try:
        if not Path('/run/archiso/bootmnt').is_mount() or not Path('/sys/firmware/efi').is_dir():
            raise ValueError('Disk installation requires a UEFI-booted Husk OS Live environment.')
        data, source = read_inventory()
        if args.action == 'inventory':
            print(json.dumps({d['name']:fingerprint(d) for d in inventory(data,source)},sort_keys=True))
            return 0
        candidates = [d for d in inventory(data, source) if d['name'] == args.device]
        if len(candidates) != 1: raise ValueError('This drive is protected or unavailable.')
        if args.action == 'verify': verify(data, source, args.device, args.fingerprint)
        print(fingerprint(candidates[0]))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
