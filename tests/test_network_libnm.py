"""Real libnm setting objects with a deterministic asynchronous D-Bus boundary.

No test changes the host's radios or network connections. Device/transport
fixtures substitute for hardware; connection verification uses real libnm.
"""
import unittest
from types import SimpleNamespace
from ownos.network import NetworkManagerController, WifiNetwork, build_wifi_connection


class AccessPoint:
    def __init__(self, nm, glib):
        self.nm, self.glib = nm, glib
        self.flags = getattr(nm, '80211ApSecurityFlags').KEY_MGMT_PSK

    def get_path(self): return '/org/freedesktop/NetworkManager/AccessPoint/1'
    def get_ssid(self): return self.glib.Bytes.new(b'Cafe: $(literal)')
    def get_strength(self): return 82
    def get_rsn_flags(self): return self.flags
    def get_wpa_flags(self): return 0
    def get_flags(self): return getattr(self.nm, '80211ApFlags').PRIVACY
    def connection_valid(self, profile): return True


class Device:
    def __init__(self, nm, interface, ap=None):
        self.nm, self.interface, self.ap = nm, interface, ap
        self.state = nm.DeviceState.DISCONNECTED
        self.disconnects = self.scans = 0
        self.saved = []

    def get_device_type(self): return self.nm.DeviceType.WIFI if self.ap else self.nm.DeviceType.ETHERNET
    def get_iface(self): return self.interface
    def get_state(self): return self.state
    def get_state_reason(self): return self.nm.DeviceStateReason.NONE
    def get_driver(self): return 'fixture-driver'
    def get_firmware_missing(self): return False
    def get_managed(self): return True
    def get_ip4_config(self): return None
    def get_ip6_config(self): return None
    def get_available_connections(self): return self.saved
    def get_access_points(self): return [self.ap] if self.ap else []
    def get_active_access_point(self): return self.ap if self.state == self.nm.DeviceState.ACTIVATED else None
    def request_scan_async(self, cancel, callback, data):
        self.scans += 1
        self.scan_callback = callback
    def request_scan_finish(self, result): return True
    def disconnect_async(self, cancel, callback, data): self.disconnects += 1
    def disconnect_finish(self, result): return True


class Client:
    def __init__(self, devices):
        self.devices = devices
        self.request = None
        self.error = None

    def get_nm_running(self): return True
    def get_devices(self): return self.devices
    def wireless_get_enabled(self): return True
    def wireless_hardware_get_enabled(self): return True
    def get_device_by_iface(self, interface): return next((d for d in self.devices if d.interface == interface), None)
    def add_and_activate_connection2(self, connection, device, path, options, cancel, callback, data):
        if self.error:
            raise self.error
        self.request = connection, device, path, options, callback, data
    def add_and_activate_connection2_finish(self, result): return object(), None
    def activate_connection_async(self, connection, device, path, cancel, callback, data):
        if self.error:
            raise self.error
        self.request = connection, device, path, None, callback, data
    def activate_connection_finish(self, result): return object()


