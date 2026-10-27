"""Fail closed before a first USB Live test; never certify physical hardware."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest


def collector():
    path = Path(__file__).resolve().parents[1] / 'scripts/collect-system-report.py'
    spec = importlib.util.spec_from_file_location('hardware_report', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(module):
    def probe(value): return dict(status='collected', stdout=json.dumps(value))
    return dict(live=True, is_husk_os=True, uefi=True, secure_boot='disabled',
        kernel_cmdline='archisobasedir=arch ' + ' '.join(module.USB_BOOT_OPTIONS),
        loaded_modules=[], storage_modules=dict(nvme=True, ahci=True), pci_storage=[],
        probes=dict(storage=probe(dict(blockdevices=[dict(path='/dev/sda', type='disk', tran='usb',
            children=[dict(path='/dev/sda1', type='part')])])),
            boot_mount=probe(dict(filesystems=[dict(source='/dev/sda1', target='/run/archiso/bootmnt',
                fstype='iso9660', options='ro,relatime')])),
            swap=probe(dict(swapdevices=[])), udisks=dict(status='collected', stdout='masked\n')))


class HardwareReportTests(unittest.TestCase):
    def test_complete_usb_only_snapshot_is_accepted(self):
        module = collector()
        self.assertEqual(module.validate_live_usb(snapshot(module)), [])

    def test_internal_or_additional_disks_and_wrong_boot_source_stop_the_test(self):
        module = collector()
        for path, transport in (('/dev/nvme0n1','nvme'), ('/dev/sdb','sata'),
                                ('/dev/mmcblk0',None), ('/dev/sdb','usb')):
            state = snapshot(module)
            storage = json.loads(state['probes']['storage']['stdout'])
            storage['blockdevices'].append(dict(path=path, type='disk', tran=transport))
            state['probes']['storage']['stdout'] = json.dumps(storage)
            with self.subTest(transport=transport): self.assertTrue(module.validate_live_usb(state))
        state = snapshot(module)
        state['probes']['boot_mount']['stdout'] = json.dumps(dict(filesystems=[dict(
            source='/dev/nvme0n1p1', target='/run/archiso/bootmnt', fstype='iso9660', options='ro')]))
        self.assertTrue(module.validate_live_usb(state))

    def test_missing_conflicting_guards_and_loaded_or_builtin_drivers_stop(self):
        module = collector(); valid = snapshot(module)
        changes = [dict(live=False), dict(is_husk_os=False), dict(uefi=False),
            dict(secure_boot='enabled'), dict(secure_boot='unknown'), dict(loaded_modules=['nvme']),
            dict(storage_modules=dict(nvme=False, ahci=True)),
            dict(kernel_cmdline=valid['kernel_cmdline']+' module_blacklist=unused'),
            dict(kernel_cmdline=valid['kernel_cmdline']+' systemd.gpt_auto=1'),
            dict(kernel_cmdline=valid['kernel_cmdline']+' --'),
            dict(kernel_cmdline=valid['kernel_cmdline']+' resume=/dev/sdb')]
        changes += [dict(kernel_cmdline=valid['kernel_cmdline'].replace(option, ''))
                    for option in module.USB_BOOT_OPTIONS]
        for change in changes:
            with self.subTest(change=change): self.assertTrue(module.validate_live_usb(dict(valid, **change)))

    def test_missing_probes_active_swap_or_writable_media_stop(self):
        module = collector()
        for name, value in [('storage','{}'), ('storage','invalid'),
                            ('swap',json.dumps(dict(swapdevices=[dict(name='/dev/sdb')]))),
                            ('boot_mount',json.dumps(dict(filesystems=[dict(source='/dev/sda1',
                                target='/run/archiso/bootmnt', fstype='iso9660', options='rw')]))),
                            ('udisks','loaded')]:
            state = snapshot(module); state['probes'][name]['stdout'] = value
            with self.subTest(name=name, value=value): self.assertTrue(module.validate_live_usb(state))
        for name in snapshot(module)['probes']:
            state = snapshot(module); del state['probes'][name]
            with self.subTest(missing=name): self.assertTrue(module.validate_live_usb(state))

    def test_report_is_private_exclusive_and_live_destination_is_session_ram(self):
        module = collector()
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory); output = runtime/'report.json'
            self.assertEqual(module.validate_live_report_path(output, runtime, 'tmpfs', os.getuid()), [])
            self.assertTrue(module.validate_live_report_path(output, runtime, 'ext4', os.getuid()))
            self.assertTrue(module.validate_live_report_path(output, runtime, 'tmpfs', os.getuid()+1))
            self.assertTrue(module.validate_live_report_path(runtime/'child/report.json', runtime, 'tmpfs', os.getuid()))
            module.write_report(output, dict(test=True))
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError): module.write_report(output, {})
            link = runtime/'link'; link.symlink_to(output)
            with self.assertRaises(FileExistsError): module.write_report(link, {})
            self.assertEqual(json.loads(output.read_text()), dict(test=True))
            alias = runtime/'alias'; alias.symlink_to(runtime, target_is_directory=True)
            self.assertTrue(module.validate_live_report_path(alias/'other.json', alias, 'tmpfs', os.getuid()))
