"""Read local Steam manifests. Never trust a manifest as a command."""
from dataclasses import dataclass
from pathlib import Path
import re


def parse_vdf(text):
    if len(text) > 2_000_000:
        raise ValueError('VDF file is too large')
    tokens = []
    pos = 0
    while pos < len(text):
        c = text[pos]
        if c.isspace(): pos += 1; continue
        if text.startswith('//', pos):
            end = text.find('\n', pos); pos = len(text) if end < 0 else end + 1; continue
        if c in '{}': tokens.append(c); pos += 1; continue
        if c != '"': raise ValueError('Expected a quoted VDF token')
        pos += 1; value = []
        while pos < len(text) and text[pos] != '"':
            if text[pos] == '\\' and pos + 1 < len(text) and text[pos + 1] in ('\\', '"'):
                pos += 1
            value.append(text[pos]); pos += 1
        if pos == len(text): raise ValueError('Unterminated VDF string')
        tokens.append(''.join(value)); pos += 1
    index = 0

    def block(nested=False, depth=0):
        nonlocal index
        if depth > 32: raise ValueError('VDF is nested too deeply')
        result = {}
        while index < len(tokens):
            key = tokens[index]; index += 1
            if key == '}':
                if not nested: raise ValueError('Unexpected closing brace')
                return result
            if key == '{' or index == len(tokens): raise ValueError('Missing VDF value')
            value = tokens[index]; index += 1
            if value == '{': value = block(True, depth + 1)
            elif value == '}': raise ValueError('Unexpected closing brace')
            result[key] = value
        if nested: raise ValueError('Unclosed VDF block')
        return result
    return block()


def read_vdf(path):
    if path.stat().st_size > 2_000_000: raise ValueError('VDF file is too large')
    return parse_vdf(path.read_text(encoding='utf-8'))


@dataclass(frozen=True)
class SteamGame:
    appid: str
    name: str
    library: Path


def discover_steam_games(roots=None):
    if roots is None:
        roots = [Path.home() / '.local/share/Steam', Path.home() / '.steam/steam']
    libraries = {Path(p).expanduser().resolve() for p in roots}
    for path in list(libraries):
        try:
            folders = read_vdf(path / 'steamapps/libraryfolders.vdf').get('libraryfolders', {})
            if not isinstance(folders, dict): continue
            for entry in folders.values():
                location = entry.get('path') if isinstance(entry, dict) else entry
                if isinstance(location, str) and Path(location).is_absolute():
                    libraries.add(Path(location).resolve())
        except (OSError, ValueError, UnicodeError):
            continue
    games = {}
    for library in sorted(libraries):
        for manifest in (library / 'steamapps').glob('appmanifest_*.acf'):
            try:
                data = read_vdf(manifest)['AppState']
                appid = data['appid']; name = data['name']
                if not isinstance(appid, str) or not re.fullmatch(r'[0-9]{1,10}', appid): continue
                if manifest.name != 'appmanifest_' + appid + '.acf': continue
                if not isinstance(name, str): continue
                games[appid] = SteamGame(appid, name[:256], library)
            except (OSError, ValueError, KeyError, TypeError, UnicodeError):
                continue
    return sorted(games.values(), key=lambda g: g.name.casefold())
