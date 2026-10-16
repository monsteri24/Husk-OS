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

def capture(argv):
    if not shutil.which(argv[0]): return {'status':'tool_missing','command':argv}
    try:
        result=subprocess.run(argv,text=True,capture_output=True,timeout=10)
        return {'status':'collected' if result.returncode == 0 else 'command_failed',
                'command':argv,'returncode':result.returncode,
                'stdout':result.stdout[:100000],'stderr':result.stderr[:10000]}
    except (OSError,subprocess.TimeoutExpired) as exc:
        return {'status':'unavailable','command':argv,'reason':str(exc)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    release=Path('/etc/os-release').read_text()
    result={'created_utc':datetime.now(timezone.utc).isoformat(), 'os_release':release,
            'is_husk_os':any(line in ('ID=huskos','ID="huskos"') for line in release.splitlines()),
            'uid':os.getuid(),'scope':'Detection and diagnostics only; not a hardware compatibility or idle performance acceptance test.',
            'commands':{name:capture(argv) for name,argv in COMMANDS.items()},
            'modules':{name:capture(['modinfo',name]) for name in MODULES}}
    # Never replace an existing report or follow a final symlink.
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2,ensure_ascii=False); stream.write('\n')
    print(args.output)
    return 0

if __name__ == '__main__':raise SystemExit(main())
