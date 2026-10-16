"""Prepare and launch the Wayland session, with a private diagnostic log."""
import datetime
import os
import shutil
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from ownos.config import ConfigStore
from ownos.i18n import _
from ownos.input_config import _replace, write_input_config
from ownos.live import session_renderer


LOG_LIMIT = 1024 * 1024
LEGACY_AUTOSTART = '''#!/bin/sh
dbus-update-activation-environment --systemd WAYLAND_DISPLAY DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE
/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 &
husk-desktop &
if [ ! -d /run/archiso ] && [ -x /usr/bin/swayidle ]; then
    swayidle -w timeout 600 'swaylock -f -c 0b1321' before-sleep 'swaylock -f -c 0b1321' &
fi
'''


def migrate_lock_binding(path):
    """Upgrade only the unmodified, old Super+L binding."""
    path = Path(path)
    tree = ET.parse(path)
    changed = False
    for binding in tree.getroot().findall('keyboard/keybind'):
        if binding.attrib != {'key': 'W-l'} or len(binding) != 1:
            continue
        action = binding[0]
        if (action.tag == 'action' and not len(action)
                and action.attrib == {'name': 'Execute', 'command': 'swaylock -f -c 0b1321'}
                and not (binding.text or '').strip() and not (action.text or '').strip()
                and not (action.tail or '').strip()):
            action.set('command', 'husk-lock')
            changed = True
    if changed:
        _replace(path, ET.tostring(tree.getroot(), encoding='utf-8', xml_declaration=True))
    return changed


def migrate_window_controls(path):
    """Supply omitted decoration controls without replacing user mouse contexts."""
    path = Path(path)
    tree = ET.parse(path)
    mice = tree.getroot().findall('mouse')
    # Labwc already provides all defaults when no mousebinds are configured.
    # Adding only controls in that case would disable its other default binds.
    if (any(mouse.find('default') is not None for mouse in mice)
            or not any(mouse.find('context/mousebind') is not None for mouse in mice)):
        return False
    existing = {name.casefold()
                for mouse in mice for context in mouse.findall('context')
                for name in (context.get('name') or context.findtext('name', '')).split()}
    changed = False
    for context, action in [('Close', 'Close'), ('Iconify', 'Iconify'), ('Maximize', 'ToggleMaximize')]:
        # Even an empty context can be a deliberate user customization.
        if context.casefold() in existing:
            continue
        target = ET.SubElement(mice[0], 'context', name=context)
        binding = ET.SubElement(target, 'mousebind', button='Left', action='Click')
        ET.SubElement(binding, 'action', name=action)
        changed = True
    if changed:
        _replace(path, ET.tostring(tree.getroot(), encoding='utf-8', xml_declaration=True))
    return changed


def prepare_session(directory=None, template_dir='/etc/ownos/labwc', store=None):
    base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    directory = Path(directory) if directory is not None else base / 'ownos/labwc'
    template_dir = Path(template_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ('rc.xml', 'environment', 'autostart'):
        target = directory / name
        if not os.path.lexists(target):
            shutil.copyfile(template_dir / name, target)
            target.chmod(0o755 if name == 'autostart' else 0o600)
    autostart = directory / 'autostart'
    if autostart.read_bytes() == LEGACY_AUTOSTART.encode('utf-8'):
        _replace(autostart, (template_dir / 'autostart').read_bytes())
        autostart.chmod(0o755)
    write_input_config(directory, template_dir / 'rc.xml', (store or ConfigStore()).load())
    migrate_lock_binding(directory / 'rc.xml')
    migrate_window_controls(directory / 'rc.xml')
    return directory


def _check_log_file(metadata):
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1):
        raise ValueError('Session log must be a regular file owned only by the current user; symlinks are refused.')


def open_session_log(directory=None, rotate=True):
    base = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))
    directory = Path(directory) if directory is not None else base / 'ownos'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    descriptor = None
    try:
        if os.fstat(directory_fd).st_uid != os.getuid():
            raise ValueError('Session log directory must belong to the current user.')
        os.fchmod(directory_fd, 0o700)
        try:
            _check_log_file(os.stat('session.log', dir_fd=directory_fd, follow_symlinks=False))
        except FileNotFoundError:
            pass
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
        descriptor = os.open('session.log', flags, 0o600, dir_fd=directory_fd)
        metadata = os.fstat(descriptor)
        _check_log_file(metadata)
        os.fchmod(descriptor, 0o600)
        if rotate and metadata.st_size > LOG_LIMIT:
            try:
                _check_log_file(os.stat('session.log.1', dir_fd=directory_fd, follow_symlinks=False))
            except FileNotFoundError:
                pass
            os.replace('session.log', 'session.log.1', src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
            os.close(descriptor)
            descriptor = None
            descriptor = os.open('session.log', flags | os.O_EXCL, 0o600, dir_fd=directory_fd)
        stream = os.fdopen(descriptor, 'a', encoding='utf-8', errors='replace', buffering=1)
        descriptor = None
        return stream
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_fd)


def _message(log, message):
    timestamp = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    print(timestamp + ' ' + message, file=log, flush=True)


def _wayland_environment():
    environment = os.environ.copy()
    environment.update(GDK_BACKEND='wayland', XDG_CURRENT_DESKTOP='Husk:OwnOS',
                       XDG_SESSION_DESKTOP='husk', XDG_SESSION_TYPE='wayland')
    return environment


def start_session(directory=None, template_dir='/etc/ownos/labwc', state_dir=None):
    with open_session_log(state_dir) as log:
        _message(log, 'Starting Husk Wayland session; compositor and child output follows.')
        # dup2 descriptors survive exec and are inherited by compositor children.
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(log.fileno(), 1)
        os.dup2(log.fileno(), 2)
        directory = prepare_session(directory, template_dir)
        environment = _wayland_environment()
        renderer = session_renderer()
        if renderer:
            environment['WLR_RENDERER'] = renderer
        command = ['/usr/bin/labwc', '-C', str(directory)]
        if not environment.get('DBUS_SESSION_BUS_ADDRESS'):
            command = ['/usr/bin/dbus-run-session', '--'] + command
        _message(log, 'Launching labwc with renderer ' + (renderer or 'automatic') + '.')
        os.execvpe(command[0], command, environment)
    return 0


def start_desktop(state_dir=None):
    with open_session_log(state_dir, rotate=False) as log:
        environment = _wayland_environment()
        _message(log, 'Starting Husk Desktop.')
        try:
            result = subprocess.call(['/usr/bin/husk-desktop'], env=environment,
                                     stdout=log, stderr=subprocess.STDOUT)
        except OSError as exc:
            _message(log, 'Husk Desktop could not start: ' + str(exc))
            result = 1
        if result:
            _message(log, 'Husk Desktop failed (' + str(result) + '); opening one recovery terminal.')
            try:
                subprocess.call(['/usr/bin/foot', '--title=Husk Desktop recovery'], env=environment,
                                stdout=log, stderr=subprocess.STDOUT)
            except OSError as exc:
                _message(log, 'Recovery terminal could not start: ' + str(exc))
        return result


def lock_session(live_directory='/run/archiso'):
    if Path(live_directory).is_dir():
        print(_('The live session cannot be locked because the live user has no password.'), file=sys.stderr)
        return 1
    return subprocess.call(['/usr/bin/swaylock', '-f', '-c', '0b1321'])
