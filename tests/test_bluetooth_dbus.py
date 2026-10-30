"""BlueZ D-Bus payload tests without changing the host's adapters."""
import unittest
from ownos.bluetooth import BluetoothController


class Bus:
    def __init__(self):
        self.calls = []
        self.result = None
        self.error = None

    def call(self, *args):
        if self.error:
            raise self.error
        self.calls.append(args)

    def call_finish(self, result):
        if self.error:
            raise self.error
        return self.result


class BluetoothDbusTests(unittest.TestCase):
    def setUp(self):
        try:
            from gi.repository import Gio, GLib
        except ImportError as exc:
            self.skipTest('GObject introspection unavailable: ' + str(exc))
        self.gio, self.glib = Gio, GLib
        self.bus = Bus()
        self.bus.result = GLib.Variant('(a{oa{sa{sv}}})', ({
            '/org/bluez/hci0': {'org.bluez.Adapter1': {
                'Alias': GLib.Variant('s', 'USB Adapter'),
                'Powered': GLib.Variant('b', False),
            }}
        },))
        self.controller = BluetoothController()
        self.controller.connection = self.bus
        self.controller.gio, self.controller.glib = Gio, GLib
        self.controller.cancel = Gio.Cancellable()
        self.addCleanup(self.controller.close)

    def read_adapters(self):
        self.controller.refresh()
        call = self.bus.calls[-1]
        self.assertEqual(call[:4], ('org.bluez', '/', 'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects'))
        call[-2](self.bus, object(), call[-1])

    def test_refresh_reads_actual_bluez_variant_structure(self):
        self.read_adapters()
        self.assertTrue(self.controller.snapshot.ready)
        self.assertEqual(self.controller.snapshot.adapters[0].name, 'USB Adapter')
        self.assertFalse(self.controller.snapshot.adapters[0].powered)

    def test_adapter_enable_uses_properties_set_and_waits_for_bluez_state(self):
        self.read_adapters()
        self.controller.set_powered(True)
        call = self.bus.calls[-1]
        self.assertEqual(call[:4], ('org.bluez', '/org/bluez/hci0', 'org.freedesktop.DBus.Properties', 'Set'))
        self.assertEqual(call[4].unpack(), ('org.bluez.Adapter1', 'Powered', True))
        self.assertTrue(self.controller.snapshot.busy)
        self.assertFalse(self.controller.snapshot.adapters[0].powered)
        call[-2](self.bus, object(), call[-1])
        self.assertEqual(self.bus.calls[-1][3], 'GetManagedObjects')

    def test_missing_service_reports_bluetooth_service_guidance(self):
        self.controller.refresh()
        self.bus.error = RuntimeError('opaque system transport detail')
        self.controller._objects_ready(self.bus, object())
        self.assertFalse(self.controller.snapshot.ready)
        self.assertIn('bluetooth.service', self.controller.snapshot.message)
        self.assertNotIn('opaque system transport detail', self.controller.snapshot.message)

    def test_power_request_transport_failure_is_visible_without_raising(self):
        self.read_adapters()
        self.bus.error = RuntimeError('opaque power transport detail')
        self.controller.set_powered(True)
        self.assertFalse(self.controller.snapshot.busy)
        self.assertIn('could not', self.controller.snapshot.message)
        self.assertNotIn('opaque power transport detail', self.controller.snapshot.message)


if __name__ == '__main__':
    unittest.main()
