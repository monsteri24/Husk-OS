import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from ownos.config import ConfigStore
from ownos.catalog import app_by_id, install_commands, FLATHUB_URLS
from ownos.gaming import game_command
from ownos.i18n import _


def normalize_command(name):
    aliases = {'husk-desktop':'own-shell', 'husk-shell':'own-shell',
               'husk-control':'own-control', 'husk-files':'own-files',
               'husk-game':'own-game', 'husk-install-app':'own-install-app',
               'husk-toggle-start':'own-toggle-start', 'husk-toggle-notifications':'own-toggle-notifications',
               'husk-status':'own-status', 'husk-live-smoke':'own-live-smoke',
               'husk-session-renderer':'own-session-renderer',
               'husk-session-start':'own-session-start',
               'husk-desktop-start':'own-desktop-start', 'husk-lock':'own-lock'}
    return aliases.get(name, name)


def install_app(appid):
    app = app_by_id(appid)
    if not app.flatpak_id:
        return subprocess.call(['/usr/bin/pkexec', '/usr/lib/ownos/own-admin', 'install', appid])
    remotes = subprocess.run(['/usr/bin/flatpak', 'remotes', '--user', '--columns=name,url'],
                             capture_output=True, text=True, check=True).stdout
    for line in remotes.splitlines():
        values = line.split()
        if values and values[0] == 'flathub' and (len(values) < 2 or values[1] not in FLATHUB_URLS):
            raise ValueError(_('Existing flathub remote points to an unexpected URL; review it before installation'))
    for command in install_commands(appid):
        result = subprocess.call(command)
        if result: return result
    return 0


def toggle(method):
    from ownos.ui.common import Gio
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    connection.call_sync('org.ownos.Desktop', '/org/ownos/Desktop', 'org.ownos.Desktop', method,
                         None, None, Gio.DBusCallFlags.NONE, 3000, None)


def main():
    public_name = Path(sys.argv[0]).name
    name = normalize_command(public_name)
    parser = argparse.ArgumentParser(prog=public_name)
    if name == 'own-game':
        parser.add_argument('game', nargs=argparse.REMAINDER); args = parser.parse_args()
        argv = args.game[1:] if args.game and args.game[0] == '--' else args.game
        command = game_command(argv, ConfigStore().load()); os.execvp(command[0], command)
    elif name == 'own-install-app':
        parser.add_argument('application', choices=['steam', 'heroic', 'lutris', 'discord', 'firefox'])
        args = parser.parse_args(); return install_app(args.application)
    elif name == 'own-shell':
        parser.add_argument('--preview', action='store_true'); args = parser.parse_args()
        from ownos.ui.shell import main as shell_main
        shell_main(args.preview)
    elif name == 'own-files':
        parser.add_argument('path', nargs='?'); args = parser.parse_args()
        from ownos.ui.file_manager import main as files_main
        files_main(args.path)
    elif name == 'own-control':
        parser.parse_args()
        from ownos.ui.control import main as control_main
        control_main()
    elif name in ('own-status','own-live-smoke'):
        parser.parse_args()
        from ownos.live import desktop_status, validate_live_status
        try: status = desktop_status()
        except Exception as exc:
            print(_('Husk Desktop status unavailable: {error}').format(error=exc), file=sys.stderr); return 1
        print(json.dumps(status,ensure_ascii=False,sort_keys=True))
        if name == 'own-live-smoke':
            problems = validate_live_status(status)
            if problems: print('\n'.join(problems),file=sys.stderr); return 1
            print(_('Live desktop status accepted. Input, audio, networking, games and installation require separate tests.'))
    elif name == 'own-session-renderer':
        parser.parse_args()
        from ownos.live import session_renderer
        print(session_renderer())
    elif name == 'own-session-start':
        parser.parse_args()
        from ownos.session import start_session
        return start_session()
    elif name == 'own-desktop-start':
        parser.parse_args()
        from ownos.session import start_desktop
        return start_desktop()
    elif name == 'own-lock':
        parser.parse_args()
        from ownos.session import lock_session
        return lock_session()
    elif name == 'own-toggle-start': parser.parse_args(); toggle('ToggleStart')
    elif name == 'own-toggle-notifications': parser.parse_args(); toggle('ToggleNotifications')
    else: parser.error(_('Use one of the husk-* entrypoints'))
    return 0
