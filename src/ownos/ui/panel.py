"""Husk Desktop taskbar composition; appearance/layout can evolve independently."""
from ownos.desktop_layout import layout
from ownos.i18n import _
from ownos.ui.common import Gtk, icon_button, launch_app, spawn


class Panel:
    def __init__(self, shell):
        self.shell = shell
        self.position = shell.settings['taskbar_position']
        self.window = shell.make_window(_('Husk Taskbar'), 1000, 62, 'TOP', layout(shell.settings)['panel_anchors'])
        self.window.get_style_context().add_class('panel')
        if shell.layer:
            shell.layer.auto_exclusive_zone_enable(self.window)
            shell.layer.set_keyboard_mode(self.window, shell.layer.KeyboardMode.NONE)
        outer = Gtk.Box(spacing=10); self.window.add(outer)
        left = Gtk.Label(label=_('Husk OS · Experimental')); left.get_style_context().add_class('muted')
        left.set_size_request(180, -1); outer.pack_start(left, False, False, 0)
        center = Gtk.Box(spacing=7); outer.set_center_widget(center)
        center.pack_start(icon_button('view-app-grid-symbolic', _('Start · Super+Space'), shell.toggle_start), False, False, 0)
        for appid, name in [('steam','steam'), ('heroic','com.heroicgameslauncher.hgl')]:
            center.pack_start(icon_button(name, appid.capitalize(), lambda id=appid: launch_app(id, shell.panel)), False, False, 0)
        center.pack_start(icon_button('folder-symbolic', _('Husk Files'), lambda: spawn(['/usr/bin/husk-files'], shell.panel)), False, False, 0)
        center.pack_start(icon_button('preferences-system-symbolic', _('Husk Settings · Gaming Control Center'), lambda: spawn(['/usr/bin/husk-control'], shell.panel)), False, False, 0)
        self.tasks = Gtk.Box(spacing=5); center.pack_start(self.tasks, False, False, 0)
        status = Gtk.Box(spacing=8); status.set_size_request(230, -1); outer.pack_end(status, False, False, 0)
        self.network = Gtk.Button(label=_('Network')); self.network.set_tooltip_text(_('Network connection settings'))
        self.network.connect('clicked', lambda _: spawn(['/usr/bin/nm-connection-editor'], shell.panel))
        status.pack_start(self.network, False, False, 0)
        status.pack_start(icon_button('audio-volume-high-symbolic', _('Volume'), shell.audio_dialog), False, False, 0)
        self.clock = Gtk.Button(); self.clock.connect('clicked', lambda _: shell.toggle_notifications())
        status.pack_end(self.clock, False, False, 0)
        self.window.show_all()

    def refresh_tasks(self):
        for child in self.tasks.get_children(): self.tasks.remove(child)
        for identifier, entry in list(self.shell.toplevels.items())[:12]:
            button = Gtk.Button(label=(entry.get('app_id') or entry.get('title') or _('Window'))[:16])
            button.set_tooltip_text(entry.get('title', _('Window')))
            if entry.get('active'): button.get_style_context().add_class('active')
            button.connect('clicked', lambda _, id=identifier: self.shell.bridge_command('activate', id))
            def pressed(widget, event, id=identifier):
                if event.button != 3: return False
                menu = Gtk.Menu()
                for label, action in [(_('Activate'),'activate'), (_('Minimize'),'minimize'), (_('Close'),'close')]:
                    item = Gtk.MenuItem(label=label)
                    item.connect('activate', lambda _, a=action: self.shell.bridge_command(a, id)); menu.append(item)
                menu.show_all(); menu.popup_at_pointer(event); return True
            button.connect('button-press-event', pressed); self.tasks.pack_start(button, False, False, 0)
        self.tasks.show_all()
