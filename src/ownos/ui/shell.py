import datetime
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path
from ownos.config import ConfigStore
from ownos.identity import OS_NAME, DESKTOP_NAME, VERSION
from ownos.desktop_layout import layout
from ownos.ui.panel import Panel
from ownos.ui.launcher import Launcher
from ownos.ui.wallpaper import Wallpaper
from ownos.i18n import _
from ownos.notifications import NotificationStore
from ownos.toplevel import ToplevelStore
from ownos.bridge import PipeLineReader
from ownos.ui.common import Gtk, Gdk, Gio, GLib, GdkPixbuf, icon, icon_button, load_style, remove_style, launch_app, open_path, spawn, error, require_display
from ownos.ui.notification_service import NotificationService

CONTROL_XML = '''<node><interface name="org.ownos.Desktop">
<method name="ToggleStart"/><method name="ToggleNotifications"/>
<method name="GetStatus"><arg name="status" type="s" direction="out"/></method>
</interface></node>'''


class HuskDesktop:
    def __init__(self, preview=False, store=None):
        require_display()
        self.preview = preview; self.store = store or ConfigStore(); self.settings = self.store.load()
        self.stopped = False; self.bridge = None; self.bridge_watch = None; self.bridge_reader = None
        self.bridge_connected = False
        self.window_store = ToplevelStore(); self.toplevels = self.window_store.entries
        self.windows = []; self.backgrounds = []; self.tasks = None; self.status_busy = False
        self.control_connection = None; self.control_registration = None
        self.layer = None
        if not preview:
            import gi
            gi.require_version('GtkLayerShell', '0.1')
            from gi.repository import GtkLayerShell
            if not GtkLayerShell.is_supported():
                raise RuntimeError('Husk Desktop requires a Wayland compositor supporting layer-shell. Use --preview for development.')
            self.layer = GtkLayerShell
        self.provider = load_style(self.settings, self.store.path.parent / "desktop.css")
        self.display = Gdk.Display.get_default()
        self.primary = self.display.get_primary_monitor() or self.display.get_monitor(0)
        self.notifications = NotificationStore()
        self.build_desktop(); self.build_panel(); self.build_start(); self.build_notifications()
        self.service = NotificationService(self.notifications, self.refresh_notifications)
        self.owner = Gio.bus_own_name(Gio.BusType.SESSION, 'org.ownos.Desktop',
            Gio.BusNameOwnerFlags.DO_NOT_QUEUE, self.control_acquired, None, None)
        self.store.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.config_monitor = Gio.File.new_for_path(str(self.store.path.parent)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self.config_monitor.connect('changed', self.settings_changed)
        self.clock_timer = GLib.timeout_add_seconds(1, self.tick)
        self.status_timer = GLib.timeout_add_seconds(10, self.update_status)
        self.tick(); self.update_status(); self.show_style_warning()
        if not preview: self.start_bridge()
        self.monitor_handlers = [self.display.connect('monitor-added', self.monitors_changed),
                                 self.display.connect('monitor-removed', self.monitors_changed)]

    def make_window(self, title, width, height, layer_name=None, anchors=(), monitor=None):
        window = Gtk.Window(title=title); window.set_default_size(width, height)
        window.set_decorated(self.preview); window.set_app_paintable(True)
        visual = window.get_screen().get_rgba_visual()
        if visual: window.set_visual(visual)
        if self.layer:
            ls = self.layer; ls.init_for_window(window)
            ls.set_namespace(window, 'ownos-' + title.lower().replace(' ', '-'))
            ls.set_layer(window, getattr(ls.Layer, layer_name)); ls.set_monitor(window, monitor or self.primary)
            for edge in anchors: ls.set_anchor(window, getattr(ls.Edge, edge), True)
            if layer_name == 'BACKGROUND':
                ls.set_keyboard_mode(window, ls.KeyboardMode.NONE)
                # Cover the output behind the panel, rather than shrinking the
                # wallpaper into the work area reserved by its exclusive zone.
                ls.set_exclusive_zone(window, -1)
            else: ls.set_keyboard_mode(window, ls.KeyboardMode.ON_DEMAND)
        self.windows.append(window)
        window.connect('delete-event', lambda *_: (window.hide(), True)[1])
        return window

    def build_desktop(self):
        for window in self.backgrounds:
            window.destroy()
            if window in self.windows: self.windows.remove(window)
        self.backgrounds = []
        monitors = [self.primary] if self.preview else [self.display.get_monitor(i) for i in range(self.display.get_n_monitors())]
        for monitor in monitors:
            geo = monitor.get_geometry()
            window = self.make_window(DESKTOP_NAME, 1000 if self.preview else geo.width,
                                      600 if self.preview else geo.height, 'BACKGROUND', ('TOP', 'BOTTOM', 'LEFT', 'RIGHT'), monitor)
            window.get_style_context().add_class('desktop')
            overlay = Gtk.Overlay(); window.add(overlay)
            background = Wallpaper(self.settings['wallpaper'])
            overlay.add(background)
            if monitor == self.primary:
                icons = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
                icons.set_margin_top(layout(self.settings)["desktop_margin_top"]); icons.set_margin_start(22)
                icons.set_halign(Gtk.Align.START); icons.set_valign(Gtk.Align.START)
                desktop = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP) or str(Path.home() / 'Desktop')
                entries = [Path.home()]
                try: entries += sorted(Path(desktop).iterdir(), key=lambda p: p.name.casefold())[:30]
                except OSError: pass
                for entry in entries:
                    button = Gtk.Button(); button.get_style_context().add_class('desktop-icon')
                    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
                    box.pack_start(icon('user-home' if entry == Path.home() else ('folder' if entry.is_dir() else 'text-x-generic'), 36), False, False, 0)
                    label = Gtk.Label(label=_('Home') if entry == Path.home() else entry.stem[:24]); label.set_max_width_chars(24)
                    box.pack_start(label, False, False, 0); button.add(box)
                    button.connect('clicked', lambda _, p=entry: self.open_desktop_entry(p))
                    icons.pack_start(button, False, False, 0)
                overlay.add_overlay(icons)
            window.show_all(); self.backgrounds.append(window)

    def open_desktop_entry(self, path):
        if path.is_dir(): spawn(['/usr/bin/husk-files', str(path)], self.panel)
        else: open_path(path, self.panel)

    def monitors_changed(self, *_):
        if self.stopped: return
        self.primary = self.display.get_primary_monitor() or self.display.get_monitor(0)
        # VT/output changes can briefly remove every monitor. Layer-shell
        # rejects a None monitor; keep the shell alive until an output returns.
        if self.primary is None: return
        self.build_desktop()
        if self.layer:
            for window in (self.panel, self.start_window, self.notification_window):
                self.layer.set_monitor(window, self.primary)

    def build_panel(self):
        self.taskbar = Panel(self)
        self.panel = self.taskbar.window
        self.tasks, self.network, self.clock = self.taskbar.tasks, self.taskbar.network, self.taskbar.clock

    def popup(self, title, width, height, right=False):
        edge = layout(self.settings)['popup_edge']
        anchors = (edge, 'RIGHT') if right else (edge,)
        window = self.make_window(title, width, height, 'OVERLAY', anchors)
        if self.layer:
            self.layer.set_margin(window, getattr(self.layer.Edge, edge), layout(self.settings)['popup_margin'])
            if right: self.layer.set_margin(window, self.layer.Edge.RIGHT, 16)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.get_style_context().add_class('popup'); window.add(box)
        return window, box

    def build_start(self):
        self.launcher = Launcher(self)
        self.start_window, self.search, self.app_list = self.launcher.window, self.launcher.search, self.launcher.app_list
        self.system_apps = self.launcher.system_apps

    def refresh_apps(self): self.launcher.refresh()
    def launch_desktop(self, info): self.launcher.launch_desktop(info)
    def app_activated(self, widget, row): self.launcher.activate(widget, row)
    def toggle_start(self): self.launcher.toggle()

    def build_notifications(self):
        self.notification_window, box = self.popup('Husk Notifications', 370, 480, True)
        label = Gtk.Label(label=_('Notification Center'), xalign=0); label.get_style_context().add_class('heading')
        box.pack_start(label, False, False, 0)
        self.notification_list = Gtk.ListBox(); self.notification_list.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll = Gtk.ScrolledWindow(); scroll.add(self.notification_list); box.pack_start(scroll, True, True, 0)
        clear = Gtk.Button(label=_('Clear Notifications')); clear.connect('clicked', self.clear_notifications)
        box.pack_end(clear, False, False, 0)

    def refresh_notifications(self):
        for child in self.notification_list.get_children(): self.notification_list.remove(child)
        for item in reversed(self.notifications.history):
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6); row.set_border_width(10)
            for text in (item.app, item.summary, item.body):
                label = Gtk.Label(label=text, xalign=0); label.set_line_wrap(True); label.set_max_width_chars(35)
                row.pack_start(label, False, False, 0)
            self.notification_list.add(row)
        self.notification_list.show_all()
        self.tick()

    def clear_notifications(self, _):
        for item in list(self.notifications.history): self.service.close(item.id)
        self.notifications.history.clear(); self.refresh_notifications()

    def toggle_notifications(self):
        if self.notification_window.get_visible(): self.notification_window.hide()
        else:
            self.start_window.hide(); self.notification_window.show_all()

    def tick(self):
        if self.stopped: return False
        unread = sum(item.active for item in self.notifications.history)
        self.clock.set_label(datetime.datetime.now().strftime('%H:%M\n%d.%m.') + (' · ' + str(unread) if unread else ''))
        return True

    def update_status(self):
        if self.stopped: return False
        if self.status_busy: return True
        self.status_busy = True
        def read():
            label = _('Network: Unknown')
            try:
                result = subprocess.run(['/usr/bin/nmcli', '-t', '-f', 'STATE', 'general'], capture_output=True, text=True, timeout=3)
                if result.returncode == 0: label = _('Connected ✓') if result.stdout.strip() in ('connected', 'connected (global)') else _('Disconnected')
            except (OSError, subprocess.TimeoutExpired): pass
            def update():
                self.status_busy = False
                if not self.stopped: self.network.set_label(label)
                return False
            GLib.idle_add(update)
        threading.Thread(target=read, daemon=True).start()
        return True

    def audio_dialog(self):
        dialog = Gtk.Dialog(title=_('Volume'), transient_for=self.panel, modal=True)
        dialog.add_button(_('Close'), Gtk.ResponseType.CLOSE)
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1); scale.set_size_request(300, 70)
        try:
            result = subprocess.run(['/usr/bin/wpctl', 'get-volume', '@DEFAULT_AUDIO_SINK@'], capture_output=True, text=True, timeout=2)
            scale.set_value(float(result.stdout.split()[1]) * 100)
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            error(self.panel, _('No default PipeWire audio device was found.')); dialog.destroy(); return
        scale.connect('value-changed', lambda widget: spawn(['/usr/bin/wpctl', 'set-volume', '--limit', '1.0', '@DEFAULT_AUDIO_SINK@', f'{widget.get_value():.0f}%'], self.panel))
        dialog.get_content_area().add(scale); dialog.show_all(); dialog.run(); dialog.destroy()

    def settings_changed(self, _, file, other, event):
        names = {item.get_basename() for item in (file, other) if item is not None}
        if self.stopped or not names.intersection({'settings.json', 'desktop.css'}): return
        self.reload_settings()

    def reload_settings(self):
        previous = self.settings
        self.settings = self.store.load()
        remove_style(self.provider)
        self.provider = load_style(self.settings, self.store.path.parent / 'desktop.css')
        self.build_desktop()
        if self.settings['taskbar_position'] != previous['taskbar_position']:
            for window in (self.panel, self.start_window, self.notification_window):
                self.windows.remove(window); window.destroy()
            self.build_panel(); self.build_start(); self.build_notifications()
            self.refresh_tasks(); self.refresh_notifications(); self.tick(); self.update_status()
        self.show_style_warning()

    def show_style_warning(self):
        warning = self.provider.husk_style_warning
        if warning and warning != getattr(self, 'last_style_warning', ''):
            self.notifications.notify(DESKTOP_NAME, _('Custom CSS was skipped'), warning)
            self.refresh_notifications()
        self.last_style_warning = warning

    def control_acquired(self, connection, _):
        if self.stopped: return
        self.control_connection = connection
        interface = Gio.DBusNodeInfo.new_for_xml(CONTROL_XML).interfaces[0]
        def call(conn, sender, path, interface, method, parameters, invocation):
            if method == 'ToggleStart': self.toggle_start()
            elif method == 'ToggleNotifications': self.toggle_notifications()
            elif method == 'GetStatus':
                invocation.return_value(GLib.Variant('(s)',(json.dumps(self.status()),))); return
            invocation.return_value(None)
        self.control_registration = connection.register_object('/org/ownos/Desktop', interface, call, None, None)

    def status(self):
        try:
            release = Path('/etc/os-release').read_text().splitlines()
            is_husk = 'ID=huskos' in release or 'ID="huskos"' in release
        except OSError: is_husk = False
        return dict(os=OS_NAME, desktop=DESKTOP_NAME, version=VERSION,
                    live=is_husk and Path('/run/archiso').is_dir(),
                    keyring_ready=Path('/run/ownos-live-keyring-ready').is_file(),
                    backend='preview' if self.preview else 'wayland',
                    desktop_surfaces=sum(window.get_mapped() for window in self.backgrounds),
                    panel_visible=self.panel.get_visible(), panel_mapped=self.panel.get_mapped(),
                    bridge_connected=self.bridge_connected and self.bridge is not None and self.bridge.poll() is None,
                    window_count=len(self.toplevels), renderer=os.environ.get('WLR_RENDERER','auto'))

    def start_bridge(self):
        executable = shutil.which('own-toplevel')
        if not executable:
            self.notifications.notify(DESKTOP_NAME, _('Window list unavailable'), _('The own-toplevel helper is missing.'))
            self.refresh_notifications(); return
        try:
            self.bridge = subprocess.Popen([executable], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        except OSError as exc:
            self.notifications.notify(DESKTOP_NAME, _('Window list could not start'), str(exc))
            self.refresh_notifications(); return
        self.bridge_reader = PipeLineReader(self.bridge.stdout.fileno())
        self.bridge_watch = GLib.io_add_watch(self.bridge.stdout.fileno(), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.bridge_event)

    def bridge_event(self, stream, condition):
        lines, ended = self.bridge_reader.read_ready()
        changed = False
        for line in lines:
            try:
                message = json.loads(line)
                if isinstance(message,dict) and message.get('event') == 'ready':
                    self.bridge_connected = message.get('foreign_toplevel') is True and message.get('seat') is True
                else: changed = self.window_store.apply(message) or changed
            except (ValueError, TypeError): pass
        if changed: self.refresh_tasks()
        if ended:
            self.bridge_connected = False
            self.bridge_watch = None; self.toplevels.clear(); self.refresh_tasks()
            if not self.stopped:
                self.notifications.notify(DESKTOP_NAME, _('Window list disconnected'), _('The compositor foreign-toplevel protocol or helper is unavailable.'))
                self.refresh_notifications()
            return False
        return True

    def bridge_command(self, action, id):
        if self.bridge and self.bridge.poll() is None:
            try: self.bridge.stdin.write(f'{action} {int(id)}\n'); self.bridge.stdin.flush()
            except (OSError, ValueError): pass

    def refresh_tasks(self): self.taskbar.refresh_tasks()

    def shutdown(self):
        if self.stopped: return
        self.stopped = True
        for handler in self.monitor_handlers: self.display.disconnect(handler)
        for source in (self.clock_timer, self.status_timer, self.bridge_watch):
            if source: GLib.source_remove(source)
        self.config_monitor.cancel(); self.service.stop()
        if self.control_registration and self.control_connection: self.control_connection.unregister_object(self.control_registration)
        Gio.bus_unown_name(self.owner)
        if self.bridge:
            if self.bridge.poll() is None: self.bridge.terminate()
            try: self.bridge.wait(timeout=2)
            except subprocess.TimeoutExpired: self.bridge.kill(); self.bridge.wait()
            self.bridge.stdin.close(); self.bridge.stdout.close()
        for window in self.windows: window.destroy()
        remove_style(self.provider)


# Compatibility for existing integrations and tests.
OwnShell = HuskDesktop

def main(preview=False):
    shell = OwnShell(preview=preview)
    import signal
    def stop(*_): shell.shutdown(); Gtk.main_quit(); return False
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, stop)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, stop)
    try: Gtk.main()
    finally: shell.shutdown()
