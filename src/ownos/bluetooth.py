"""BlueZ adapter status; device pairing is delegated to Blueman."""
from dataclasses import dataclass, replace
from ownos.network import RadioBlock, read_rfkill


@dataclass(frozen=True)
class BluetoothAdapter:
    path: str
    name: str
    powered: bool


@dataclass(frozen=True)
class BluetoothSnapshot:
    ready: bool = False
    adapters: tuple = ()
    blocks: RadioBlock = RadioBlock()
    message: str = 'Connecting to Bluetooth service…'
    busy: bool = False


def snapshot_from_objects(objects, blocks=RadioBlock()):
    adapters = []
    for path, interfaces in objects.items():
        props = interfaces.get('org.bluez.Adapter1')
        if props is not None:
            adapters.append(BluetoothAdapter(path, str(props.get('Alias') or props.get('Name') or path.rsplit('/', 1)[-1]), bool(props.get('Powered', False))))
    if blocks.hard:
        message = 'Bluetooth is blocked by a hardware switch. Check the wireless switch or BIOS/UEFI settings.'
    elif blocks.soft:
        message = 'Bluetooth is blocked by rfkill. Check airplane mode or run rfkill unblock bluetooth, then turn Bluetooth on.'
    elif not adapters:
        message = 'No Bluetooth adapter detected by BlueZ. Check the adapter, driver and firmware. A virtual machine needs a Bluetooth adapter passed through to the guest.'
    elif any(adapter.powered for adapter in adapters):
        message = 'Bluetooth is on. Open Bluetooth devices to discover, pair, connect or disconnect devices.'
    else:
        message = 'Bluetooth is off. Turn it on to discover and connect devices.'
    return BluetoothSnapshot(True, tuple(adapters), blocks, message)


class BluetoothController:
    """Read BlueZ adapters and change power through asynchronous D-Bus calls."""
    def __init__(self):
        self.snapshot = BluetoothSnapshot()
        self.changed = lambda snapshot: None
        self.connection = self.gio = self.glib = self.cancel = None
        self.closed = self.initializing = self.fetching = False
        self.pending = 0
        self.power_failed = False

    def _emit(self, snapshot):
        if not self.closed:
            self.snapshot = snapshot
            self.changed(snapshot)

    def start(self, changed):
        self.changed = changed
        if self.closed or self.initializing:
            return
        if self.connection is not None:
            self.refresh()
            return
        try:
            from gi.repository import Gio, GLib
            self.gio, self.glib = Gio, GLib
            self.cancel = Gio.Cancellable()
            self.initializing = True
            Gio.bus_get(Gio.BusType.SYSTEM, self.cancel, self._bus_ready, None)
        except ImportError:
            self._emit(BluetoothSnapshot(message='Bluetooth D-Bus bindings are unavailable. Check the python-gobject desktop dependency.'))

    def _bus_ready(self, source, result, unused=None):
        self.initializing = False
        try:
            connection = self.gio.bus_get_finish(result)
        except Exception:
            self._emit(BluetoothSnapshot(message='Cannot reach the system D-Bus. Bluetooth controls need the system D-Bus and bluetooth.service.'))
            return
        if self.closed:
            return
        self.connection = connection
        self.refresh()

    def refresh(self):
        if self.closed or self.fetching:
            return
        if self.connection is None:
            if not self.initializing:
                self.start(self.changed)
            return
        self.fetching = True
        try:
            self.connection.call(
                'org.bluez', '/', 'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects',
                None, self.glib.VariantType.new('(a{oa{sa{sv}}})'),
                self.gio.DBusCallFlags.NO_AUTO_START, 10000, self.cancel, self._objects_ready, None)
        except Exception:
            self.fetching = False
            self._emit(BluetoothSnapshot(message='Bluetooth service is unavailable on the system D-Bus. Check that bluez is installed and bluetooth.service is running.'))

    def _objects_ready(self, connection, result, unused=None):
        self.fetching = False
        try:
            objects = connection.call_finish(result).unpack()[0]
            snapshot = snapshot_from_objects(objects, read_rfkill(radio_type='bluetooth'))
            if self.power_failed:
                snapshot = replace(snapshot, message='Bluetooth power could not be changed. Check rfkill, the hardware switch and Bluetooth permissions. ' + snapshot.message)
            self._emit(replace(snapshot, busy=bool(self.pending)))
        except Exception:
            self._emit(BluetoothSnapshot(blocks=read_rfkill(radio_type='bluetooth'),
                                         message='Bluetooth service is unavailable on the system D-Bus. Check that bluez is installed and bluetooth.service is running.'))

    def set_powered(self, enabled):
        if self.closed or self.connection is None or self.pending or not self.snapshot.adapters:
            return
        self.pending = len(self.snapshot.adapters)
        self.power_failed = False
        self._emit(replace(self.snapshot, busy=True, message='Changing Bluetooth power…'))
        for adapter in self.snapshot.adapters:
            try:
                self.connection.call(
                    'org.bluez', adapter.path, 'org.freedesktop.DBus.Properties', 'Set',
                    self.glib.Variant('(ssv)', ('org.bluez.Adapter1', 'Powered', self.glib.Variant('b', bool(enabled)))),
                    None, self.gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION, 15000,
                    self.cancel, self._power_ready, None)
            except Exception:
                self.pending -= 1
                self.power_failed = True
        if self.power_failed and not self.pending:
            self._emit(replace(self.snapshot, busy=False,
                               message='Bluetooth power could not be changed. Check the system D-Bus and bluetooth.service, then refresh.'))

    def _power_ready(self, connection, result, unused=None):
        try:
            connection.call_finish(result)
        except Exception:
            self.power_failed = True
        self.pending -= 1
        if not self.pending:
            self.refresh()

    def close(self):
        self.closed = True
        if self.cancel is not None:
            self.cancel.cancel()
        self.changed = lambda snapshot: None
