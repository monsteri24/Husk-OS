"""Read-only live acceptance policy and virtual-display compatibility."""
import json
import os
import subprocess
from ownos.identity import OS_NAME, DESKTOP_NAME


def choose_renderer(vm_kind, current):
    if current: return current
    return 'pixman' if vm_kind in ('qemu','kvm','oracle','vmware','microsoft','bhyve') else ''


def session_renderer(current=None, detect=None):
    current = os.environ.get('WLR_RENDERER', '') if current is None else current
    if current: return current
    if detect is None:
        def detect():
            try:
                return subprocess.run(['/usr/bin/systemd-detect-virt','--vm'], capture_output=True,
                                      text=True, timeout=3).stdout.strip()
            except (OSError, subprocess.TimeoutExpired): return ''
    return choose_renderer(detect(), current)


def desktop_status(fetch=None):
    """Query the running shell, not a persisted or fabricated boot marker."""
    if fetch is None:
        from ownos.ui.common import Gio, GLib
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        def fetch():
            result = connection.call_sync('org.ownos.Desktop', '/org/ownos/Desktop',
                'org.ownos.Desktop', 'GetStatus', None, GLib.VariantType.new('(s)'),
                Gio.DBusCallFlags.NONE, 5000, None)
            return result.unpack()[0]
    payload = fetch()
    if not isinstance(payload, str) or len(payload.encode('utf-8')) > 65536:
        raise ValueError('Husk Desktop returned oversized or invalid status metadata.')
    status = json.loads(payload)
    if not isinstance(status, dict): raise ValueError('Husk Desktop status must be an object.')
    return status


def validate_live_status(status):
    if not isinstance(status, dict): return ['Husk Desktop returned invalid status metadata.']
    problems = []
    for key,value in [('os',OS_NAME),('desktop',DESKTOP_NAME),('backend','wayland')]:
        if status.get(key) != value: problems.append('Unexpected ' + key + ': ' + str(status.get(key)))
    for key in ('live','panel_visible','panel_mapped','bridge_connected'):
        if status.get(key) is not True: problems.append('Live check failed: ' + key)
    surfaces = status.get('desktop_surfaces')
    if type(surfaces) is not int or surfaces < 1: problems.append('No mapped desktop background surface.')
    return problems
