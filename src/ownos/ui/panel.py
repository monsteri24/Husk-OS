"""Husk Desktop taskbar composition; appearance/layout can evolve independently."""
import cairo
from ownos.desktop_layout import layout
from ownos.i18n import _
from ownos.panel_state import panel_mode
from ownos.ui.common import Gtk, icon_button, launch_app, spawn


COMPACT_STYLE = b'''
window.panel.panel-compact {
    background-color: transparent; background-image: none; border: none;
    padding: 0; box-shadow: none; transition-duration: 0s;
}
window.panel.panel-compact button {
    padding: 3px; min-width: 24px; min-height: 24px; border-radius: 8px;
}
'''


class Panel:
    def __init__(self, shell):
        self.shell = shell
        self.position = shell.settings['taskbar_position']
        self.mode = 'desktop'
        self.controls = {}
        self.window = shell.make_window(_('Husk Taskbar'), 1000, 62, 'TOP', layout(shell.settings)['panel_anchors'])
        self.window.get_style_context().add_class('panel')
        self.provider = Gtk.CssProvider(); self.provider.load_from_data(COMPACT_STYLE)
        Gtk.StyleContext.add_provider_for_screen(self.window.get_screen(), self.provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self.window.connect('destroy', self.destroy)
        self.window.connect('size-allocate', self.update_input_region)
        self.window.connect('map-event', self.update_input_region)
        if shell.layer:
            shell.layer.auto_exclusive_zone_enable(self.window)
            shell.layer.set_keyboard_mode(self.window, shell.layer.KeyboardMode.NONE)
        outer = Gtk.Box(spacing=10); self.window.add(outer)
        self.left = Gtk.Label(label=_('Husk OS · Experimental')); self.left.get_style_context().add_class('muted')
        self.left.set_size_request(180, -1); outer.pack_start(self.left, False, False, 0)
        center = self.center = Gtk.Box(spacing=7); outer.set_center_widget(center)
        center.pack_start(icon_button('husk-start', _('Start · Super+Space'), shell.toggle_start), False, False, 0)
        for appid, name in [('steam','steam'), ('heroic','com.heroicgameslauncher.hgl')]:
            center.pack_start(icon_button(name, appid.capitalize(), lambda id=appid: launch_app(id, shell.panel), fallback='husk-games'), False, False, 0)
        center.pack_start(icon_button('husk-files', _('Husk Files'), lambda: spawn(['/usr/bin/husk-files'], shell.panel)), False, False, 0)
        center.pack_start(icon_button('husk-settings', _('Husk Settings · Gaming Control Center'), lambda: spawn(['/usr/bin/husk-control'], shell.panel)), False, False, 0)
        self.tasks = Gtk.Box(spacing=5); center.pack_start(self.tasks, False, False, 0)
        status = self.status = Gtk.Box(spacing=8); status.set_size_request(260, -1); outer.pack_end(status, False, False, 0)
        self.network = Gtk.Button(label=_('Network')); self.network.set_tooltip_text(_('Network connection settings'))
        self.network.connect('clicked', lambda _: self.open_control('network'))
        status.pack_start(self.network, False, False, 0)
        self.volume = icon_button('audio-volume-high-symbolic', _('Volume'), shell.audio_dialog)
        status.pack_start(self.volume, False, False, 0)
        self.bluetooth = icon_button('bluetooth-symbolic', _('Bluetooth settings'), lambda: self.open_control('bluetooth'))
        status.pack_start(self.bluetooth, False, False, 0)
        self.clock = Gtk.Button(); self.clock.connect('clicked', lambda _: shell.toggle_notifications())
        self.clock.set_tooltip_text(_('Clock · Notification Center'))
        status.pack_start(self.clock, False, False, 0)
        self.window.show_all()

    def open_control(self, name):
        window = self.controls.get(name)
        if window is None:
            if name == 'network':
                from ownos.ui.network import NetworkWindow
                window = NetworkWindow(self.window)
            else:
                from ownos.ui.bluetooth import BluetoothWindow
                window = BluetoothWindow(self.window)
            self.controls[name] = window
            window.connect('destroy', lambda *_: self.controls.pop(name, None))
        window.show_all(); window.present()

    def destroy(self, *_):
        for window in list(self.controls.values()):
            window.destroy()
        Gtk.StyleContext.remove_provider_for_screen(self.window.get_screen(), self.provider)

    def refresh_visibility(self):
        display = self.shell.display
        monitor = self.shell.primary
        if monitor is None:
            return
        geometry = monitor.get_geometry()
        name = None
        # GTK 3 exposes the compositor's output name through GdkScreen.
        for index in range(display.get_n_monitors()):
            if display.get_monitor(index) == monitor:
                name = self.window.get_screen().get_monitor_plug_name(index)
                break
        mode = panel_mode(self.shell.toplevels.values(), output_name=name,
                          geometry=(geometry.x, geometry.y, geometry.width, geometry.height),
                          monitor_count=display.get_n_monitors())
        if mode == self.mode:
            self.update_input_region()
            return
        self.mode = mode
        context = self.window.get_style_context()
        if mode == 'desktop':
            context.remove_class('panel-compact')
            self.left.set_no_show_all(False); self.left.show()
            self.window.set_default_size(1000, 62); self.window.resize(1000, 62)
            if self.shell.layer:
                self.shell.layer.auto_exclusive_zone_enable(self.window)
        else:
            context.add_class('panel-compact')
            self.left.set_no_show_all(True); self.left.hide()
            self.window.set_default_size(1000, 42); self.window.resize(1000, 42)
            if self.shell.layer:
                # -1 lets the actual window use the whole output and ignores
                # other exclusive surfaces. It does not reserve a panel strip.
                self.shell.layer.set_exclusive_zone(self.window, -1)
        if mode == 'fullscreen':
            self.window.hide()
            for attribute in ('start_window', 'notification_window'):
                popup = getattr(self.shell, attribute, None)
                if popup is not None:
                    popup.hide()
        else:
            self.window.show_all()
        self.update_input_region()

    def update_input_region(self, *_):
        native = self.window.get_window()
        if native is None:
            return False
        if self.mode == 'desktop':
            # GDK's C API accepts NULL to reset the mask, but the GTK 3
            # introspection binding rejects None. Use the actual logical
            # allocation so restoring from compact mode covers the full bar.
            region = cairo.Region(cairo.RectangleInt(0, 0, self.window.get_allocated_width(),
                                                      self.window.get_allocated_height()))
            native.input_shape_combine_region(region, 0, 0)
            return False
        region = cairo.Region()
        def buttons(widget):
            if isinstance(widget, Gtk.Button):
                yield widget
            elif isinstance(widget, Gtk.Container):
                for child in widget.get_children():
                    yield from buttons(child)
        # Only visible controls take pointer input; every transparent gap
        # reaches the maximized application's content underneath the surface.
        for button in buttons(self.window):
            if not button.get_mapped():
                continue
            point = button.translate_coordinates(self.window, 0, 0)
            if point is not None:
                region.union(cairo.RectangleInt(point[0], point[1], button.get_allocated_width(),
                                                 button.get_allocated_height()))
        native.input_shape_combine_region(region, 0, 0)
        return False

    def refresh_tasks(self):
        for child in self.tasks.get_children(): self.tasks.remove(child)
        for identifier, entry in list(self.shell.toplevels.items())[:12]:
            button = icon_button(entry.get('app_id') or 'husk-app', entry.get('title') or _('Window'),
                                 lambda id=identifier: self.shell.bridge_command('activate', id))
            if entry.get('active'): button.get_style_context().add_class('active')
            def pressed(widget, event, id=identifier):
                if event.button != 3: return False
                menu = Gtk.Menu()
                for label, action in [(_('Activate'),'activate'), (_('Minimize'),'minimize'), (_('Close'),'close')]:
                    item = Gtk.MenuItem(label=label)
                    item.connect('activate', lambda _, a=action: self.shell.bridge_command(a, id)); menu.append(item)
                menu.show_all(); menu.popup_at_pointer(event); return True
            button.connect('button-press-event', pressed); self.tasks.pack_start(button, False, False, 0)
        self.tasks.show_all()
        self.refresh_visibility()
