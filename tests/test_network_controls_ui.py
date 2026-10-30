"""GTK control tests with deterministic hardware state; no real radio changes."""
import importlib
import os
import unittest
from unittest.mock import patch

from ownos.network import NetworkDevice, NetworkSnapshot, WifiNetwork
from ownos.bluetooth import BluetoothSnapshot


class NetworkFixture:
    def __init__(self):
        self.snapshot = NetworkSnapshot(ready=True, devices=(
            NetworkDevice('eth0', 'Ethernet', 'Connected', True, addresses=('10.0.2.15',), nameservers=('10.0.2.3',)),
            NetworkDevice('wlan0', 'Wi-Fi', 'Disconnected'),
        ), networks=(WifiNetwork('/ap/1', 'wlan0', b'Cafe: $()', 'Cafe: $()', 85, 'wpa-psk'),
                     WifiNetwork('/ap/2', 'wlan0', b'Open', 'Open', 60, 'open')))
        self.connections, self.disconnections, self.refreshes = [], [], []
        self.closed = False

    def start(self, changed):
        self.changed = changed
        changed(self.snapshot)

    def connect_network(self, path, password='', remember=True):
        self.connections.append((path, password, remember))

    def disconnect_wifi(self, interface):
        self.disconnections.append(interface)

    def refresh(self, scan=False):
        self.refreshes.append(scan)

    def set_wireless(self, enabled):
        pass

    def close(self):
        self.closed = True


class BluetoothFixture:
    def __init__(self):
        self.snapshot = BluetoothSnapshot(ready=True, message='No Bluetooth adapter detected by BlueZ.')
        self.closed = False

    def start(self, changed):
        changed(self.snapshot)

    def refresh(self):
        pass

    def set_powered(self, enabled):
        pass

    def close(self):
        self.closed = True


@unittest.skipUnless(os.environ.get('OWNOS_UI_TESTS') == '1', 'Run inside a GTK test display')
class RadioControlUITests(unittest.TestCase):
    def setUp(self):
        try:
            self.network_ui = importlib.import_module('ownos.ui.network')
            self.bluetooth_ui = importlib.import_module('ownos.ui.bluetooth')
            from ownos.ui.common import Gtk
            self.Gtk = Gtk
        except ImportError as exc:
            self.fail('GTK radio controls missing: ' + str(exc))

    def drain(self):
        for _ in range(200):
            if not self.Gtk.events_pending():
                break
            self.Gtk.main_iteration_do(False)

    def window(self):
        controller = NetworkFixture()
        window = self.network_ui.NetworkWindow(controller=controller)
        self.addCleanup(window.destroy)
        window.show_all()
        self.drain()
        return window, controller

    def test_select_network_connects_with_masked_secret_and_clears_entry(self):
        window, controller = self.window()
        window.network_list.select_row(window.network_list.get_row_at_index(0))
        self.assertFalse(window.password.get_visibility())
        self.assertTrue(window.password.get_visible())
        window.password.set_text('$(literal); password')
        window.connect_button.clicked()
        self.assertEqual(controller.connections, [('/ap/1', '$(literal); password', True)])
        self.assertEqual(window.password.get_text(), '')
        self.assertIn('Ethernet', window.device_status.get_text())

    def test_selecting_open_network_clears_password_and_refresh_scans(self):
        window, controller = self.window()
        window.network_list.select_row(window.network_list.get_row_at_index(0))
        window.password.set_text('must not travel to another SSID')
        window.network_list.select_row(window.network_list.get_row_at_index(1))
        self.assertEqual(window.password.get_text(), '')
        self.assertFalse(window.password_box.get_visible())
        window.refresh_button.clicked()
        self.assertEqual(controller.refreshes, [True])

    def test_ethernet_cannot_be_disconnected_from_wifi_window(self):
        window, controller = self.window()
        self.assertFalse(window.disconnect_button.get_sensitive())
        self.assertEqual(controller.disconnections, [])

    def test_bluetooth_without_adapter_is_explicit_and_manager_is_available(self):
        controller = BluetoothFixture()
        window = self.bluetooth_ui.BluetoothWindow(controller=controller)
        self.addCleanup(window.destroy)
        window.show_all()
        self.assertIn('No Bluetooth adapter', window.status.get_text())
        self.assertFalse(window.power_switch.get_sensitive())
        with patch.object(self.bluetooth_ui, 'spawn') as launch:
            window.manage_button.clicked()
        launch.assert_called_once_with(['/usr/bin/blueman-manager'], window)

    def test_destroy_stops_controller(self):
        window, controller = self.window()
        window.destroy()
        self.assertTrue(controller.closed)


if __name__ == '__main__':
    unittest.main()
