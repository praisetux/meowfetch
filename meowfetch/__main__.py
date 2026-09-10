#!/usr/bin/env python3
"""Meowfetch — a fetch script with a pawesome twist"""

import argparse, os, random, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from . import __version__
from .utils import BOLD, RST, _COLOURS, color_strip, install, load_cache, save_cache, _load_json
from .collectors import (
    get_user, get_hostname,
    get_os, get_kernel, get_uptime,
    get_packages,
    get_shell, get_terminal,
    get_cpu, get_gpu,
    get_ram, get_disk,
)

CATS    = _load_json('cats.json')
FESTIVE = _load_json('festive_cats.json')

_DISK_LABEL = 'Disk (C:\\)' if os.name == 'nt' else 'Disk (/)'


def festive_cat(today=None):
    """The festive entry for today, or None on an ordinary day.

    Reads the machine's local date, so the cat lands on the holiday in the
    user's own timezone rather than on some fixed one.
    """
    today = today or date.today()
    for entry in FESTIVE.values():
        if [today.month, today.day] in entry['dates']:
            return entry
    return None


_CACHE_TTL = {
    'OS':        86400,  # 24h — static between reinstalls
    'Kernel':    86400,  # 24h — static between reboots
    'Shell':     86400,  # 24h — rarely changes
    'CPU':       86400,  # 24h — static hardware
    'GPU':       86400,  # 24h — static hardware
    'Packages':  300,    # 5min — slow to collect, changes infrequently
    _DISK_LABEL: 60,     # 1min — changes occasionally
    # Uptime, RAM, Terminal intentionally absent — always collected fresh
}


def main(color=None):
    user    = get_user()
    host    = get_hostname()
    festive = festive_cat()

    cat = festive['art'] if festive else random.choice(CATS)
    # An explicit --color always wins; otherwise a holiday themes the whole
    # panel, and any other day falls back to the usual cyan.
    if color is None:
        color = festive['colour'] if festive else 'cyan'
    use_colour = sys.stdout.isatty() and 'NO_COLOR' not in os.environ
    accent = _COLOURS[color] if use_colour else ''
    bold = BOLD if use_colour else ''
    reset = RST if use_colour else ''

    collectors = {
        'OS':        get_os,
        'Kernel':    get_kernel,
        'Uptime':    get_uptime,
        'Packages':  get_packages,
        'Shell':     get_shell,
        'Terminal':  get_terminal,
        'CPU':       get_cpu,
        'GPU':       get_gpu,
        'RAM':       get_ram,
        _DISK_LABEL: get_disk,
    }

    now   = time.time()
    cache = load_cache()
    # A code update can change what collectors emit — don't serve values
    # cached by an older version.
    if cache.get('_version') != __version__:
        cache = {'_version': __version__}

    results  = {}
    to_fetch = {}
    for label, fn in collectors.items():
        ttl   = _CACHE_TTL.get(label, 0)
        entry = cache.get(label)
        timestamp = entry.get('ts') if isinstance(entry, dict) else None
        age = now - timestamp if isinstance(timestamp, (int, float)) \
            and not isinstance(timestamp, bool) else -1
        if ttl > 0 and isinstance(entry, dict) and 'val' in entry \
                and 0 <= age < ttl:
            results[label] = entry['val']
        else:
            to_fetch[label] = fn

    if to_fetch:
        with ThreadPoolExecutor() as pool:
            futures = {label: pool.submit(fn) for label, fn in to_fetch.items()}
            fresh = {}
            for label, future in futures.items():
                try:
                    fresh[label] = future.result()
                except Exception:
                    fresh[label] = 'Unknown'
        results.update(fresh)
        dirty = False
        for label, val in fresh.items():
            # Don't cache failures/sentinels — a transient '' or 'Unknown'
            # would otherwise be pinned for the whole TTL (up to 24h).
            if _CACHE_TTL.get(label, 0) > 0 and val and val != 'Unknown':
                cache[label] = {'val': val, 'ts': now}
                dirty = True
        if dirty:
            save_cache(cache)

    rows = [
        f'{bold}{accent}{user}{reset}@{bold}{accent}{host}{reset}',
        f'{accent}{"─" * (len(user) + len(host) + 1)}{reset}',
    ]
    for label in collectors:
        val = results.get(label)
        if val:
            rows.append(f'{bold}{accent}{label}{reset}: {val}')
    rows += [''] + (color_strip() if use_colour else [])

    cat_w    = max(len(line) for line in cat)
    cat_rows = [f'{bold}{accent}{line.ljust(cat_w)}{reset}' for line in cat]

    n = max(len(cat_rows), len(rows))
    cat_rows += [' ' * cat_w] * (n - len(cat_rows))
    rows     += [''] * (n - len(rows))

    print()
    for cat_line, info_line in zip(cat_rows, rows):
        print(f'  {cat_line}    {info_line}')
    print()


def cli():
    parser = argparse.ArgumentParser(prog='meowfetch')
    parser.add_argument(
        '--color', '-c',
        choices=_COLOURS,
        default=None,
        metavar='NAME',
        help=f'colour scheme, default cyan ({", ".join(_COLOURS)})',
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--install', action='store_true', help='install this local copy')
    actions.add_argument('--update', action='store_true', help='download and install the latest version')
    actions.add_argument('--uninstall', action='store_true', help='remove the user installation')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    args = parser.parse_args()

    if args.update or args.uninstall:
        from .installer import main as manage
        raise SystemExit(manage(['update' if args.update else 'uninstall']))
    elif args.install:
        try:
            install()
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            parser.exit(1, f'error: {error}\n')
    else:
        main(args.color)


if __name__ == '__main__':
    cli()
