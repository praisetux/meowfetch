import json, os, platform, shutil, subprocess, tempfile
from datetime import timedelta

_SYS      = platform.system()
_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

# enable ANSI escape support on Windows 10+
if _SYS == 'Windows':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        for handle_id in (-11, -12):  # stdout, stderr
            handle = kernel32.GetStdHandle(handle_id)
            mode   = ctypes.c_ulong()
            kernel32.GetConsoleMode(handle, ctypes.byref(mode))
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except OSError:
        pass

RST  = '\033[0m'
BOLD = '\033[1m'

def _load_json(name):
    with open(os.path.join(_DATA_DIR, name)) as f:
        return json.load(f)

_COLOURS = _load_json('colours.json')


def run(*cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ''

def has(cmd):
    return shutil.which(cmd) is not None

def cmd_lines(*args):
    out = run(*args)
    return out.splitlines() if out else []

def bar(pct, width=10):
    filled = min(width, max(0, round(width * pct / 100)))
    return f'[{"█" * filled}{"░" * (width - filled)}]'

def fmt_secs(secs):
    td = timedelta(seconds=int(secs))
    h, rem = divmod(td.seconds, 3600)
    parts = []
    if td.days: parts.append(f'{td.days}d')
    if h:       parts.append(f'{h}h')
    if rem // 60 or not parts:
        parts.append(f'{rem // 60}m')
    return ' '.join(parts)

def color_strip():
    normal = ''.join(f'\033[4{i}m   ' for i in range(8)) + RST
    bright = ''.join(f'\033[10{i}m   ' for i in range(8)) + RST
    return [normal, bright]


# cache path: ~/.cache on Unix, %LOCALAPPDATA% on Windows
if _SYS == 'Windows':
    _CACHE_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'meowfetch')
else:
    _CACHE_DIR = os.path.join(os.path.expanduser('~'), '.cache', 'meowfetch')
_CACHE_FILE = os.path.join(_CACHE_DIR, 'cache.json')

def load_cache():
    try:
        with open(_CACHE_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}

def save_cache(data):
    os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                mode='w', dir=_CACHE_DIR, prefix='cache.', suffix='.tmp',
                delete=False) as f:
            temporary = f.name
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, _CACHE_FILE)
    except OSError:
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def install():
    # Compatibility entry point for callers of the original installer.
    from pathlib import Path
    from .installer import install as install_package
    install_package(Path(__file__).resolve().parent)
