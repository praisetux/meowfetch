# meowfetch

Hi, this is just a small project I've made whilst experiementing with agentic coding. This project is not something to be taken seriously.

Meowfetch is a fetch utility with a pawesome twist! When ran it will display one of several cats, along side system information.

![preview](meowfetch.png)

---
requirements

- Python 3.9 or newer
- curl (for the online installer)

No Git, pip, or third-party Python packages are required.

---
installation

## Linux / macOS

```bash
curl -fsSL https://raw.githubusercontent.com/praisetux/meowfetch/main/install.sh | sh
```

The installer downloads the latest source archive from GitHub's `main` branch,
checks that the application starts, and installs it for your user. No sudo is needed.

Run it immediately with:

```bash
~/.local/bin/meowfetch
```

If `meowfetch` isn't found, make it available in the current bash/zsh terminal:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

For future terminals, add that line **once** to `~/.bashrc` (bash) or `~/.zshrc`
(zsh). For fish, run `fish_add_path "$HOME/.local/bin"`. The installer also prints
instructions for your shell; it does not edit your shell configuration.

---
manual install

Download and extract the repository ZIP from GitHub, open a terminal in the
extracted folder, and run:

```bash
python3 meowfetch.py --install
```

This uses the same installer as the online command. After installation, the
extracted folder can be removed. On Windows, use `py meowfetch.py --install`;
the installer prints the launcher location and user PATH instructions.

---
colours

use `--color` / `-c` to set the accent colour:

```bash
meowfetch --color pink
meowfetch -c bright_cyan
```

available: `red`, `green`, `yellow`, `orange`, `blue`, `magenta`, `cyan`, `white`, `pink`, `bright_red`, `bright_green`, `bright_blue`, `bright_cyan`

default is `cyan`.

---
updating

```bash
meowfetch --update
```

Or re-run the online install command. Both download the latest `main` archive;
local installation with `--install` uses the files in that local copy instead.
The new package is staged and checked before replacing the installed copy.

When migrating from the old Git-based installer, the entire previous checkout
(including local edits) is kept in a `meowfetch-backup-*` directory beside the
installation. The installer prints its location. Updates replace application
code, so make your own code changes in a separate development checkout.

---
uninstalling

```bash
meowfetch --uninstall
```

This removes the installed package and launcher. Cached information, migration
backups, and unrelated files are kept. If the command is not on PATH, use
`~/.local/bin/meowfetch --uninstall` on Linux/macOS.

The Linux/macOS installation uses `~/.local/share/meowfetch` for the application
and `~/.local/bin/meowfetch` for the launcher.

---
# AI notice
This project contains AI generated code.
