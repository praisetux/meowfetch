"""Shared, standard-library-only installer for local and downloaded copies."""

import argparse
import os
from pathlib import Path, PurePosixPath
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen
import zipfile

ARCHIVE_URL = 'https://github.com/praisetux/meowfetch/archive/refs/heads/main.zip'
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_EXTRACTED_BYTES = 64 * 1024 * 1024
MANAGED_MARKER = '.meowfetch-managed'


def copy_limited(incoming, output, limit, message):
    """Copy a stream of unknown length without letting it fill the disk."""
    copied = 0
    while True:
        chunk = incoming.read(65536)
        if not chunk:
            return copied
        copied += len(chunk)
        if copied > limit:
            raise ValueError(message)
        output.write(chunk)


def locations():
    if platform.system() == 'Windows':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home())
        root = base / 'Programs' / 'meowfetch'
        return root / 'lib', root / 'meowfetch.cmd'
    return (Path.home() / '.local/share/meowfetch',
            Path.home() / '.local/bin/meowfetch')


def download_package(destination):
    """Extract only regular package files, never arbitrary archive paths."""
    archive = destination / 'source.zip'
    with urlopen(ARCHIVE_URL, timeout=30) as response, archive.open('wb') as output:
        copy_limited(response, output, MAX_ARCHIVE_BYTES,
                     'The downloaded archive is larger than expected')
    package = destination / 'meowfetch'
    budget = MAX_EXTRACTED_BYTES
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename):
                raise ValueError('The downloaded archive contains an unsafe path')
            if len(path.parts) < 3 or path.parts[1] != 'meowfetch' or entry.is_dir():
                continue
            if ((entry.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('The downloaded archive contains a symbolic link')
            target = destination.joinpath(*path.parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(entry) as incoming, target.open('wb') as output:
                budget -= copy_limited(incoming, output, budget,
                                       'The downloaded archive expands too far')
    return package


def launcher_text(library):
    code = (f'import sys; sys.path.insert(0, {str(library)!r}); '
            'from meowfetch.__main__ import cli; cli()')
    if platform.system() == 'Windows':
        # Batch expands percent signs even inside quoted arguments.
        command = subprocess.list2cmdline([sys.executable, '-c', code])
        return '@echo off\n' + command.replace('%', '%%') + ' %*\n'
    return f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -c {shlex.quote(code)} "$@"\n'


def launcher_is_managed(launcher):
    """Recognize launchers created by current and earlier installers."""
    if not launcher.exists():
        return False
    try:
        contents = launcher.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        return False
    return 'from meowfetch.__main__ import cli; cli()' in contents


def path_help(launcher):
    print(f'Run now: {shlex.quote(str(launcher))}' if platform.system() != 'Windows'
          else f'Run now: "{launcher}"')
    def comparable(entry):
        return os.path.normcase(os.path.normpath(os.path.expanduser(entry)))
    paths = os.environ.get('PATH', '').split(os.pathsep)
    if comparable(str(launcher.parent)) in [comparable(p) for p in paths if p]:
        return
    if platform.system() == 'Windows':
        print(f'Add {launcher.parent} to your user Path in Environment Variables, then open a new terminal.')
        return
    shell = Path(os.environ.get('SHELL', '')).name
    if shell == 'fish':
        print('Make the command available now and in future terminals:\n  fish_add_path "$HOME/.local/bin"')
    else:
        print('For this terminal (bash/zsh/sh):\n  export PATH="$HOME/.local/bin:$PATH"')
        rc = '~/.zshrc' if shell == 'zsh' else '~/.bashrc' if shell == 'bash' else 'your shell startup file'
        print(f'For future terminals, add that export line once to {rc}.')


def install(source=None):
    """Validate a staged copy before replacing the managed installation."""
    root, launcher = locations()
    if root.is_symlink() or launcher.is_symlink():
        raise ValueError('Installation paths must not be symbolic links')
    if launcher.exists() and not launcher_is_managed(launcher):
        raise ValueError(f'Refusing to replace an unrecognized launcher: {launcher}')
    if root.exists() and not (root / 'meowfetch/__main__.py').is_file():
        raise ValueError(f'Refusing to replace an unrecognized directory: {root}')
    root.parent.mkdir(parents=True, exist_ok=True)
    launcher.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.meowfetch-stage-', dir=root.parent) as temporary:
        workspace = Path(temporary)
        if source is None:
            incoming = workspace / 'download'
            incoming.mkdir()
            source = download_package(incoming)
        source = Path(source)
        if not all((source / name).is_file()
                   for name in ('__init__.py', '__main__.py', 'installer.py')):
            raise ValueError('The new copy is missing its package entry points or installer')
        stage = workspace / 'application'
        stage.mkdir()
        legacy = (root / '.git').exists()
        # Keep unrelated files in a manual installation. Git checkouts are
        # preserved in full as a separate backup instead.
        if root.exists() and not legacy:
            for item in root.iterdir():
                if item.name == 'meowfetch':
                    continue
                target = stage / item.name
                if item.is_dir() and not item.is_symlink():
                    shutil.copytree(item, target, symlinks=True)
                else:
                    shutil.copy2(item, target, follow_symlinks=False)
        shutil.copytree(source, stage / 'meowfetch',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (stage / MANAGED_MARKER).write_text('meowfetch installer\n', encoding='utf-8')
        check = subprocess.run(
            [sys.executable, '-I', '-c',
             'import sys; sys.path.insert(0, sys.argv[1]); '
             'from meowfetch.__main__ import cli; sys.argv = ["meowfetch", "--version"]; cli()',
             str(stage)], capture_output=True, text=True, timeout=30,
        )
        if check.returncode:
            raise ValueError('The new copy failed its startup check: ' + check.stderr.strip())
        # Stage the launcher beside its destination; renaming it in from the
        # workspace fails when the two directories are on separate filesystems.
        handle, staged = tempfile.mkstemp(prefix='.meowfetch-launcher-', dir=launcher.parent)
        os.close(handle)
        launcher_stage = Path(staged)
        previous = workspace / 'previous'
        backup = None
        if legacy:
            backup = Path(tempfile.mkdtemp(prefix='meowfetch-backup-', dir=root.parent))
            previous = backup / 'checkout'
        replaced = False
        # The old copy only exists inside the workspace between the two
        # renames, so an interrupt there has to roll back like any other error.
        try:
            launcher_stage.write_text(launcher_text(root), encoding='utf-8')
            launcher_stage.chmod(0o755)
            if root.exists():
                root.rename(previous)
            stage.rename(root)
            replaced = True
            launcher_stage.replace(launcher)
        except BaseException:
            launcher_stage.unlink(missing_ok=True)
            if replaced:
                shutil.rmtree(root)
            if previous.exists():
                previous.rename(root)
            if backup is not None:
                backup.rmdir()
            raise
        print(f'Installed: {launcher}')
        if backup is not None:
            print(f'Previous Git checkout preserved: {previous}')
    path_help(launcher)


def uninstall():
    root, launcher = locations()
    if root.is_symlink() or launcher.is_symlink():
        raise ValueError('Installation paths must not be symbolic links')
    if not (root / 'meowfetch/__main__.py').is_file():
        raise ValueError(f'No managed installation found at {root}')
    if not (root / MANAGED_MARKER).is_file() and not launcher_is_managed(launcher):
        raise ValueError(f'Refusing to remove an unrecognized installation: {root}')
    if (root / '.git').exists():
        raise ValueError('This installation is a Git checkout; update first to preserve it in a backup')
    # Leave extra files, caches and migration backups alone.
    # Keep the command usable if package removal fails partway through.
    shutil.rmtree(root / 'meowfetch')
    launcher.unlink(missing_ok=True)
    (root / MANAGED_MARKER).unlink(missing_ok=True)
    if not any(root.iterdir()):
        root.rmdir()
    print('Uninstalled meowfetch. Cached data and any migration backups were kept.')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install or update meowfetch without Git.')
    parser.add_argument('action', nargs='?', choices=('install', 'update', 'uninstall'), default='install')
    args = parser.parse_args(argv)
    try:
        if args.action == 'uninstall':
            uninstall()
        else:
            install()
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
