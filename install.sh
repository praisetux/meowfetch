#!/bin/sh
set -eu

case "${1:-install}" in
  install|update|uninstall) action="${1:-install}" ;;
  -h|--help) echo 'Usage: sh install.sh [install|update|uninstall]'; exit 0 ;;
  *) echo 'Usage: sh install.sh [install|update|uninstall]' >&2; exit 2 ;;
esac

PYTHON=""
for candidate in python3 python3.14 python3.13 python3.12 python3.11 python3.10 python3.9; do
  if command -v "$candidate" >/dev/null 2>&1 \
      && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 9))' 2>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done
if [ -z "$PYTHON" ]; then
  echo 'error: Python 3.9 or newer is required but was not found' >&2
  exit 1
fi
# Removing an installation needs neither the network nor a fresh copy of the
# remote installer; the installed one already knows what it put where.
INSTALLED="${HOME:-}/.local/share/meowfetch/meowfetch/installer.py"
if [ "$action" = uninstall ] && [ -f "$INSTALLED" ]; then
  exec "$PYTHON" "$INSTALLED" uninstall
fi

if ! command -v curl >/dev/null 2>&1; then
  echo 'error: curl is required to download the installer' >&2
  exit 1
fi

STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT
trap 'exit 1' HUP INT TERM
curl -fsSL --connect-timeout 15 --max-time 60 \
  https://raw.githubusercontent.com/praisetux/meowfetch/main/meowfetch/installer.py \
  -o "$STAGING/installer.py"
"$PYTHON" "$STAGING/installer.py" "$action"
