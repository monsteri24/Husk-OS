"""Curated installation checks shared by the GUI and root-owned helper.

Connectivity checks are read-only. They use pacman's resolved configuration,
never replace mirrors, alter DNS, disable signatures or refresh a database.
"""
from dataclasses import dataclass
import os
import pwd
import re
import socket
import ssl
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from ownos.i18n import _


def app_installed(app):
    """Verify the package record, never a command found in an untrusted PATH."""
    command = (['/usr/bin/flatpak', 'info', '--user', app.flatpak_id]
               if app.flatpak_id else ['/usr/bin/pacman', '-Q', '--', app.package])
    try:
        return subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=8, check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _live_password_status(user):
    # Shadow's passwd(1) documents seven fields, with NP/P/L in field two.
    result = subprocess.run(['/usr/bin/passwd', '-S', user], capture_output=True,
                            text=True, check=True, timeout=8)
    fields = result.stdout.split()
    return fields[1] if len(fields) == 7 and fields[0] == user else ''


def live_authentication_state():
    """Return ready/setup for this Live account; fail closed on unknown states."""
    if not Path('/run/archiso').is_dir():
        return 'ready'
    user = pwd.getpwuid(os.getuid()).pw_name
    if user != 'live':
        return 'ready'
    state = _live_password_status(user)
    if state == 'P':
        return 'ready'
    if state == 'NP':
        return 'setup'
    raise RuntimeError(_('The Live account does not have a usable administrator password. Review the account configuration before installing system applications.'))


@dataclass(frozen=True)
class InstallProblem(Exception):
    kind: str
    message: str
    detail: str = ''

    def __str__(self):
        return self.message


def trusted_flathub():
    """Check disabled remotes too: remote-add must not reuse an unsafe one."""
    from ownos.catalog import FLATHUB_URLS
    remotes = subprocess.run(
        ['/usr/bin/flatpak', 'remotes', '--user', '--show-disabled', '--columns=name,url,options'],
        capture_output=True, text=True, check=True, timeout=8).stdout
    for line in remotes.splitlines():
        values = line.split(maxsplit=2)
        if not values or values[0] != 'flathub':
            continue
        if len(values) < 2 or values[1] not in FLATHUB_URLS:
            raise InstallProblem('repository', _('The existing Flathub remote has an unexpected address.'),
                                 _('Review the user Flathub remote before retrying.'))
        options = values[2].replace(',', ' ').split() if len(values) > 2 else ()
        if 'no-gpg-verify' in options:
            raise InstallProblem('signature', _('Flathub signature verification is disabled.'),
                                 _('Restore GPG verification on the user Flathub remote before retrying.'))
        if 'disabled' in options:
            raise InstallProblem('repository', _('The user Flathub remote is disabled.'),
                                 _('Enable the trusted Flathub remote before retrying.'))


def repository_targets(app):
    """One candidate list per repository that the full upgrade will refresh."""
    if app.flatpak_id:
        return [('Flathub setup', ['https://flathub.org/repo/flathub.flatpakrepo']),
                ('Flathub', ['https://dl.flathub.org/repo/summary'])]
    def query(*args):
        result = subprocess.run(['/usr/bin/pacman-conf', *args], capture_output=True,
                                text=True, check=True, timeout=8)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    repositories = query('--repo-list')
    if not repositories:
        raise InstallProblem('repository', _('No package repositories are configured.'))
    targets = []
    for repo in repositories:
        # Names are configuration output, not package-manager options.
        if not re.fullmatch(r'[A-Za-z0-9_.+-]+', repo):
            raise InstallProblem('repository', _('A package repository name is invalid.'))
        servers = query('--repo', repo, 'Server')
        candidates = [server.rstrip('/') + '/' + repo + '.db' for server in servers]
        if not candidates:
            raise InstallProblem('repository', _('No mirrors are configured for {repository}.').format(repository=repo))
        targets.append((repo, candidates))
    return targets