class LibnmTests(unittest.TestCase):
    def setUp(self):
        try:
            import gi
            gi.require_version('NM', '1.0')
            from gi.repository import NM, GLib, Gio
        except (ImportError, ValueError) as exc:
            self.skipTest('libnm introspection unavailable: ' + str(exc))
        self.nm, self.glib, self.gio = NM, GLib, Gio
        self.ap = AccessPoint(NM, GLib)
        self.wifi = Device(NM, 'wlan0', self.ap)
        self.ethernet = Device(NM, 'eth0')
        self.client = Client([self.ethernet, self.wifi])
        self.controller = NetworkManagerController()
        self.controller.nm, self.controller.glib, self.controller.gio = NM, GLib, Gio
        self.controller.cancel = Gio.Cancellable()
        self.controller.client = self.client
        self.addCleanup(self.controller.close)
        self.controller.refresh()

    def test_personal_wifi_uses_verified_libnm_settings_and_unchanged_ssid_bytes(self):
        network = WifiNetwork('/ap', 'wlan0', b'Cafe: $()\xff', 'Cafe', 82, 'wpa-psk')
        connection = build_wifi_connection(self.nm, self.glib, network, '$(literal); password')
        self.assertTrue(connection.verify())
        self.assertEqual(bytes(connection.get_setting_wireless().get_ssid().get_data()), network.ssid_bytes)
        self.assertEqual(connection.get_setting_wireless_security().get_psk(), '$(literal); password')
        self.assertEqual(connection.get_setting_ip4_config().get_method(), 'auto')
        self.assertEqual(connection.get_setting_ip6_config().get_method(), 'auto')

    def test_open_network_has_no_password_setting(self):
        network = WifiNetwork('/ap', 'wlan0', b'Open', 'Open', 82, 'open')
        connection = build_wifi_connection(self.nm, self.glib, network, '')
        self.assertTrue(connection.verify())
        self.assertIsNone(connection.get_setting_wireless_security())

    def test_wpa3_and_enhanced_open_profiles_require_protected_management_frames(self):
        for security, password in [('sae', 'a long SAE passphrase ' * 8), ('owe', '')]:
            with self.subTest(security=security):
                network = WifiNetwork('/ap', 'wlan0', b'Cafe', 'Cafe', 82, security)
                connection = build_wifi_connection(self.nm, self.glib, network, password)
                self.assertTrue(connection.verify())
                self.assertEqual(connection.get_setting_wireless_security().get_pmf(), self.nm.SettingWirelessSecurityPmf.REQUIRED)

    def test_connect_uses_dbus_settings_with_session_profile_and_waits_for_actual_state(self):
        self.controller.connect_network(self.ap.get_path(), 'safe $() password', remember=False)
        connection, device, path, options, callback, data = self.client.request
        self.assertTrue(connection.verify())
        self.assertEqual(connection.get_setting_wireless_security().get_psk(), 'safe $() password')
        self.assertEqual(options.unpack()['persist'], 'volatile')
        self.assertIs(device, self.wifi)
        self.assertFalse(self.controller.snapshot.networks[0].connected)
        callback(self.client, object(), data)
        self.assertFalse(self.controller.snapshot.networks[0].connected)
        self.wifi.state = self.nm.DeviceState.ACTIVATED
        self.controller.refresh()
        self.assertTrue(self.controller.snapshot.networks[0].connected)

    def test_saved_profile_is_reused_without_requesting_or_exposing_its_secret(self):
        profile = self.nm.SimpleConnection.new()
        self.wifi.saved = [profile]
        self.controller.refresh()
        self.controller.connect_network(self.ap.get_path())
        self.assertIs(self.client.request[0], profile)
        self.assertEqual(self.client.request[-1], 'saved')

    def test_ethernet_is_preserved_and_only_wifi_can_be_disconnected(self):
        self.controller.disconnect_wifi('eth0')
        self.assertEqual(self.ethernet.disconnects, 0)
        self.controller.disconnect_wifi('wlan0')
        self.assertEqual(self.wifi.disconnects, 1)
        self.assertEqual(self.ethernet.disconnects, 0)

    def test_refresh_requests_scan_only_for_wifi(self):
        self.controller.refresh(scan=True)
        self.assertEqual(self.wifi.scans, 1)
        self.assertEqual(self.ethernet.scans, 0)
        self.assertTrue(self.controller.snapshot.busy)
        self.wifi.scan_callback(self.wifi, object())
        self.assertFalse(self.controller.snapshot.busy)

    def test_transport_error_cannot_echo_password_into_status(self):
        secret = 'private-test-passphrase'
        self.client.error = ValueError(secret)
        self.controller.connect_network(self.ap.get_path(), secret)
        self.assertNotIn(secret, self.controller.snapshot.message)
        self.assertIn('could not', self.controller.snapshot.message)

    def test_saved_connection_transport_failure_is_reported_without_crashing(self):
        self.wifi.saved = [self.nm.SimpleConnection.new()]
        self.client.error = RuntimeError('untrusted transport details')
        self.controller.refresh()
        self.controller.connect_network(self.ap.get_path())
        self.assertFalse(self.controller.snapshot.busy)
        self.assertNotIn('untrusted transport details', self.controller.snapshot.message)
        self.assertIn('could not', self.controller.snapshot.message)

    def test_enterprise_and_mixed_personal_security_classification(self):
        flags = getattr(self.nm, '80211ApSecurityFlags')
        self.ap.flags = flags.KEY_MGMT_802_1X
        self.controller.refresh()
        self.assertEqual(self.controller.snapshot.networks[0].security, 'enterprise')
        self.ap.flags = flags.KEY_MGMT_PSK | flags.KEY_MGMT_SAE
        self.controller.refresh()
        self.assertEqual(self.controller.snapshot.networks[0].security, 'wpa-psk')

    def test_password_entry_configuration_uses_supported_gtk3_privacy_controls(self):
        from ownos.ui import network
        configure = getattr(network, 'configure_password_entry', None)
        self.assertIsNotNone(configure, 'GTK3 password configuration is missing')
        from ownos.ui.common import Gtk
        settings = SimpleNamespace()
        entry = SimpleNamespace(set_visibility=lambda value: setattr(settings, 'visible', value),
                                set_input_purpose=lambda value: setattr(settings, 'purpose', value),
                                set_input_hints=lambda value: setattr(settings, 'hints', value))
        configure(entry)
        self.assertFalse(settings.visible)
        self.assertEqual(settings.purpose, Gtk.InputPurpose.PASSWORD)
        self.assertTrue(settings.hints & Gtk.InputHints.NO_SPELLCHECK)
        self.assertFalse(settings.hints & Gtk.InputHints.WORD_COMPLETION)


if __name__ == '__main__':
    unittest.main()
