"""A diagnostic TTY must never take the live compositor's seat permanently."""
import importlib.util
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class BootHarnessTests(unittest.TestCase):
    def load_harness(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/ci-test-system1.py'
        spec = importlib.util.spec_from_file_location('husk_boot_harness', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def prior_evidence(self):
        build=dict(source_commit='candidate-source',iso_bytes=2147778560,
                   rootfs=dict(status='PASS'),v3_rootfs=dict(status='PASS'),release_file_eligible=False)
        boot=dict(iso_sha256='a'*64,iso_bytes=2147778560,boot='PASSED',terminal='PASSED',shutdown='PASSED',
                  problems=[],desktop_status=dict(os='Husk OS',desktop='Husk Desktop',backend='wayland',
                      version='v3-phase2',live=True,panel_visible=True,panel_mapped=True,
                      bridge_connected=True,desktop_surfaces=1))
        return build,boot

    def test_missing_prior_live_boot_requires_a_real_new_boot_even_when_payload_checks_pass(self):
        module=self.load_harness(); build,_=self.prior_evidence()
        self.assertIsNone(module.verified_recovered_boot(build,None,'candidate-source','a'*64,2147778560))

    def test_only_matching_successful_live_boot_evidence_can_be_reused(self):
        module=self.load_harness(); build,boot=self.prior_evidence()
        self.assertEqual(module.verified_recovered_boot(build,boot,'candidate-source','a'*64,2147778560),boot)
        for change in (dict(iso_sha256='b'*64),dict(iso_bytes=2147778561),dict(boot='FAILED'),
                       dict(terminal='NOT TESTED'),dict(shutdown='FAILED'),dict(problems=['failed']),
                       dict(desktop_status=dict(boot['desktop_status'],live=False)),
                       dict(desktop_status=dict(boot['desktop_status'],version='system-2'))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.verified_recovered_boot(build,dict(boot,**change),'candidate-source','a'*64,2147778560)

    def test_a_wrong_build_or_failed_payload_never_authorizes_evidence_reuse(self):
        module=self.load_harness(); build,boot=self.prior_evidence()
        for change in (dict(source_commit='other-source'),dict(iso_bytes=1),dict(rootfs=dict(status='FAIL')),
                       dict(v3_rootfs=dict(status='FAIL'))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.verified_recovered_boot(dict(build,**change),boot,'candidate-source','a'*64,2147778560)

    def test_normal_iso_boot_must_observe_effective_half_ram_tmpfs_not_just_a_test_kernel_argument(self):
        module = self.load_harness()
        self.assertTrue(callable(getattr(module, 'validate_live_write_space', None)),
                        'The real ISO boot needs effective temporary-write-space validation')
        valid = dict(kernel_cmdline='archisobasedir=arch cow_spacesize=50%',
                     memory_total_bytes=4*1024**3,
                     live_write_space=dict(filesystem='tmpfs', total_bytes=2*1024**3))
        self.assertEqual(module.validate_live_write_space(valid), [])
        for changes in (dict(kernel_cmdline='archisobasedir=arch'),
                        dict(live_write_space=dict(filesystem='tmpfs', total_bytes=256*1024**2)),
                        dict(live_write_space=dict(filesystem='ext4', total_bytes=2*1024**3)),
                        dict(memory_total_bytes=8*1024**3), dict(memory_total_bytes=None)):
            self.assertTrue(module.validate_live_write_space(dict(valid, **changes)))
        self.assertTrue(module.validate_live_write_space({}))

    def test_diagnostic_query_returns_to_the_compositor_vt(self):
        module = self.load_harness()
        self.assertTrue(hasattr(module, 'request_guest_evidence'))
        class Monitor:
            active = 1
            queried = False
            def key(self, keys): self.active = {'ctrl-alt-f1': 1, 'ctrl-alt-f2': 2}[keys]
            def type_console(self, text):
                self.queried = self.active == 2 and 'probe.py' in text
        monitor = Monitor()
        with patch.object(module.time, 'sleep'):
            module.request_guest_evidence(monitor)
        self.assertTrue(monitor.queried)
        self.assertEqual(monitor.active, 1)

    def test_failed_diagnostic_typing_still_restores_the_compositor_vt(self):
        module = self.load_harness()
        self.assertTrue(hasattr(module, 'request_guest_evidence'))
        class Monitor:
            active = 1
            def key(self, keys): self.active = {'ctrl-alt-f1': 1, 'ctrl-alt-f2': 2}[keys]
            def type_console(self, text): raise RuntimeError('keyboard disconnected')
        monitor = Monitor()
        with patch.object(module.time, 'sleep'), self.assertRaisesRegex(RuntimeError, 'keyboard disconnected'):
            module.request_guest_evidence(monitor)
        self.assertEqual(monitor.active, 1)

    def test_usb_probe_uses_the_same_collector_and_compiles(self):
        module=self.load_harness()
        compile(module.hardware_probe(), '<actual USB guest probe>', 'exec')
        self.assertIn(module.collector_digest(), module.hardware_probe())

    def test_usb_boot_options_are_typed_into_the_actual_uefi_menu(self):
        module=self.load_harness()
        class Monitor:
            events=[]
            def key(self, keys): self.events.append(('key',keys))
            def type_console(self, text, submit=True): self.events.append(('text',text,submit))
            def capture(self, name): self.events.append(('capture',name))
        monitor=Monitor()
        with patch.object(module.time,'sleep'):
            module.edit_usb_boot(monitor,'protected')
        text=next(item for item in monitor.events if item[0]=='text')
        self.assertIn('module_blacklist=nvme,ahci,vmd',text[1])
        self.assertFalse(text[2])
        self.assertEqual(monitor.events[-1],('key','ret'))
        self.assertLess(monitor.events.index(('key','e')),monitor.events.index(text))

    def test_usb_vm_disks_are_new_regular_disposable_files_and_iso_is_read_only(self):
        module=self.load_harness()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            disks=module.create_usb_sentinels(root)
            self.assertEqual(set(disks), {'nvme-test','sata-test'})
            for path in disks.values():
                self.assertEqual(path.parent,root)
                self.assertTrue(path.is_file()); self.assertFalse(path.is_symlink())
                self.assertEqual(path.stat().st_size,32*1024**2)
            with self.assertRaises(FileExistsError): module.create_usb_sentinels(root)
            options=module.usb_drive_options(root/'candidate.iso',disks)
            self.assertIn('usb-storage,bus=xhci.0,drive=live,bootindex=1',options)
            self.assertIn('nvme,drive=nvme-test,serial=HUSK-NVME',options)
            self.assertIn('ide-hd,drive=sata-test,bus=ide.0,serial=HUSK-SATA',options)
            self.assertTrue(any('id=live' in arg and 'readonly=on' in arg for arg in options))
            self.assertNotIn('-kernel',options); self.assertNotIn('-initrd',options)

    def test_both_sentinel_disks_need_complete_zero_write_statistics(self):
        module=self.load_harness()
        keys=('wr_bytes','wr_operations','unmap_bytes','unmap_operations','failed_wr_operations',
              'invalid_wr_operations','failed_unmap_operations','invalid_unmap_operations')
        valid=[dict(device=name,stats=dict.fromkeys(keys,0)|dict(flush_operations=1))
               for name in ('nvme-test','sata-test')]
        self.assertEqual(module.validate_usb_blockstats(valid),[])
        self.assertTrue(module.validate_usb_blockstats(valid[:1]))
        for key in keys:
            bad=copy.deepcopy(valid); bad[1]['stats'][key]=1
            with self.subTest(key=key): self.assertTrue(module.validate_usb_blockstats(bad))
        bad=copy.deepcopy(valid); del bad[0]['stats']['wr_bytes']
        self.assertTrue(module.validate_usb_blockstats(bad))

    def test_final_operation_counts_are_observed_after_guest_poweroff_before_host_quit(self):
        module=self.load_harness()
        class Monitor:
            events=[]
            def command(self, name):
                self.events.append(name)
                if name=='query-status': return dict(status='shutdown',running=False)
                if name=='query-blockstats': return [dict(device='nvme-test',stats=dict(wr_bytes=512))]
                raise AssertionError(name)
        monitor=Monitor()
        observed=module.observe_usb_shutdown(monitor)
        self.assertEqual(monitor.events,['query-status','query-blockstats'])
        self.assertEqual(observed['guest_status']['status'],'shutdown')
        self.assertTrue(module.validate_usb_blockstats(observed['blockstats']))
        class Paused:
            def command(self, name): return dict(status='paused',running=False)
        with self.assertRaisesRegex(RuntimeError,'shutdown'):
            module.observe_usb_shutdown(Paused(),timeout=0)

    def test_protected_and_negative_control_need_actual_controller_and_disk_observations(self):
        from test_hardware_report import collector, snapshot
        module=self.load_harness(); report=collector(); state=snapshot(report)
        state['pci_storage']=[dict(class_code=kind,driver=None) for kind in ('0x010802','0x010601')]
        self.assertEqual(module.validate_hardware_usb(state,'protected'),[])
        self.assertTrue(module.validate_hardware_usb(dict(state,pci_storage=[]),'protected'))
        self.assertTrue(module.validate_hardware_usb(state,'control'))
        control=copy.deepcopy(state)
        control['kernel_cmdline']=control['kernel_cmdline'].replace(report.USB_BOOT_OPTIONS[0],'')
        control['loaded_modules']=['nvme','ahci']
        for device,driver in zip(control['pci_storage'],('nvme','ahci')): device['driver']=driver
        devices=json.loads(control['probes']['storage']['stdout'])
        devices['blockdevices'] += [dict(path='/dev/nvme0n1',type='disk',tran='nvme'),
                                   dict(path='/dev/sdb',type='disk',tran='sata')]
        control['probes']['storage']['stdout']=json.dumps(devices)
        self.assertEqual(module.validate_hardware_usb(control,'control'),[])
        self.assertTrue(module.validate_hardware_usb(control,'protected'))