def _probe_repository(url):
    parsed = urlsplit(url)
    if parsed.scheme == 'file':
        if parsed.netloc not in ('', 'localhost') or not Path(parsed.path).is_file():
            raise InstallProblem('repository', _('A local package repository is unavailable.'))
        return
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username:
        raise InstallProblem('repository', _('A package mirror uses an unsupported address.'))
    # urllib performs DNS, the connection and TLS certificate validation. HEAD
    # avoids downloading package data. Some otherwise valid mirrors require GET.
    request = Request(url, method='HEAD', headers={'User-Agent': 'HuskOS-Installer/3'})
    try:
        with urlopen(request, timeout=6):
            return
    except HTTPError as exc:
        if exc.code not in (405, 501):
            raise
    with urlopen(Request(url, headers={'Range': 'bytes=0-0', 'User-Agent': 'HuskOS-Installer/3'}), timeout=6) as response:
        response.read(1)


def _connection_problem(exc):
    reason = exc.reason if isinstance(exc, URLError) else exc
    if isinstance(reason, socket.gaierror):
        return InstallProblem('dns', _('Package server names could not be resolved.'),
                              _('Open Network settings, connect to the internet and check DNS, then retry.'))
    if isinstance(reason, ssl.SSLError):
        return InstallProblem('tls', _('The package server certificate could not be verified.'),
                              _('Check the date and time and the network connection. Certificate checks remain enabled.'))
    if isinstance(exc, HTTPError):
        return InstallProblem('mirror', _('A package mirror is unavailable.'),
                              _('The repository returned HTTP {status}. Check the configured mirrors, then retry.').format(status=exc.code))
    return InstallProblem('network', _('The package servers could not be reached.'),
                          _('Connect to the internet in Network settings, then retry. A captive portal, proxy or firewall may also block the connection.'))


def preflight_install(app, report=lambda message: None, cancelled=lambda: False):
    """Check every configured repo, allowing up to three distinct mirror hosts.

    Success is evidence of connectivity now, not a guarantee about a later
    download. The privileged helper repeats this check immediately before Syu.
    """
    if cancelled():
        raise InstallProblem('cancelled', _('Installation cancelled.'))
    if app.flatpak_id:
        trusted_flathub()
    elif Path('/var/lib/pacman/db.lck').exists():
        raise InstallProblem('locked', _('Another package transaction is active.'),
                             _('Wait for it to finish, then retry. Husk OS will not remove the package lock.'))
    try:
        targets = repository_targets(app)
    except InstallProblem:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise InstallProblem('repository', _('The package repository configuration could not be read.'), str(exc)) from exc
    for name, candidates in targets:
        report(_('Checking {repository} connectivity and DNS…').format(repository=name))
        checked, failures = set(), []
        for url in candidates:
            if cancelled():
                raise InstallProblem('cancelled', _('Installation cancelled.'))
            # Use only the hostname in diagnostics, never URL credentials.
            host = urlsplit(url).hostname or 'local repository'
            if host in checked:
                continue
            checked.add(host)
            try:
                _probe_repository(url)
                break
            except InstallProblem:
                raise
            except (OSError, URLError, ValueError) as exc:
                failures.append(_connection_problem(exc))
            if len(checked) >= 3:
                break
        else:
            if not failures:
                raise InstallProblem('repository', _('No usable package mirrors are configured.'))
        # A break due to the retry bound must fail just like exhaustion.
        if failures and len(failures) == len(checked):
            problem = failures[0] if all(p.kind == failures[0].kind for p in failures) else failures[-1]
            raise InstallProblem(problem.kind, problem.message,
                                 name + ' (' + ', '.join(sorted(checked)) + '): ' + problem.detail)


def graphical_commands(app):
    """Only fixed curated targets; consent is collected by the graphical UI."""
    from ownos.catalog import FLATHUB_REPOFILE
    if app.flatpak_id:
        return [(['/usr/bin/flatpak', 'remote-add', '--user', '--if-not-exists', 'flathub', FLATHUB_REPOFILE], 'repository'),
                (['/usr/bin/flatpak', 'install', '--user', '--noninteractive', '--assumeyes',
                  'flathub', app.flatpak_id], 'install')]
    return [(['/usr/bin/pkexec', '--disable-internal-agent', '/usr/lib/ownos/own-admin',
              'install-confirmed', app.id], 'authorization')]


