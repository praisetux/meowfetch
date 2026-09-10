# meowfetch

Hi, this is a small project I made while experimenting with agentic coding. It
is not intended to be taken too seriously.

Meowfetch is a fetch utility with a pawesome twist. It displays one of several
cats alongside information about your system.

![preview](meowfetch.png)

## Requirements

- Python 3.9 or newer
- curl for the Linux/macOS online installer

Linux, macOS, and Windows are supported. Git, pip, administrator access, and
third-party Python packages are not required.

## Installation

### Linux and macOS

```bash
curl -fsSL https://raw.githubusercontent.com/praisetux/meowfetch/main/install.sh | sh
```

The installer downloads the latest source archive, checks that Meowfetch starts,
and installs it for your user. It does not modify your shell configuration.

Run it immediately with:

```bash
~/.local/bin/meowfetch
```

If `meowfetch` isn't found, make it available in the current bash/zsh terminal:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

For future terminals, add that line **once** to `~/.bashrc` for bash or
`~/.zshrc` for zsh. For fish, run:

```fish
fish_add_path "$HOME/.local/bin"
```

### Windows

1. Download the [repository ZIP](https://github.com/praisetux/meowfetch/archive/refs/heads/main.zip).
2. Extract it and open PowerShell in the extracted folder.
3. Install Meowfetch for your Windows user:

```powershell
py .\meowfetch.py --install
```

If the Python launcher is unavailable, use `python` instead of `py`. The
installer prints the installed command and tells you which folder to add to your
user `Path`. After adding it, open a new terminal and run `meowfetch`.

You can also run it directly without changing `Path`:

```powershell
& "$env:LOCALAPPDATA\Programs\meowfetch\meowfetch.cmd"
```

### Install from a local copy

From an extracted source archive or Git checkout, run:

```bash
python3 meowfetch.py --install
```

On Windows, use `py meowfetch.py --install`. This installs the files from the
local copy using the same checks as the online installer. The source folder can
then be removed.

## Usage

Run Meowfetch with:

```bash
meowfetch
```

### Colours

Use `--color` or `-c` to set the accent colour:

```bash
meowfetch --color pink
meowfetch -c bright_cyan
```

Available colours: `red`, `green`, `yellow`, `orange`, `blue`, `magenta`,
`cyan`, `white`, `pink`, `bright_red`, `bright_green`, `bright_blue`, and
`bright_cyan`.

The default is `cyan`.

## Updating

```bash
meowfetch --update
```

This works on Linux, macOS, and Windows. On Linux and macOS, re-running the
online installation command also updates Meowfetch. Updates download the latest
`main` archive, stage it, and check it before replacing the installed copy.

When migrating from the old Git-based installer, the entire previous checkout
(including local edits) is kept in a `meowfetch-backup-*` directory beside the
installation. The installer prints its location. Updates replace application
code, so make your own code changes in a separate development checkout.

## Uninstalling

```bash
meowfetch --uninstall
```

This works on all supported platforms and removes the installed package and
launcher. Cached information, migration backups, and unrelated files are kept.
If the command is not on your PATH, use one of these commands:

```bash
~/.local/bin/meowfetch --uninstall
```

```powershell
& "$env:LOCALAPPDATA\Programs\meowfetch\meowfetch.cmd" --uninstall
```

## Installed locations

| Platform | Application files | Command |
| --- | --- | --- |
| Linux/macOS | `~/.local/share/meowfetch` | `~/.local/bin/meowfetch` |
| Windows | `%LOCALAPPDATA%\Programs\meowfetch\lib` | `%LOCALAPPDATA%\Programs\meowfetch\meowfetch.cmd` |

## AI notice

This project contains AI generated code.
