"""Adapter diagnostics and Blueman device controls for Husk Desktop."""
from ownos.bluetooth import BluetoothController, BluetoothSnapshot
from ownos.i18n import _
from ownos.ui.common import Gtk, GLib, spawn


class BluetoothWindow(Gtk.Window):
    def __init__(self, parent=None, controller=None):
        super().__init__(title=_('Husk Bluetooth'))
        self.set_default_size(520, 320)
        if parent is not None:
            self.set_transient_for(parent)
            self.set_destroy_with_parent(True)
        self.controller = controller if controller is not None else BluetoothController()
        self.rendering = False
        self.timer = None
        self.connect('destroy', self._closed)
        self.connect('delete-event', lambda *_: (self.destroy(), True)[1])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_border_width(24)
        self.add(box)
        header = Gtk.Box(spacing=12)
        title = Gtk.Label(label=_('Bluetooth'), xalign=0)
        title.get_style_context().add_class('heading')
        header.pack_start(title, True, True, 0)
        self.power_switch = Gtk.Switch()
        self.power_switch.set_valign(Gtk.Align.CENTER)
        self.power_switch.connect('notify::active', self._power_changed)
        header.pack_end(self.power_switch, False, False, 0)
        box.pack_start(header, False, False, 0)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        self.status.set_selectable(True)
        box.pack_start(self.status, False, False, 0)
        self.adapters = Gtk.Label(xalign=0)
        self.adapters.set_line_wrap(True)
        self.adapters.set_selectable(True)
        box.pack_start(self.adapters, False, False, 0)
        info = Gtk.Label(label=_('Bluetooth devices opens Blueman for discovery, pairing, connection and disconnection.'), xalign=0)
        info.set_line_wrap(True)
        box.pack_start(info, False, False, 0)
        actions = Gtk.Box(spacing=12)
        self.manage_button = Gtk.Button(label=_('Bluetooth devices'))
        self.manage_button.connect('clicked', lambda _: spawn(['/usr/bin/blueman-manager'], self))
        actions.pack_start(self.manage_button, False, False, 0)
        self.refresh_button = Gtk.Button(label=_('Refresh'))
        self.refresh_button.connect('clicked', lambda _: self.controller.refresh())
        actions.pack_end(self.refresh_button, False, False, 0)
        box.pack_end(actions, False, False, 0)
        self._render(BluetoothSnapshot())
        self.controller.start(self._render)
        self.timer = GLib.timeout_add_seconds(3, self._poll)

    def _render(self, snapshot):
        self.rendering = True
        self.power_switch.set_active(any(adapter.powered for adapter in snapshot.adapters))
        self.power_switch.set_sensitive(snapshot.ready and bool(snapshot.adapters) and not snapshot.blocks.hard and not snapshot.busy)
        self.refresh_button.set_sensitive(not snapshot.busy)
        self.status.set_text(snapshot.message)
        self.adapters.set_text('\n'.join(adapter.name + ' · ' + (_('On') if adapter.powered else _('Off')) for adapter in snapshot.adapters))
        self.rendering = False

    def _power_changed(self, switch, unused):
        if not self.rendering:
            self.controller.set_powered(switch.get_active())

    def _poll(self):
        self.controller.refresh()
        return True

    def _closed(self, unused):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
        self.controller.close()
