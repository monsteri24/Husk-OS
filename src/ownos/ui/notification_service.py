from ownos.identity import OS_NAME, VERSION
from ownos.ui.common import Gio, GLib

XML = '''<node><interface name="org.freedesktop.Notifications">
<method name="GetCapabilities"><arg direction="out" type="as"/></method>
<method name="GetServerInformation"><arg direction="out" type="s"/><arg direction="out" type="s"/><arg direction="out" type="s"/><arg direction="out" type="s"/></method>
<method name="Notify"><arg direction="in" type="s"/><arg direction="in" type="u"/><arg direction="in" type="s"/><arg direction="in" type="s"/><arg direction="in" type="s"/><arg direction="in" type="as"/><arg direction="in" type="a{sv}"/><arg direction="in" type="i"/><arg direction="out" type="u"/></method>
<method name="CloseNotification"><arg direction="in" type="u"/></method>
<signal name="NotificationClosed"><arg type="u"/><arg type="u"/></signal>
</interface></node>'''


class NotificationService:
    def __init__(self, store, changed):
        self.store, self.changed = store, changed
        self.connection = None; self.registration = None; self.timeouts = {}
        self.stopped = False
        self.owner = Gio.bus_own_name(Gio.BusType.SESSION, 'org.freedesktop.Notifications',
            Gio.BusNameOwnerFlags.DO_NOT_QUEUE, self.acquired, None, None)

    def acquired(self, connection, _):
        if self.stopped: return
        self.connection = connection
        interface = Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
        self.registration = connection.register_object('/org/freedesktop/Notifications', interface, self.call, None, None)

    def call(self, connection, sender, path, interface, method, params, invocation):
        if method == 'GetCapabilities': invocation.return_value(GLib.Variant('(as)', (['body'],)))
        elif method == 'GetServerInformation': invocation.return_value(GLib.Variant('(ssss)', (OS_NAME, OS_NAME, VERSION, '1.2')))
        elif method == 'Notify':
            app, replaces, _icon, summary, body, _actions, _hints, timeout = params.unpack()
            n = self.store.notify(app, summary, body, replaces)
            if n.id in self.timeouts: GLib.source_remove(self.timeouts.pop(n.id))
            retained = {item.id for item in self.store.history}
            for old in list(self.timeouts):
                if old not in retained: GLib.source_remove(self.timeouts.pop(old))
            if timeout != 0:
                duration = 5000 if timeout < 0 else max(100, min(timeout, 120000))
                def expire():
                    self.timeouts.pop(n.id, None); self.close(n.id, 1); return False
                self.timeouts[n.id] = GLib.timeout_add(duration, expire)
            self.changed(); invocation.return_value(GLib.Variant('(u)', (n.id,)))
        elif method == 'CloseNotification':
            self.close(params.unpack()[0], 3); invocation.return_value(None)

    def close(self, identifier, reason=2):
        if identifier in self.timeouts: GLib.source_remove(self.timeouts.pop(identifier))
        if self.store.close(identifier) and self.connection:
            self.connection.emit_signal(None, '/org/freedesktop/Notifications',
                'org.freedesktop.Notifications', 'NotificationClosed', GLib.Variant('(uu)', (identifier, reason)))
        self.changed()

    def stop(self):
        self.stopped = True
        for source in self.timeouts.values(): GLib.source_remove(source)
        self.timeouts.clear()
        if self.registration and self.connection: self.connection.unregister_object(self.registration)
        if self.owner: Gio.bus_unown_name(self.owner); self.owner = None
