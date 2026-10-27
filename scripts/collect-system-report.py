#!/usr/bin/env python3
"""Collect read-only guest diagnostics. A detected device is not a passed device test."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

COMMANDS = {
    'kernel':['uname','-a'], 'cpu':['lscpu'],
    'memory':['free','-b'], 'swap':['swapon','--show','--bytes'],
    'storage':['lsblk','--json','-o','NAME,TYPE,SIZE,MODEL,FSTYPE,MOUNTPOINTS'],
    'disk_usage':['df','-B1'], 'pci_drivers':['lspci','-nnk'], 'usb':['lsusb'],
    'network':['nmcli','device','status'], 'audio':['wpctl','status'],
    'power_profiles':['powerprofilesctl','list'], 'battery':['upower','-d'],
    'services':['systemctl','--failed','--no-pager'],
    'boot_time':['systemd-analyze','time'], 'boot_order':['systemd-analyze','critical-chain'],
    'desktop':['husk-status'], 'boot_journal':['journalctl','-b','-p','warning','--no-pager'],
}
MODULES = ('ahci','nvme','usb_storage','uas','usbhid','hid_generic','i2c_hid_acpi',
           'amdgpu','i915','xe','nouveau','nvidia','btusb','snd_hda_intel','snd_usb_audio',
           'uvcvideo','xpad','hid_playstation','hid_nintendo','iwlwifi','rtw89_core')

# One-time systemd-boot edit, deliberately absent from normal/installed defaults.
USB_BOOT_OPTIONS = ('module_blacklist=nvme,ahci,vmd', 'initcall_blacklist=ahci_pci_driver_init',
    'noresume', 'systemd.gpt_auto=0',
    'rd.systemd.gpt_auto=0', 'systemd.mask=udisks2.service', 'systemd.mask=swap.target',
    'rd.systemd.mask=swap.target')
USB_COMMANDS = {
    'storage':['lsblk','--json','--paths','--tree','-o','PATH,TYPE,TRAN,RO,MOUNTPOINTS'],
    'boot_mount':['findmnt','--json','--target','/run/archiso/bootmnt','-o','SOURCE,TARGET,FSTYPE,OPTIONS'],
    'swap':['cat','/proc/swaps'],
    'udisks':['systemctl','show','udisks2.service','--property=LoadState','--value'],
}
HARDWARE_COMMANDS = {
    'kernel':['uname','-r'], 'pci_drivers':['lspci','-nnk'], 'usb':['lsusb'],
    'network':['nmcli','--fields','DEVICE,TYPE,STATE','device','status'],
    'radio':['rfkill','--json'], 'audio':['wpctl','status'], 'sound_devices':['aplay','--list-devices'],
    'input':['libinput','list-devices'], 'wayland':['wayland-info'], 'opengl':['glxinfo','-B'],
    'vulkan':['vulkaninfo','--summary'],
    'nvidia':['nvidia-smi','--query-gpu=name,pci.bus_id,driver_version','--format=csv,noheader'],
    'desktop':['husk-status'],
}

def capture(argv):
    if not shutil.which(argv[0]): return {'status':'tool_missing','command':argv}
    try:
        result=subprocess.run(argv,text=True,capture_output=True,timeout=10)
        return {'status':'collected' if result.returncode == 0 else 'command_failed',
                'command':argv,'returncode':result.returncode,
                'stdout':result.stdout[:100000],'stderr':result.stderr[:10000]}
    except (OSError,subprocess.TimeoutExpired) as exc:
        return {'status':'unavailable','command':argv,'reason':str(exc)}

def secure_boot_status(efivar, kernel):
    """No inference from an absent variable; require canonical boot evidence."""
    values=set()
    if efivar is not None and len(efivar)==5 and efivar[4] in (0,1):
        values.add('enabled' if efivar[4] else 'disabled')
    if kernel.get('status')=='collected':
        for line in kernel.get('stdout','').splitlines():
            for value in ('enabled','disabled'):
                if line.strip()=='secureboot: Secure boot '+value: values.add(value)
    return values.pop() if len(values)==1 else 'unknown'

def hardware_state():
    release=Path('/etc/os-release').read_text()
    state=dict(live=Path('/run/archiso').is_dir(), uefi=Path('/sys/firmware/efi').is_dir(),
        is_husk_os=any(line in ('ID=huskos','ID="huskos"') for line in release.splitlines()),
        kernel_cmdline=Path('/proc/cmdline').read_text().strip(), secure_boot='unknown',
        loaded_modules=sorted(line.split()[0] for line in Path('/proc/modules').read_text().splitlines()),
        probes={name:capture(argv) for name,argv in USB_COMMANDS.items()},
        storage_modules={}, storage_builtin={}, storage_driver_probes={}, pci_storage=[], dmi={}, drm={})
    raw=None
    kernel=capture(['journalctl','-b','-k','--no-pager','-o','cat','--grep','secureboot: Secure boot'])
    state['secure_boot_evidence']=dict(kernel=kernel)
    try:
        raw=Path('/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c').read_bytes()
        state['secure_boot_evidence']['efivar_hex']=raw.hex()
    except OSError as exc: state['secure_boot_evidence']['efivar_error']=str(exc)
    state['secure_boot']=secure_boot_status(raw,kernel)
    for name in ('nvme','ahci'):
        probe=capture(['modinfo','--field','filename',name])
        state['storage_driver_probes'][name]=probe
        state['storage_modules'][name]=(probe.get('status')=='collected' and '.ko' in probe.get('stdout',''))
        state['storage_builtin'][name]=(probe.get('status')=='collected' and probe.get('stdout','').strip()=='(builtin)')
    for device in Path('/sys/bus/pci/devices').glob('*'):
        try:
            kind=(device/'class').read_text().strip()
            if not kind.startswith('0x01'): continue
            driver=(device/'driver').resolve().name if (device/'driver').is_symlink() else None
            state['pci_storage'].append(dict(pci=device.name, class_code=kind, driver=driver))
        except OSError: pass
    for name in ('sys_vendor','product_name','product_version','bios_version'):
        try: state['dmi'][name]=Path('/sys/class/dmi/id',name).read_text().strip()
        except OSError: pass
    for connector in Path('/sys/class/drm').glob('card*-*'):
        try: state['drm'][connector.name]=dict(status=(connector/'status').read_text().strip(),
                                            modes=(connector/'modes').read_text().splitlines())
        except OSError: pass
    return state

def validate_live_usb(state):
    """USB-only detection gate, not a guarantee for unknown storage controllers."""
    problems=[]
    if any(state.get(name) is not True for name in ('live','is_husk_os','uefi')):
        problems.append('Expected an actual Husk OS UEFI Live session')
    if state.get('secure_boot')!='disabled': problems.append('Secure Boot is enabled or unverified: STOP')
    tokens=state.get('kernel_cmdline','').split()
    if (not all(option in tokens for option in USB_BOOT_OPTIONS) or
        any(sum(token.startswith(key+'=') for token in tokens)!=1
            for key in ('module_blacklist','initcall_blacklist','systemd.gpt_auto','rd.systemd.gpt_auto')) or
        any(token=='--' or token.startswith(('resume=','systemd.debug_shell','rd.systemd.debug_shell')) for token in tokens)):
        problems.append('Missing or conflicting one-time USB safety boot options')
    if any(name in state.get('loaded_modules',[]) for name in ('nvme','ahci','vmd')):
        problems.append('An internal storage driver is loaded')
    if (state.get('storage_modules',{}).get('nvme') is not True or
        not (state.get('storage_modules',{}).get('ahci') is True or state.get('storage_builtin',{}).get('ahci') is True)):
        problems.append('Cannot verify the expected loadable NVMe and loadable/built-in AHCI driver kinds')
    for device in state.get('pci_storage',[]):
        if device.get('class_code') not in ('0x010802','0x010601') or device.get('driver') is not None:
            problems.append('Unsupported or bound internal storage controller: STOP')
    probes=state.get('probes',{})
    if any(probes.get(name,{}).get('status')!='collected' for name in USB_COMMANDS):
        problems.append('A required storage/swap/automount observation is unavailable')
        return problems
    try:
        storage=json.loads(probes['storage']['stdout'])['blockdevices']
        disks=[item for item in storage if item.get('type')=='disk']
        if len(disks)!=1 or disks[0].get('tran')!='usb' or any(item.get('type') not in ('disk','loop') for item in storage):
            raise ValueError('Only the boot USB may be exposed; an internal/additional/unknown disk is visible')
        def paths(item):
            return [item['path']]+[path for child in item.get('children',[]) for path in paths(child)]
        boot=json.loads(probes['boot_mount']['stdout'])['filesystems']
        if (len(boot)!=1 or boot[0].get('source') not in paths(disks[0]) or
            boot[0].get('target')!='/run/archiso/bootmnt' or boot[0].get('fstype')!='iso9660' or
            'ro' not in boot[0].get('options','').split(',') or 'rw' in boot[0].get('options','').split(',')):
            raise ValueError('The actual Live boot mount is not read-only ISO media on the sole USB disk')
        swap=[line.split() for line in probes['swap']['stdout'].splitlines() if line.strip()]
        if swap!=[['Filename','Type','Size','Used','Priority']]: raise ValueError('Active swap or invalid /proc/swaps observation: STOP')
        if probes['udisks']['stdout'].strip()!='masked': raise ValueError('UDisks is not runtime-masked')
    except (KeyError,TypeError,ValueError) as exc: problems.append(str(exc))
    return problems

def validate_live_report_path(output, runtime, filesystem, uid):
    if (filesystem!='tmpfs' or runtime.is_symlink() or runtime.resolve()!=runtime or
        runtime.stat().st_uid!=uid or output.parent!=runtime):
        return ['Live report must be a direct child of the current user-owned session tmpfs']
    return []

def write_report(path, result):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2,ensure_ascii=False); stream.write('\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--live-usb',action='store_true',help='Fail closed on first USB Live safety checks; RAM output only')
    args=parser.parse_args()
    if args.live_usb:
        if os.getuid()==0: parser.error('Run as the unprivileged Live desktop user')
        runtime=Path('/run/user')/str(os.getuid())
        filesystem=capture(['findmnt','-n','-o','FSTYPE','--target',str(runtime)]).get('stdout','').strip()
        problems=validate_live_report_path(args.output,runtime,filesystem,os.getuid())
        if problems: parser.error('; '.join(problems))
        state=hardware_state(); problems=validate_live_usb(state)
        result=dict(created_utc=datetime.now(timezone.utc).isoformat(),uid=os.getuid(),
            scope='Detection only; physical GPU, peripheral and Windows safety acceptance NOT TESTED.',
            hardware=state, safety=dict(status='STOP' if problems else 'USB_ONLY',problems=problems),
            commands={name:capture(argv) for name,argv in HARDWARE_COMMANDS.items()})
        write_report(args.output,result); print(args.output)
        return 1 if problems else 0
    release=Path('/etc/os-release').read_text()
    result={'created_utc':datetime.now(timezone.utc).isoformat(), 'os_release':release,
            'is_husk_os':any(line in ('ID=huskos','ID="huskos"') for line in release.splitlines()),
            'uid':os.getuid(),'scope':'Detection and diagnostics only; not a hardware compatibility or idle performance acceptance test.',
            'commands':{name:capture(argv) for name,argv in COMMANDS.items()},
            'modules':{name:capture(['modinfo',name]) for name in MODULES}}
    write_report(args.output,result)
    print(args.output)
    return 0

if __name__ == '__main__':raise SystemExit(main())
