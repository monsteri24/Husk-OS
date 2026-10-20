"""Acceptance orchestration contracts; these tests never boot or install a VM."""
import importlib.util
import ast
import json
import io
from pathlib import Path
import re
import stat
import shutil
import subprocess
import socket
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


class InstallHarnessTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'scripts/ci-test-v3-install.py'
        self.assertTrue(path.is_file(), 'The real disposable installation harness is missing')
        spec = importlib.util.spec_from_file_location('v3_install_harness', path)
        self.harness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.harness)

    def test_an_existing_disk_or_symlink_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            disk = directory / 'install-target.qcow2'
            disk.write_bytes(b'preserve-existing-data')
            with self.assertRaises(ValueError):
                self.harness.create_disposable_disk(directory)
            self.assertEqual(disk.read_bytes(), b'preserve-existing-data')
            disk.unlink()
            target = directory / 'other-data'; target.write_bytes(b'preserve-target')
            disk.symlink_to(target)
            with self.assertRaises(ValueError):
                self.harness.create_disposable_disk(directory)
            self.assertEqual(target.read_bytes(), b'preserve-target')

    @unittest.skipUnless(shutil.which('qemu-img'), 'qemu-img is needed for a real sparse-image check')
    def test_a_new_disk_is_qcow2_without_a_backing_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            disk = self.harness.create_disposable_disk(Path(temporary))
            self.assertEqual(disk.name, 'install-target.qcow2')
            self.assertTrue(disk.is_file())
            import json
            info = json.loads(subprocess.check_output(['qemu-img', 'info', '--output=json', str(disk)]))
            self.assertEqual(info['format'], 'qcow2')
            self.assertEqual(info['virtual-size'], 32 * 1024 ** 3)
            self.assertNotIn('backing-filename', info)

    def test_installed_boot_has_no_live_media_or_kernel_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            values = dict(artifacts=directory, disk=directory/'install-target.qcow2',
                          iso=directory/'live.iso', firmware_code=directory/'code.fd',
                          firmware_vars=directory/'vars.fd', kernel=directory/'vmlinuz-linux',
                          initrd=directory/'initramfs-linux.img', iso_label='HUSK_TEST', kvm=False)
            for key in ('disk', 'iso', 'firmware_code', 'firmware_vars', 'kernel', 'initrd'):
                values[key].touch()
            live = self.harness.make_qemu_command('live', **values)
            installed = self.harness.make_qemu_command('installed', **values)
            self.assertIn('-kernel', live)
            self.assertIn('systemd.debug_shell=ttyS1', live[live.index('-append') + 1])
            self.assertIn('systemd.mask=serial-getty@ttyS1.service', live[live.index('-append') + 1])
            self.assertNotIn('console=ttyS1', live[live.index('-append') + 1])
            serial_ports = [live[i + 1] for i, value in enumerate(live[:-1]) if value == '-serial']
            self.assertEqual(serial_ports, ['file:'+str(directory/'live-serial.log'), 'chardev:setup'])
            self.assertIn('-chardev', live)
            self.assertNotIn('-chardev', installed)
            for argument in ('-cdrom', '-kernel', '-initrd', '-append'):
                self.assertNotIn(argument, installed)
            self.assertNotIn(str(values['iso']), installed)
            for command in (live, installed):
                self.assertEqual(command[command.index('-nic')+1],
                                 'user,model=virtio-net-pci,ipv6=off',
                                 'The offline fixture must not advertise an independent IPv6 router')
            self.assertTrue(any('serial=HUSK-DISPOSABLE' in item for item in installed))
            with self.assertRaises(ValueError):
                self.harness.make_qemu_command('installed', **dict(values, disk=Path('/dev/vda')))

    def test_serial_setup_waits_for_real_output_and_rejects_multiline_commands(self):
        self.assertTrue(hasattr(self.harness,'SerialConsole'), 'The acknowledged serial test channel is missing')
        try: client, guest = socket.socketpair()
        except PermissionError: self.skipTest('Local policy blocks Unix sockets; the real channel test runs in Actions')
        self.addCleanup(guest.close)
        console = self.harness.SerialConsole(connection=client)
        self.addCleanup(console.close)
        self.assertEqual(console.read(), b'')
        console.sendline('id -u')
        self.assertEqual(guest.recv(1024), b'id -u\n')
        guest.sendall(b'boot is still running\r\n')
        self.assertIn(b'boot is still running', console.read())
        guest.sendall(b'HUSK-READY-test-token\r\n')
        self.assertIn(b'HUSK-READY-test-token', console.read())
        for command in ('id\nreboot', 'id\rreboot', 'id\0'):
            with self.subTest(command=command), self.assertRaises(ValueError): console.sendline(command)
        guest.close()
        with self.assertRaisesRegex(RuntimeError,'serial console'):
            console.read()

    def test_uart_commands_are_paced_and_only_probe_input_can_be_reset(self):
        connection = Mock()
        console = self.harness.SerialConsole(connection=connection)
        command = 'printf readiness-' + 'a' * 80
        with patch.object(self.harness.time,'sleep') as pause:
            console.sendline(command)
        chunks = [call.args[0] for call in connection.sendall.call_args_list]
        self.assertEqual(b''.join(chunks),command.encode()+b'\n')
        self.assertTrue(all(0 < len(chunk) <= 16 for chunk in chunks), 'Do not flood an emulated UART FIFO')
        self.assertGreater(pause.call_count,0)
        console.interrupt()
        self.assertEqual(connection.sendall.call_args.args,(b'\x03',))

    def test_installed_evidence_requires_real_user_disk_session_and_version(self):
        valid = dict(phase='installed', uid=1001, user='huskcheck', live=False, uefi=True,
                     debug_shell=False, root_device='/dev/vda2', root_fstype='ext4',
                     optical_media=[], packages=['ownos-core','ownos-ui','ownos-desktop','linux','grub','sddm'],
                     session=dict(Type='wayland', Name='huskcheck', Remote='no'),
                     status=dict(version='v3-phase2', backend='wayland', live=False,
                                 bridge_connected=True, panel_mapped=True, desktop_surfaces=1))
        self.assertEqual(self.harness.validate_installed_report(valid, 'v3-phase2', 'huskcheck'), [])
        for changes in [dict(uid=0), dict(live=True), dict(uefi=False), dict(debug_shell=True),
                        dict(root_device='/dev/sda2'), dict(optical_media=['/dev/sr0']),
                        dict(user='live'), dict(session=dict(Type='tty',Name='huskcheck',Remote='no')),
                        dict(status=dict(valid['status'], version='system-2'))]:
            with self.subTest(changes=changes):
                self.assertTrue(self.harness.validate_installed_report(dict(valid, **changes),
                                                                      'v3-phase2', 'huskcheck'))

    def test_install_success_requires_explicit_confirmation_and_postponed_restart(self):
        events = [dict(event=name) for name in self.harness.REQUIRED_DRIVER_EVENTS]
        events += [dict(event='cancel-click'),dict(event='cancel-confirmed')]
        valid = dict(phase='installation', success=True, events=events, process_exit=0,
                     restart_postponed=True, offline=True, guard_target_accepted=True,
                     live_medium_rejected=True,cancellation=True,cancellation_host_confirmed=True,
                     target_checks={name:True for name in self.harness.REQUIRED_TARGET_CHECKS})
        self.assertEqual(self.harness.validate_install_report(valid), [])
        missing = [event for event in events if event['event'] != 'confirmation-click']
        self.assertTrue(self.harness.validate_install_report(dict(valid, events=missing)))
        self.assertTrue(self.harness.validate_install_report(dict(valid, restart_postponed=False)))
        self.assertTrue(self.harness.validate_install_report(dict(valid,cancellation=False)))
        self.assertTrue(self.harness.validate_install_report(dict(valid,cancellation_host_confirmed=False)))
        self.assertTrue(self.harness.validate_install_report(dict(valid,
            target_checks=dict(valid['target_checks'], initramfs=False))))

    def test_embedded_guest_sources_compile_and_decode_real_proc_environment(self):
        for name in ('GUEST_SETUP','INSTALLED_PROBE'):
            source=getattr(self.harness,name)
            tree=ast.parse(source)
            compile(source,'<'+name+'>','exec')
            separators=[node.args[0].value for node in ast.walk(tree)
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and
                node.func.attr=='split' and node.args and isinstance(node.args[0],ast.Constant)
                and isinstance(node.args[0].value,bytes)]
            self.assertIn(b'\0',separators)

    def guest_functions(self, *names):
        tree = ast.parse(self.harness.GUEST_SETUP)
        definitions = [node for node in tree.body
                       if isinstance(node, ast.FunctionDef) and node.name in names]
        self.assertEqual({node.name for node in definitions}, set(names))
        clock = [0.0]
        namespace = dict(json=json, re=re, state={}, time=SimpleNamespace(
            monotonic=lambda: clock[0], sleep=lambda seconds: clock.__setitem__(0, clock[0]+seconds)))
        exec(compile(ast.Module(body=definitions, type_ignores=[]), '<guest-functions>', 'exec'), namespace)
        return namespace

    def test_offline_setup_temporarily_updates_networkmanager_without_an_ipv6_default(self):
        guest = self.guest_functions('routes', 'disconnect_external_routes')
        route = [json.dumps([dict(dst='default', gateway='10.0.2.2', dev='enp0s2')]), '[]', '', '[]', '[]']
        command = Mock(side_effect=lambda *args, **kwargs: SimpleNamespace(stdout=route.pop(0) if route else '[]'))
        guest['command'] = command
        self.assertTrue(guest['disconnect_external_routes']())
        calls = [call.args[0] for call in command.call_args_list]
        self.assertEqual([argv for argv in calls if argv[0]=='nmcli'], [
            ['nmcli', '--wait', '20', 'device', 'modify', 'enp0s2',
             'ipv4.never-default', 'yes', 'ipv6.never-default', 'yes']])
        self.assertTrue(all(argv[1:]==['-j',argv[2],'route','show','exact','default']
                            for argv in calls if argv[0]=='ip'))
        self.assertEqual(route, [])

    def test_offline_setup_updates_a_dual_stack_device_once(self):
        guest = self.guest_functions('routes', 'disconnect_external_routes')
        route = [json.dumps([dict(dst='default', dev='enp0s2')]),
                 json.dumps([dict(dst='default', dev='enp0s2', gateway='fe80::2')]), '', '[]', '[]']
        guest['command'] = Mock(side_effect=lambda *args, **kwargs: SimpleNamespace(stdout=route.pop(0) if route else '[]'))
        self.assertTrue(guest['disconnect_external_routes']())
        changes = [call.args[0] for call in guest['command'].call_args_list if call.args[0][0] == 'nmcli']
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0][5], 'enp0s2')

    def test_offline_route_detection_ignores_link_routes_and_unreachable_defaults(self):
        guest = self.guest_functions('routes')
        route = [json.dumps([dict(dst='10.0.2.0/24', dev='enp0s2')]),
                 json.dumps([dict(dst='default', type='unreachable'), dict(dst='fe80::/64', dev='enp0s2')])]
        guest['command'] = Mock(side_effect=lambda *args, **kwargs: SimpleNamespace(stdout=route.pop(0)))
        self.assertEqual(guest['routes'](), [])

    def test_offline_route_detection_rejects_malformed_or_ambiguous_routes(self):
        for route in ('not-json', '{}', '[null]', '[{"dst":"default"}]',
                      '[{"dst":"default","dev":"unsafe/name"}]',
                      '[{"dst":"default","dev":"enp0s2","type":"unknown"}]'):
            with self.subTest(route=route):
                guest = self.guest_functions('routes')
                guest['command'] = Mock(return_value=SimpleNamespace(stdout=route))
                with self.assertRaisesRegex(RuntimeError, 'route'):
                    guest['routes']()

    def test_offline_setup_rejects_routes_that_remain_after_networkmanager_update(self):
        guest = self.guest_functions('routes', 'disconnect_external_routes')
        guest['command'] = Mock(return_value=SimpleNamespace(stdout='[{"dst":"default","dev":"enp0s2"}]'))
        with self.assertRaisesRegex(RuntimeError, 'default routes'):
            guest['disconnect_external_routes']()

    def test_offline_setup_waits_for_kernel_routes_to_converge_after_a_successful_reapply(self):
        guest = self.guest_functions('disconnect_external_routes')
        pending = [dict(device='enp0s2', family='-6', gateway='fe80::2')]
        observations = [pending, pending, [], pending, [], [], [], [], [], []]
        guest['routes'] = Mock(side_effect=lambda: observations.pop(0) if observations else [])
        guest['command'] = Mock(return_value=SimpleNamespace(stdout='Connection successfully reapplied'))
        self.assertTrue(guest['disconnect_external_routes']())
        self.assertEqual(guest['command'].call_count, 1, 'Do not retry successful NetworkManager mutations')
        self.assertGreaterEqual(guest['time'].monotonic(), 1)
        self.assertTrue(guest['state']['offline_route_checks'])

    def test_offline_setup_timeout_preserves_remaining_routes_in_diagnostics(self):
        guest = self.guest_functions('disconnect_external_routes')
        pending = [dict(device='enp0s2', family='-6', gateway='fe80::2')]
        guest['routes'] = Mock(return_value=pending)
        guest['command'] = Mock(return_value=SimpleNamespace(stdout='Connection successfully reapplied'))
        with self.assertRaisesRegex(RuntimeError, 'enp0s2'):
            guest['disconnect_external_routes']()
        self.assertEqual(guest['state']['offline_route_checks'][-1]['routes'], pending)
        self.assertEqual(guest['command'].call_count, 1)

    def test_offline_setup_propagates_a_networkmanager_failure(self):
        guest = self.guest_functions('routes', 'disconnect_external_routes')
        def command(argv, **kwargs):
            if argv[0] == 'nmcli': raise RuntimeError('NetworkManager rejected the temporary change')
            return SimpleNamespace(stdout='[{"dst":"default","dev":"enp0s2"}]')
        guest['command'] = command
        with self.assertRaisesRegex(RuntimeError, 'NetworkManager rejected'):
            guest['disconnect_external_routes']()

    def test_offline_setup_does_not_ignore_a_real_route_command_error(self):
        guest = self.guest_functions('routes', 'disconnect_external_routes')
        guest['command'] = Mock(side_effect=RuntimeError('route inspection failed'))
        with self.assertRaisesRegex(RuntimeError, 'inspection failed'):
            guest['disconnect_external_routes']()

    def test_root_fixture_obtains_private_expiring_xauthority_as_the_live_user(self):
        guest = self.guest_functions('authorize_x11')
        runtime = Path('/run/user/1000')
        directory = runtime / 'husk-installer-test.123456'
        def metadata(path):
            regular = path.name == 'Xauthority'
            return SimpleNamespace(st_uid=1000, st_mode=(stat.S_IFREG | 0o600) if regular else
                                   (stat.S_IFDIR | 0o700), st_nlink=1, st_size=120)
        guest.update(P=Path, stat=stat, pwd=SimpleNamespace(getpwuid=lambda uid: SimpleNamespace(pw_name='live')))
        guest['command'] = Mock(side_effect=[SimpleNamespace(stdout=str(directory)+'\n'), SimpleNamespace(stdout='')])
        with patch.object(Path, 'lstat', metadata):
            authority = guest['authorize_x11'](dict(DISPLAY=':0', XDG_RUNTIME_DIR=str(runtime)), 1000)
        self.assertEqual(authority, str(directory/'Xauthority'))
        calls = guest['command'].call_args_list
        self.assertEqual(calls[0].args[0][:4], ['runuser', '-u', 'live', '--'])
        self.assertEqual(calls[1].args[0], ['runuser', '-u', 'live', '--', '/usr/bin/xauth',
                         '-f', authority, 'generate', ':0', '.', 'trusted', 'timeout', '120'])
        self.assertEqual(calls[1].kwargs['env']['LANG'], 'C.UTF-8')

    def test_root_fixture_refuses_remote_display_or_nonprivate_authority(self):
        guest = self.guest_functions('authorize_x11')
        guest.update(P=Path, stat=stat, pwd=SimpleNamespace(getpwuid=lambda uid: SimpleNamespace(pw_name='live')))
        guest['command'] = Mock()
        for display, uid in [('remote.example:0', 1000), (':0', 0)]:
            with self.subTest(display=display, uid=uid), self.assertRaises(ValueError):
                guest['authorize_x11'](dict(DISPLAY=display, XDG_RUNTIME_DIR='/run/user/1000'), uid)
        self.assertFalse(guest['command'].called)
        for mode in (stat.S_IFDIR | 0o755, stat.S_IFLNK | 0o700):
            with self.subTest(mode=mode), patch.object(Path, 'lstat',
                    return_value=SimpleNamespace(st_uid=1000, st_mode=mode)), self.assertRaises(ValueError):
                guest['authorize_x11'](dict(DISPLAY=':0', XDG_RUNTIME_DIR='/run/user/1000'), 1000)
        self.assertFalse(guest['command'].called)

    def test_cancellation_evidence_includes_writes_discards_and_flushes(self):
        guest = self.guest_functions('disk_write_evidence')
        with tempfile.TemporaryDirectory() as temporary:
            disk = Path(temporary) / 'disk'
            with disk.open('wb') as stream:
                stream.truncate(32 * 1024 ** 3)
            import hashlib
            import builtins
            counters = '1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17'
            guest.update(serial=lambda: 'HUSK-DISPOSABLE', hashlib=hashlib,
                         P=lambda path: SimpleNamespace(read_text=lambda: counters),
                         open=lambda *args, **kwargs: builtins.open(disk, *args[1:], **kwargs))
            evidence = guest['disk_write_evidence']()
            self.assertEqual({key: evidence[key] for key in
                ('writes_completed', 'sectors_written', 'discards_completed', 'sectors_discarded', 'flushes_completed')},
                dict(writes_completed=5, sectors_written=7, discards_completed=12,
                     sectors_discarded=14, flushes_completed=16))

    def test_host_blockstats_require_zero_data_writes_and_discards_but_record_flushes(self):
        stats = dict(wr_bytes=0, wr_operations=0, unmap_bytes=0, unmap_operations=0,
                     failed_wr_operations=0, invalid_wr_operations=0,
                     failed_unmap_operations=0, invalid_unmap_operations=0, flush_operations=1)
        valid = [dict(device='optical', stats={}), dict(device='target', stats=stats)]
        self.assertEqual(self.harness.cancellation_blockstats(valid), stats)
        for field in stats.keys() - {'flush_operations'}:
            for value in (1, -1, None, True):
                with self.subTest(field=field, value=value):
                    changed = dict(stats, **{field: value})
                    with self.assertRaises(ValueError):
                        self.harness.cancellation_blockstats([dict(device='target', stats=changed)])
        for value in ([], [dict(device='other', stats=stats)],
                      [dict(device='target', stats=stats)] * 2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.harness.cancellation_blockstats(value)

    def test_guest_cancellation_requires_unchanged_data_counters_and_partition_edges(self):
        guest = self.guest_functions('unchanged_cancellation_data')
        before = dict(writes_completed=0, sectors_written=0, discards_completed=0,
                      sectors_discarded=0, flushes_completed=0, partition_edges_sha256='a' * 64)
        # Linux may count a zero-sector flush as a completed write. The host's
        # independent QMP check must additionally accept before installation.
        after = dict(before, writes_completed=1, flushes_completed=1)
        self.assertTrue(guest['unchanged_cancellation_data'](before, after))
        for change in (dict(sectors_written=1), dict(discards_completed=1), dict(sectors_discarded=1),
                       dict(partition_edges_sha256='b' * 64), dict(writes_completed=-1)):
            with self.subTest(change=change):
                self.assertFalse(guest['unchanged_cancellation_data'](before, dict(after, **change)))

    def test_cancellation_acknowledgement_is_withheld_until_independent_host_proof(self):
        acceptance = SimpleNamespace(token='test-token', resources={}, cancellation_verified=False)
        handler = self.harness.Acceptance.handler(acceptance)
        request = handler.__new__(handler)
        request.path = '/test-token/cancellation-reviewed'
        request.wfile = io.BytesIO()
        for method in ('send_error', 'send_response', 'send_header', 'end_headers'):
            setattr(request, method, Mock())
        request.do_GET()
        request.send_error.assert_called_once_with(503)
        self.assertEqual(request.wfile.getvalue(), b'')
        request.send_response.assert_not_called()
        acceptance.cancellation_verified = True
        request.do_GET()
        request.send_response.assert_called_once_with(200)
        self.assertEqual(request.wfile.getvalue(), b'REVIEWED\n')
        request.send_error.reset_mock()
        request.path = '/wrong-token/cancellation-reviewed'
        request.do_GET()
        request.send_error.assert_called_once_with(404)

    def test_saved_text_redacts_generated_password_and_upstream_crypt_arguments(self):
        self.assertTrue(hasattr(self.harness,'redact_artifact_text'), 'Evidence redaction is missing')
        password='DisposableGeneratedSecret739'
        crypt='$y$j9T$testSalt123$testHash456abcdefghijklmnop'
        text='Create user huskcheck\npassword='+password+'\nusermod -p '+crypt+' huskcheck\n'
        safe=self.harness.redact_artifact_text(text,password)
        self.assertNotIn(password,safe)
        self.assertNotIn(crypt,safe)
        self.assertIn('Create user huskcheck',safe)


if __name__ == '__main__':
    unittest.main()
