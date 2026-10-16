"""Curated launcher/install choices. No unreviewed AUR recipes."""
from dataclasses import dataclass
from ownos.i18n import _


@dataclass(frozen=True)
class App:
    id: str
    name: str
    icon: str
    command: tuple
    package: str = ''
    flatpak_id: str = ''


APPS = (
    App('steam', 'Steam', 'steam', ('/usr/bin/steam',), 'steam'),
    App('heroic', 'Heroic · Epic / GOG', 'com.heroicgameslauncher.hgl',
        ('/usr/bin/flatpak', 'run', 'com.heroicgameslauncher.hgl'), flatpak_id='com.heroicgameslauncher.hgl'),
    App('lutris', 'Lutris', 'lutris', ('/usr/bin/lutris',), 'lutris'),
    App('discord', 'Discord', 'discord', ('/usr/bin/discord',), 'discord'),
    App('firefox', 'Firefox', 'firefox', ('/usr/bin/firefox',), 'firefox'),
)
FLATHUB_REPOFILE = 'https://flathub.org/repo/flathub.flatpakrepo'
FLATHUB_URLS = ('https://dl.flathub.org/repo/', 'https://dl.flathub.org/repo')


def app_by_id(appid):
    for app in APPS:
        if app.id == appid:
            return app
    raise ValueError(_('Unknown application'))


def install_commands(appid):
    app = app_by_id(appid)
    if app.flatpak_id:
        return [
            ['/usr/bin/flatpak', 'remote-add', '--user', '--if-not-exists', 'flathub', FLATHUB_REPOFILE],
            ['/usr/bin/flatpak', 'install', '--user', 'flathub', app.flatpak_id],
        ]
    return [['/usr/bin/pkexec', '/usr/lib/ownos/own-admin', 'install', app.id]]
