"""Unprivileged, single-purpose bridge to passwd's controlling terminal.

The GUI starts this file with Python isolated mode. The chosen password enters
only through an anonymous stdin pipe; argv, environment and stdout contain no
secret. PAM and passwd retain their own password policy. This helper cannot
change a different account or authorize a package transaction.
"""
import errno
import json
import os
from pathlib import Path
import pty
import pwd
import select
import signal
import subprocess
import sys
import termios
import time


def _eligible():
    if not Path('/run/archiso').is_dir() or os.getuid() == 0:
        return False
    user = pwd.getpwuid(os.getuid()).pw_name
    if user != 'live':
        return False
    result = subprocess.run(['/usr/bin/passwd', '-S', user], capture_output=True,
                            text=True, check=True, timeout=8)
    fields = result.stdout.split()
    return len(fields) == 7 and fields[0] == user and fields[1] == 'NP'


def valid_password(password):
    return (isinstance(password, str) and 8 <= len(password) <= 128 and
            not any(ord(c) < 32 or ord(c) == 127 for c in password))


def _exchange(password, timeout=35):
    """Run in this single-threaded child, giving passwd a controlling PTY.

    Prompt text is fixed by LC_ALL=C. Refuse unexpected prompts and never
    write a password while terminal echo is enabled. No raw transcript leaves
    this process, including a PAM module that accidentally prints its input.
    """
    child, master = pty.fork()
    if child == 0:
        os.execve('/usr/bin/passwd', ['/usr/bin/passwd'],
                  {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'TERM': 'dumb'})
    finished = False
    try:
        deadline, transcript, step = time.monotonic() + timeout, b'', 0
        terminal_open = True
        prompts = (b'new password:', b'retype new password:')
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master] if terminal_open else [], [], [], 0.1)
            if ready:
                try:
                    chunk = os.read(master, 4096)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        chunk = b''
                    else:
                        raise
                if not chunk:
                    terminal_open = False
                transcript = (transcript + chunk)[-16384:]
                if chunk and step < 2 and prompts[step] in transcript.lower():
                    if termios.tcgetattr(master)[3] & termios.ECHO:
                        return 1
                    os.write(master, password.encode('utf-8') + b'\n')
                    transcript = b''
                    step += 1
            done, status = os.waitpid(child, os.WNOHANG)
            if done:
                finished = True
                return 0 if os.waitstatus_to_exitcode(status) == 0 and step == 2 else 1
        done, status = os.waitpid(child, os.WNOHANG)
        if done:
            finished = True
            return 0 if os.waitstatus_to_exitcode(status) == 0 and step == 2 else 1
        return 1
    finally:
        if not finished:
            try:
                os.killpg(child, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(child, 0)
        os.close(master)


def main():
    # This is intentionally not a root helper and accepts no account/program
    # arguments. Eligibility is checked again after the graphical preflight.
    if len(sys.argv) != 1 or not _eligible():
        return 1
    try:
        raw = sys.stdin.buffer.readline(1025)
        password = json.loads(raw)
        if not valid_password(password):
            return 1
        return _exchange(password)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
