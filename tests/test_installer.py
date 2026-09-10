"""Installer integration tests; all installations stay in temporary directories."""

import contextlib
import errno
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from meowfetch import installer

PACKAGE = Path(__file__).resolve().parent.parent / 'meowfetch'
SCRIPT = PACKAGE.parent / 'install.sh'


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name) / "space ' quote $value `literal`"
        self.root = self.base / 'share/meowfetch'
        self.launcher = self.base / 'bin/meowfetch'
        self.patch = mock.patch.object(installer, 'locations', return_value=(self.root, self.launcher))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def install(self):
        installer.install(PACKAGE)

    def assert_launcher_works(self):
        result = subprocess.run([str(self.launcher), '--version'], cwd=self.temporary.name,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('meowfetch 1.2.0', result.stdout)

    def archive(self, extra=None):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            for path in PACKAGE.rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    archive.writestr('meowfetch-main/meowfetch/' + path.relative_to(PACKAGE).as_posix(), path.read_bytes())
            if extra:
                archive.writestr(*extra)
        buffer.seek(0)
        return buffer

    def test_local_install_launcher_handles_shell_characters_and_resources(self):
        self.install()
        self.assert_launcher_works()
        self.assertTrue((self.root / 'meowfetch/data/cats.json').is_file())
        self.assertIn('Run now:', self.output.getvalue())

    def test_download_install_without_git_and_update_after_manual_install(self):
        self.install()
        (self.root / 'meowfetch/obsolete.py').write_text('old code')
        (self.root / 'personal.txt').write_text('keep me')
        with mock.patch.object(installer, 'urlopen', return_value=self.archive()) as download:
            self.assertEqual(installer.main(['update']), 0)
        download.assert_called_once_with(installer.ARCHIVE_URL, timeout=30)
        self.assertFalse((self.root / 'meowfetch/obsolete.py').exists())
        self.assertEqual((self.root / 'personal.txt').read_text(), 'keep me')
        self.assertFalse((self.root / '.git').exists())
        self.assert_launcher_works()

    def test_fresh_archive_install(self):
        with mock.patch.object(installer, 'urlopen', return_value=self.archive()):
            self.assertEqual(installer.main(['install']), 0)
        self.assert_launcher_works()

    def test_legacy_checkout_and_local_changes_are_preserved(self):
        self.install()
        (self.root / '.git').mkdir()
        (self.root / '.git/config').write_text('original repository')
        (self.root / 'meowfetch/custom.py').write_text('local change')
        self.install()
        backups = list(self.root.parent.glob('meowfetch-backup-*/checkout'))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / 'meowfetch/custom.py').read_text(), 'local change')
        self.assertEqual((backups[0] / '.git/config').read_text(), 'original repository')
        self.assertFalse((self.root / '.git').exists())
        self.assert_launcher_works()

    def test_invalid_package_leaves_current_installation_untouched(self):
        self.install()
        launcher_before = self.launcher.read_bytes()
        broken = self.base / 'broken'
        broken.mkdir()
        (broken / '__init__.py').write_text('')
        (broken / 'installer.py').write_text('')
        (broken / '__main__.py').write_text('raise RuntimeError("bad release")')
        with self.assertRaisesRegex(ValueError, 'startup check'):
            installer.install(broken)
        self.assertEqual(self.launcher.read_bytes(), launcher_before)
        self.assert_launcher_works()

    def test_interrupt_during_the_swap_restores_the_installation(self):
        self.install()
        (self.root / 'meowfetch/old.txt').write_text('old installation')
        real_rename, renames = Path.rename, []
        def interrupt_second(source, target):
            renames.append(source)
            if len(renames) == 2:
                raise KeyboardInterrupt
            return real_rename(source, target)
        with mock.patch.object(Path, 'rename', interrupt_second):
            with self.assertRaises(KeyboardInterrupt):
                self.install()
        self.assertEqual((self.root / 'meowfetch/old.txt').read_text(), 'old installation')
        self.assert_launcher_works()
        self.assertEqual(list(self.launcher.parent.glob('.meowfetch-launcher-*')), [])

    def test_launcher_installs_when_it_is_on_another_filesystem(self):
        real_replace = Path.replace
        def same_filesystem_only(source, target):
            if source.parent != Path(target).parent:
                raise OSError(errno.EXDEV, 'Invalid cross-device link')
            return real_replace(source, target)
        with mock.patch.object(Path, 'replace', same_filesystem_only):
            self.install()
        self.assert_launcher_works()
        self.assertEqual(list(self.launcher.parent.glob('.meowfetch-launcher-*')), [])

    def test_oversized_download_leaves_working_installation(self):
        self.install()
        with mock.patch.object(installer, 'MAX_ARCHIVE_BYTES', 16), \
                mock.patch.object(installer, 'urlopen', return_value=self.archive()), \
                contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(installer.main(['update']), 1)
        self.assertIn('larger than expected', error.getvalue())
        self.assert_launcher_works()

    def test_oversized_extraction_leaves_working_installation(self):
        self.install()
        with mock.patch.object(installer, 'MAX_EXTRACTED_BYTES', 16), \
                mock.patch.object(installer, 'urlopen', return_value=self.archive()), \
                contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(installer.main(['update']), 1)
        self.assertIn('expands too far', error.getvalue())
        self.assert_launcher_works()

    def test_failed_launcher_replacement_rolls_back_application(self):
        self.install()
        (self.root / 'meowfetch/old.txt').write_text('old installation')
        with mock.patch.object(Path, 'replace', side_effect=PermissionError('read-only launcher')):
            with self.assertRaises(PermissionError):
                self.install()
        self.assertEqual((self.root / 'meowfetch/old.txt').read_text(), 'old installation')
        self.assert_launcher_works()

    def test_install_refuses_to_replace_an_unrelated_launcher(self):
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_text('#!/bin/sh\necho unrelated\n')
        with self.assertRaisesRegex(ValueError, 'unrecognized launcher'):
            self.install()
        self.assertEqual(self.launcher.read_text(), '#!/bin/sh\necho unrelated\n')
        self.assertFalse(self.root.exists())

    def test_download_failure_leaves_working_installation(self):
        self.install()
        with mock.patch.object(installer, 'urlopen', side_effect=OSError('offline')), contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(installer.main(['update']), 1)
        self.assertIn('offline', error.getvalue())
        self.assert_launcher_works()
        self.assertEqual(list(self.root.parent.glob('.meowfetch-stage-*')), [])

    def test_truncated_archive_leaves_working_installation(self):
        self.install()
        with mock.patch.object(installer, 'urlopen', return_value=io.BytesIO(b'not a zip')), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(installer.main(['update']), 1)
        self.assert_launcher_works()

    def test_archive_rejects_path_traversal_and_symlinks(self):
        for entry in ('meowfetch-main/meowfetch/../../escape', '/absolute/path', 'meowfetch-main/meowfetch/..\\escape'):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as temp:
                with mock.patch.object(installer, 'urlopen', return_value=self.archive((entry, 'bad'))):
                    with self.assertRaisesRegex(ValueError, 'unsafe path'):
                        installer.download_package(Path(temp))
        link = zipfile.ZipInfo('meowfetch-main/meowfetch/link')
        link.external_attr = 0o120777 << 16
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(installer, 'urlopen', return_value=self.archive((link, '/tmp/target'))):
            with self.assertRaisesRegex(ValueError, 'symbolic link'):
                installer.download_package(Path(temp))

    def test_uninstall_removes_app_but_preserves_extra_files(self):
        self.install()
        (self.root / 'personal.txt').write_text('keep')
        self.assertEqual(installer.main(['uninstall']), 0)
        self.assertFalse(self.launcher.exists())
        self.assertFalse((self.root / 'meowfetch').exists())
        self.assertEqual((self.root / 'personal.txt').read_text(), 'keep')

    def test_failed_package_removal_keeps_the_launcher_working(self):
        self.install()
        with mock.patch.object(installer.shutil, 'rmtree',
                               side_effect=PermissionError('locked package')):
            with self.assertRaises(PermissionError):
                installer.uninstall()
        self.assert_launcher_works()
        self.assertTrue((self.root / 'meowfetch').is_dir())

    def test_uninstall_clean_install_removes_root(self):
        self.install()
        installer.uninstall()
        self.assertFalse(self.root.exists())
        self.assertFalse(self.launcher.exists())

    def test_uninstall_refuses_legacy_checkout(self):
        self.install()
        (self.root / '.git').mkdir()
        with self.assertRaisesRegex(ValueError, 'Git checkout'):
            installer.uninstall()
        self.assert_launcher_works()

    def test_uninstall_refuses_an_unmarked_installation_without_our_launcher(self):
        (self.root / 'meowfetch').mkdir(parents=True)
        (self.root / 'meowfetch/__main__.py').write_text('personal program')
        with self.assertRaisesRegex(ValueError, 'unrecognized installation'):
            installer.uninstall()
        self.assertTrue((self.root / 'meowfetch/__main__.py').is_file())

    def test_install_refuses_unrelated_directory(self):
        self.root.mkdir(parents=True)
        (self.root / 'precious.txt').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'unrecognized'):
            self.install()
        self.assertEqual((self.root / 'precious.txt').read_text(), 'keep')

    def test_install_refuses_symlink_destination(self):
        target = self.base / 'target'
        target.mkdir(parents=True)
        self.root.parent.mkdir(parents=True)
        self.root.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symbolic links'):
            self.install()
        self.assertEqual(list(target.iterdir()), [])

    def test_path_help_for_bash_zsh_and_fish(self):
        for shell, expected in (('/bin/bash', '~/.bashrc'), ('/bin/zsh', '~/.zshrc'), ('/bin/fish', 'fish_add_path')):
            with self.subTest(shell=shell), mock.patch.dict(os.environ, {'SHELL': shell, 'PATH': ''}), contextlib.redirect_stdout(io.StringIO()) as output:
                installer.path_help(Path('/example/.local/bin/meowfetch'))
                self.assertIn(expected, output.getvalue())
                self.assertIn('Run now:', output.getvalue())

    def test_path_help_is_quiet_when_the_directory_is_already_listed(self):
        home = Path(os.path.expanduser('~'))
        for parent, entry in ((Path('/example/.local/bin'), '/example/.local/bin/'),
                              (home / '.local/bin', '~/.local/bin')):
            with self.subTest(entry=entry), mock.patch.dict(os.environ, {'PATH': entry}), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                installer.path_help(parent / 'meowfetch')
            self.assertNotIn('export PATH', output.getvalue())

    def test_missing_entry_points_are_rejected(self):
        empty = self.base / 'empty'
        empty.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'entry points'):
            installer.install(empty)
        self.assertFalse(self.launcher.exists())

    def test_windows_location_preserves_existing_lib_layout(self):
        self.patch.stop()
        with mock.patch.object(installer.platform, 'system', return_value='Windows'), mock.patch.dict(os.environ, {'LOCALAPPDATA': str(self.base)}):
            root, launcher = installer.locations()
        self.assertEqual(root, self.base / 'Programs/meowfetch/lib')
        self.assertEqual(launcher, self.base / 'Programs/meowfetch/meowfetch.cmd')

    def test_cli_dispatches_management_and_preserves_exit_status(self):
        from meowfetch import __main__ as app
        for flag, action in (('--update', 'update'), ('--uninstall', 'uninstall')):
            with self.subTest(flag=flag), mock.patch.object(sys, 'argv', ['meowfetch', flag]), mock.patch.object(installer, 'main', return_value=1) as manage:
                with self.assertRaises(SystemExit) as result:
                    app.cli()
                self.assertEqual(result.exception.code, 1)
                manage.assert_called_once_with([action])

    def test_cli_rejects_conflicting_actions(self):
        from meowfetch import __main__ as app
        with mock.patch.object(sys, 'argv', ['meowfetch', '--update', '--uninstall']), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                app.cli()
        self.assertEqual(result.exception.code, 2)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.bin = Path(self.temporary.name) / 'bin'
        self.bin.mkdir()
        for executable in ('mktemp', 'rm'):
            (self.bin / executable).symlink_to(shutil.which(executable))
        (self.bin / 'python3.9').symlink_to(sys.executable)
        self.home = Path(self.temporary.name) / 'home'
        self.home.mkdir()
        self.env = dict(os.environ, PATH=str(self.bin), HOME=str(self.home))

    def run_script(self, *args):
        return subprocess.run(['/bin/sh', str(SCRIPT), *args], env=self.env,
                              capture_output=True, text=True, timeout=15)

    def curl_stub(self, code):
        stub = self.bin / 'curl'
        stub.write_text('#!' + sys.executable + '\n' + code)
        stub.chmod(0o755)

    def test_bootstrap_without_git_downloads_and_dispatches_action(self):
        self.curl_stub('import pathlib, sys\npathlib.Path(sys.argv[sys.argv.index("-o") + 1]).write_text("import sys; print(\\\"action=\\\" + sys.argv[1])")\n')
        for action in ('install', 'update', 'uninstall'):
            result = self.run_script(action)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('action=' + action, result.stdout)

    def test_failed_download_stops_before_running_installer(self):
        self.curl_stub('import sys\nsys.exit(22)\n')
        result = self.run_script()
        self.assertEqual(result.returncode, 22)

    def test_missing_curl_has_clear_error(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn('curl is required', result.stderr)

    def test_missing_python_has_clear_error(self):
        (self.bin / 'python3.9').unlink()
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn('Python 3.9 or newer', result.stderr)

    def test_uninstall_uses_the_installed_copy_instead_of_the_network(self):
        installed = self.home / '.local/share/meowfetch/meowfetch'
        installed.mkdir(parents=True)
        (installed / 'installer.py').write_text('import sys; print("local " + sys.argv[1])')
        result = self.run_script('uninstall')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('local uninstall', result.stdout)

    def test_help_and_invalid_action_need_no_dependencies(self):
        self.assertEqual(self.run_script('--help').returncode, 0)
        self.assertEqual(self.run_script('invalid').returncode, 2)


if __name__ == '__main__':
    unittest.main()