def transaction_problem(status, output, native=True):
    """Keep authorization, connectivity and package/signature failures distinct."""
    lower = output.lower()
    if native and status in (126, 127):
        return InstallProblem('authorization',
                              _('Authorization was cancelled.') if status == 126 else _('Administrator authorization failed.'),
                              _('Retry to open the authorization dialog again. Check that a graphical polkit agent is running if no dialog appeared.'))
    if 'ownos-error:dns' in lower or 'could not resolve' in lower or 'name or service not known' in lower:
        return _connection_problem(socket.gaierror())
    if any(text in lower for text in ('ownos-error:network', 'failed to connect', 'network is unreachable', 'connection timed out', 'could not connect')):
        return _connection_problem(OSError())
    if any(text in lower for text in ('invalid or corrupted package', 'signature', 'unknown trust')):
        return InstallProblem('signature', _('Package signature verification failed.'),
                              _('Review the transaction details and the system keyring. Signature checks remain enabled.'))
    if 'ownos-error:tls' in lower:
        return _connection_problem(ssl.SSLError())
    if 'ownos-error:mirror' in lower or 'ownos-error:repository' in lower:
        return InstallProblem('repository', _('The configured package repositories are unavailable.'),
                              _('Review the repository diagnostic in Transaction details, then retry.'))
    if 'db.lck' in lower or 'another pacman transaction' in lower or 'unable to lock database' in lower:
        return InstallProblem('locked', _('Another package transaction is active.'),
                              _('Wait for it to finish, then retry. The package lock will not be removed.'))
    return InstallProblem('transaction', _('Installation failed (exit status {status}).').format(status=status),
                          _('Review the transaction details, correct the reported problem, then retry.'))


def transaction_stage(line):
    """Translate actual pacman/Flatpak output into stages, never invented %s."""
    text = line.lower()
    for needles, label in (
        (('ownos-stage:preflight',), _('Checking package repositories…')),
        (('synchronizing package databases',), _('Refreshing package databases…')),
        (('starting full system upgrade', 'resolving dependencies'), _('Resolving packages and system updates…')),
        (('retrieving packages', 'downloading'), _('Downloading packages…')),
        (('checking keys', 'checking package integrity'), _('Verifying package signatures and integrity…')),
        (('processing package changes', 'installing', 'upgrading'), _('Installing packages and system updates…')),
        (('running post-transaction hooks',), _('Finishing package setup…')),
    ):
        if any(needle in text for needle in needles):
            return label
    return None


def prepare_live_authentication():
    """Set only the invoking Live user's password, using passwd's own TTY UI.

    Installed systems, other users and per-user Flatpak transactions do not
    enter this path. No password or generated input passes through Python.
    Authentication remains pkexec/polkit's responsibility after this returns.
    """
    if not Path('/run/archiso').is_dir():
        return 0
    try:
        user = pwd.getpwuid(os.getuid()).pw_name
    except (OSError, KeyError) as exc:
        print(_('Could not check the Live administrator password status: {error}').format(
            error=exc), file=sys.stderr, flush=True)
        return 1
    if user != 'live':
        return 0
    for check in range(2):
        try:
            state = _live_password_status(user)
        except (OSError, subprocess.SubprocessError) as exc:
            diagnostic = getattr(exc, 'stderr', None) or str(exc)
            print(_('Could not check the Live administrator password status: {error}').format(
                error=diagnostic), file=sys.stderr, flush=True)
            return getattr(exc, 'returncode', 1) or 1
        if state == 'P':
            return 0
        if state != 'NP' or check:
            break
        print(_('A temporary Live administrator password is required to install system applications. Set a password now, then enter it again in the authorization dialog. It lasts only for this Live session.'), flush=True)
        try:
            result = subprocess.call(['/usr/bin/passwd'])
        except OSError as exc:
            print(str(exc), file=sys.stderr, flush=True)
            return 1
        if result:
            return result
    print(_('The Live account does not have a usable administrator password. Installation was stopped.'),
          file=sys.stderr, flush=True)
    return 1
