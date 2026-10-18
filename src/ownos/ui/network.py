"""Nearby Wi-Fi selection and NetworkManager diagnostics for Husk Desktop."""
from ownos.i18n import _
from ownos.network import NetworkManagerController, NetworkSnapshot, network_diagnostics
from ownos.ui.common import Gtk, GLib, spawn


SECURITY_LABELS = {
    'open': 'Open network', 'wpa-psk': 'WPA/WPA2 Personal', 'sae': 'WPA3 Personal',
    'owe': 'Enhanced Open', 'enterprise': 'Enterprise · use Advanced settings',
    'wep': 'WEP · use Advanced settings',
}


def _text(label='', wrap=True):
    widget = Gtk.Label(label=label, xalign=0)
    widget.set_line_wrap(wrap)
    widget.set_selectable(True)
    return widget


def configure_password_entry(entry):
    # GTK3 uses PASSWORD purpose to mark private input. GTK4's PRIVATE hint is
    # absent from GTK3, which is the desktop's supported toolkit.
    entry.set_visibility(False)
    entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
    entry.set_input_hints(Gtk.InputHints.NO_SPELLCHECK | Gtk.InputHints.NO_EMOJI)


class NetworkWindow(Gtk.Window):
    def __init__(self, parent=None, controller=None):
        super().__init__(title=_('Husk Network'))
        self.set_default_size(640, 700)
        if parent is not None:
            self.set_transient_for(parent)
            self.set_destroy_with_parent(True)
        self.controller = controller if controller is not None else NetworkManagerController()
        self.snapshot = NetworkSnapshot()
        self.selected_path = None
        self.disconnect_interface = None
        self.rendering = False
        self.rows_signature = None
        self.timer = None
        self.connect('destroy', self._closed)
        self.connect('delete-event', lambda *_: (self.destroy(), True)[1])

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.add(scroll)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.set_border_width(20)
        scroll.add(box)
        header = Gtk.Box(spacing=12)
        heading = _text(_('Wi-Fi and Ethernet'))
        heading.get_style_context().add_class('heading')
        header.pack_start(heading, True, True, 0)
        self.refresh_button = Gtk.Button(label=_('Refresh'))
        self.refresh_button.connect('clicked', lambda _: self.controller.refresh(scan=True))
        header.pack_end(self.refresh_button, False, False, 0)
        box.pack_start(header, False, False, 0)
        radio = Gtk.Box(spacing=12)
        radio.pack_start(_text(_('Wi-Fi')), True, True, 0)
        self.wifi_switch = Gtk.Switch()
        self.wifi_switch.set_valign(Gtk.Align.CENTER)
        self.wifi_switch.connect('notify::active', self._wireless_changed)
        radio.pack_end(self.wifi_switch, False, False, 0)
        box.pack_start(radio, False, False, 0)
        self.status = _text(_('Connecting to NetworkManager…'))
        box.pack_start(self.status, False, False, 0)
        self.network_list = Gtk.ListBox()
        self.network_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.network_list.connect('row-selected', self._selected)
        network_scroll = Gtk.ScrolledWindow()
        network_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        network_scroll.set_min_content_height(180)
        network_scroll.add(self.network_list)
        box.pack_start(network_scroll, True, True, 0)
        self.empty = _text(_('No nearby Wi-Fi networks are available. Turn Wi-Fi on and refresh. Hidden networks can be added in Advanced settings.'))
        self.empty.set_no_show_all(True)
        box.pack_start(self.empty, False, False, 0)
        self.selection_status = _text(_('Select a nearby Wi-Fi network.'))
        box.pack_start(self.selection_status, False, False, 0)

        self.password_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.password_box.set_no_show_all(True)
        self.password_box.pack_start(_text(_('Wi-Fi password')), False, False, 0)
        self.password = Gtk.Entry()
        configure_password_entry(self.password)
        self.password.connect('activate', lambda _: self._connect_selected())
        self.password_box.pack_start(self.password, False, False, 0)
        box.pack_start(self.password_box, False, False, 0)
        self.remember = Gtk.CheckButton(label=_('Remember new connection securely with NetworkManager'))
        self.remember.set_active(True)
        box.pack_start(self.remember, False, False, 0)
        actions = Gtk.Box(spacing=10)
        self.connect_button = Gtk.Button(label=_('Connect'))
        self.connect_button.connect('clicked', lambda _: self._connect_selected())
        actions.pack_start(self.connect_button, False, False, 0)
        self.disconnect_button = Gtk.Button(label=_('Disconnect Wi-Fi'))
        self.disconnect_button.connect('clicked', self._disconnect)
        actions.pack_start(self.disconnect_button, False, False, 0)
        advanced = Gtk.Button(label=_('Advanced settings'))
        advanced.connect('clicked', lambda _: spawn(['/usr/bin/nm-connection-editor'], self))
        actions.pack_end(advanced, False, False, 0)
        box.pack_start(actions, False, False, 0)

        details = Gtk.Expander(label=_('Interfaces and diagnostics'))
        detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        detail_box.set_margin_top(10)
        self.device_status = _text()
        detail_box.pack_start(self.device_status, False, False, 0)
        self.diagnostics = _text()
        detail_box.pack_start(self.diagnostics, False, False, 0)
        details.add(detail_box)
        box.pack_start(details, False, False, 0)
        self.details = details
        self._render(self.snapshot)
        self.controller.start(self._render)
        self.timer = GLib.timeout_add_seconds(3, self._poll)

    def _poll(self):
        self.controller.refresh()
        return True

    def _wireless_changed(self, switch, unused):
        if not self.rendering:
            self.controller.set_wireless(switch.get_active())

    def _render(self, snapshot):
        self.snapshot = snapshot
        self.rendering = True
        self.wifi_switch.set_active(snapshot.wireless_enabled)
        self.wifi_switch.set_sensitive(snapshot.ready and not snapshot.busy and snapshot.wireless_hardware_enabled)
        self.refresh_button.set_sensitive(not snapshot.busy)
        notes = network_diagnostics(snapshot)
        self.status.set_text(snapshot.message or (notes[0] if notes else _('Choose a nearby Wi-Fi network to connect.')))
        self.empty.set_visible(snapshot.ready and not snapshot.networks)
        signature = tuple(snapshot.networks)
        if signature != self.rows_signature:
            self.rows_signature = signature
            for row in self.network_list.get_children():
                self.network_list.remove(row)
            selected = None
            for network in snapshot.networks:
                row = Gtk.ListBoxRow()
                row.network = network
                content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
                content.set_border_width(10)
                name_label = _text(network.ssid, False)
                name_label.set_selectable(False)
                content.pack_start(name_label, False, False, 0)
                status = _('Connected') if network.connected else (_('Saved') if network.saved else '')
                detail = f'{network.strength}% · {SECURITY_LABELS.get(network.security, network.security)} · {network.interface}'
                if status:
                    detail += ' · ' + status
                detail_label = _text(detail)
                detail_label.set_selectable(False)
                content.pack_start(detail_label, False, False, 0)
                row.add(content)
                self.network_list.add(row)
                if network.path == self.selected_path:
                    selected = row
            self.network_list.show_all()
            if selected is not None:
                self.network_list.select_row(selected)
        self.device_status.set_text('\n\n'.join(
            f'{device.kind} · {device.interface} · {device.state}\n'
            + _('Driver: ') + (device.driver or _('not reported'))
            + ('\n' + _('IP: ') + ', '.join(device.addresses) if device.addresses else '')
            + ('\n' + _('DNS: ') + ', '.join(device.nameservers) if device.nameservers else '')
            for device in snapshot.devices) or _('No network interfaces reported.'))
        self.diagnostics.set_text('\n\n'.join(notes) or _('No adapter or DNS configuration problems reported.'))
        if notes:
            self.details.set_expanded(True)
        self.rendering = False
        self._selected(self.network_list, self.network_list.get_selected_row())

    def _selected(self, widget, row):
        if self.rendering:
            return
        network = row.network if row is not None else None
        path = network.path if network is not None else None
        if path != self.selected_path:
            self.password.set_text('')
        self.selected_path = path
        secured = network is not None and network.security in ('wpa-psk', 'sae')
        self.password_box.set_visible(secured)
        if secured:
            for child in self.password_box.get_children():
                child.show_all()
        self.password.set_placeholder_text(_('Leave blank to use saved password') if network is not None and network.saved else _('Password'))
        if network is None:
            self.selection_status.set_text(_('Select a nearby Wi-Fi network.'))
        else:
            self.selection_status.set_text(network.ssid + ' · ' + SECURITY_LABELS.get(network.security, network.security))
        can_connect = network is not None and network.security in ('open', 'wpa-psk', 'sae', 'owe') and not network.connected
        self.connect_button.set_sensitive(can_connect and self.snapshot.ready and self.snapshot.wireless_enabled and not self.snapshot.busy)
        connected = [device.interface for device in self.snapshot.devices if device.kind == 'Wi-Fi' and device.connected]
        self.disconnect_interface = network.interface if network is not None and network.interface in connected else next(iter(connected), None)
        self.disconnect_button.set_sensitive(bool(self.disconnect_interface) and not self.snapshot.busy)
        self.disconnect_button.set_tooltip_text(self.disconnect_interface or _('No connected Wi-Fi interface'))

    def _connect_selected(self):
        if self.selected_path is None or not self.connect_button.get_sensitive():
            return
        password = self.password.get_text()
        self.password.set_text('')
        self.controller.connect_network(self.selected_path, password, self.remember.get_active())

    def _disconnect(self, unused):
        if self.disconnect_interface is not None:
            self.controller.disconnect_wifi(self.disconnect_interface)

    def _closed(self, unused):
        self.password.set_text('')
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
        self.controller.close()
