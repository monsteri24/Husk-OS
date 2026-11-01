"""Wi-Fi models, hardware diagnostics and libnm credential boundaries."""
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class NetworkModelTests(unittest.TestCase):
    def setUp(self):
        try:
            self.network = importlib.import_module('ownos.network')
        except ImportError as exc:
            self.fail('Wi-Fi control implementation missing: ' + str(exc))

    def test_network_list_keeps_connected_ap_and_distinct_security(self):
        ap = self.network.WifiNetwork
        networks = self.network.visible_networks([
            ap('/weak', 'wlan0', b'Cafe', 'Cafe', 35, 'wpa-psk', True),
            ap('/strong', 'wlan0', b'Cafe', 'Cafe', 90, 'wpa-psk'),
            ap('/open', 'wlan0', b'Cafe', 'Cafe', 70, 'open'),
            ap('/other', 'wlan0', b'Other', 'Other', 95, 'sae'),
        ])
        self.assertEqual([item.path for item in networks], ['/weak', '/other', '/open'])

    def test_missing_adapter_explains_vm_and_driver_limit(self):
        snapshot = self.network.NetworkSnapshot(ready=True)
        text = '\n'.join(self.network.network_diagnostics(snapshot))
        self.assertIn('No Wi-Fi adapter', text)
        self.assertIn('virtual machine', text)
        self.assertIn('firmware', text)

    def test_absent_adapter_is_not_presented_as_a_hardware_switch_failure(self):
        snapshot = self.network.NetworkSnapshot(ready=True, wireless_hardware_enabled=False)
        text = '\n'.join(self.network.network_diagnostics(snapshot))
        self.assertIn('No Wi-Fi adapter', text)
        self.assertNotIn('blocked by a hardware switch', text)

    def test_connected_ethernet_remains_visible_when_wifi_absent(self):
        ethernet = self.network.NetworkDevice('eth0', 'Ethernet', 'Connected', True,
                                              driver='virtio_net', addresses=('10.0.2.15',),
                                              nameservers=('10.0.2.3',))
        snapshot = self.network.NetworkSnapshot(ready=True, devices=(ethernet,))
        self.assertEqual(snapshot.devices[0].interface, 'eth0')
        self.assertEqual(snapshot.devices[0].kind, 'Ethernet')
        self.assertNotIn('no DNS', '\n'.join(self.network.network_diagnostics(snapshot)))

    def test_connected_interface_without_dns_has_actionable_diagnostic(self):
        ethernet = self.network.NetworkDevice('eth0', 'Ethernet', 'Connected', True,
                                              addresses=('10.0.2.15',))
        snapshot = self.network.NetworkSnapshot(ready=True, devices=(ethernet,))
        self.assertIn('DNS', '\n'.join(self.network.network_diagnostics(snapshot)))

    def test_rfkill_distinguishes_hardware_and_software_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, hard, soft in [('rfkill0', '1', '0'), ('rfkill1', '0', '1')]:
                entry = root / 'class/rfkill' / name
                entry.mkdir(parents=True)
                for filename, content in [('type', 'wlan'), ('hard', hard), ('soft', soft)]:
                    (entry / filename).write_text(content)
            blocks = self.network.read_rfkill(root, 'wlan')
        self.assertTrue(blocks.hard)
        self.assertTrue(blocks.soft)

    def test_missing_pci_driver_reports_hardware_id_without_inventing_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pci = root / 'bus/pci/devices/0000:03:00.0'
            pci.mkdir(parents=True)
            (pci / 'class').write_text('0x028000')
            (pci / 'vendor').write_text('0x1234')
            (pci / 'device').write_text('0xabcd')
            notes = self.network.hardware_diagnostics(root)
        self.assertIn('1234:abcd', '\n'.join(notes))
        self.assertIn('no loaded driver', '\n'.join(notes))

    def test_wpa_password_validation_uses_bytes_and_accepts_literal_shell_text(self):
        validate = self.network.validate_password
        self.assertEqual(validate('wpa-psk', '$(never-run); secret'), '')
        self.assertEqual(validate('wpa-psk', 'a' * 64), '')
        self.assertNotEqual(validate('wpa-psk', 'short'), '')
        self.assertNotEqual(validate('wpa-psk', 'x' * 64), '')
        self.assertNotEqual(validate('wpa-psk', 'é' * 32), '')
        self.assertEqual(validate('sae', 'short'), '')
        self.assertEqual(validate('sae', 'long SAE password ' * 8), '')
        self.assertNotEqual(validate('sae', ''), '')

    def test_missing_libnm_is_reported_without_crashing_or_blocking(self):
        controller_type = getattr(self.network, 'NetworkManagerController', None)
        self.assertIsNotNone(controller_type, 'Asynchronous NetworkManager controller is missing')
        changes = []
        with patch.dict('sys.modules', {'gi': None}):
            controller = controller_type()
            controller.start(changes.append)
        self.assertFalse(changes[-1].ready)
        self.assertIn('libnm', changes[-1].message)
        controller.close()

    def test_device_failure_is_safe_and_explains_credentials_or_dhcp(self):
        message = getattr(self.network, 'failure_message', None)
        self.assertIsNotNone(message, 'Device failure explanation is missing')
        self.assertIn('password', message('no-secrets'))
        self.assertIn('DHCP', message('dhcp-failed'))
        self.assertNotIn('$(secret)', message('$(secret)'))


class BluetoothModelTests(unittest.TestCase):
    def setUp(self):
        try:
            self.bluetooth = importlib.import_module('ownos.bluetooth')
        except ImportError as exc:
            self.fail('Bluetooth control implementation missing: ' + str(exc))

    def test_no_adapter_is_distinct_from_powered_off_adapter(self):
        missing = self.bluetooth.snapshot_from_objects({})
        powered_off = self.bluetooth.snapshot_from_objects({
            '/org/bluez/hci0': {'org.bluez.Adapter1': {'Alias': 'USB Bluetooth', 'Powered': False}}
        })
        self.assertEqual(missing.adapters, ())
        self.assertIn('No Bluetooth adapter', missing.message)
        self.assertFalse(powered_off.adapters[0].powered)
        self.assertIn('off', powered_off.message)

    def test_bluez_adapter_state_is_reflected_without_claiming_pairing(self):
        snapshot = self.bluetooth.snapshot_from_objects({
            '/org/bluez/hci0': {'org.bluez.Adapter1': {'Alias': 'Built-in', 'Powered': True}},
            '/org/bluez/hci0/dev_00': {'org.bluez.Device1': {'Name': 'Headphones', 'Paired': True}}
        })
        self.assertEqual(len(snapshot.adapters), 1)
        self.assertEqual(snapshot.adapters[0].name, 'Built-in')
        self.assertIn('on', snapshot.message)

    def test_missing_dbus_bindings_reports_service_issue(self):
        controller_type = getattr(self.bluetooth, 'BluetoothController', None)
        self.assertIsNotNone(controller_type, 'Asynchronous BlueZ controller is missing')
        changes = []
        with patch.dict('sys.modules', {'gi': None}):
            controller = controller_type()
            controller.start(changes.append)
        self.assertFalse(changes[-1].ready)
        self.assertIn('D-Bus', changes[-1].message)
        controller.close()


if __name__ == '__main__':
    unittest.main()
