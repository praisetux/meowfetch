import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from meowfetch import collectors, utils
from meowfetch import __main__ as app


class CacheTests(unittest.TestCase):
    def test_save_cache_is_atomic_and_leaves_no_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(utils, '_CACHE_DIR', directory), \
                mock.patch.object(utils, '_CACHE_FILE', str(Path(directory) / 'cache.json')):
            utils.save_cache({'OS': {'ts': 1, 'val': 'Test Linux'}})
            self.assertEqual(
                json.loads((Path(directory) / 'cache.json').read_text()),
                {'OS': {'ts': 1, 'val': 'Test Linux'}},
            )
            self.assertEqual(list(Path(directory).glob('*.tmp')), [])

    def test_bad_and_future_timestamps_do_not_crash_or_get_reused(self):
        cache = {
            '_version': app.__version__,
            'OS': {'ts': None, 'val': 'bad cached value'},
            'Kernel': {'ts': 10**20, 'val': 'future cached value'},
        }
        collectors_to_patch = (
            'get_os', 'get_kernel', 'get_uptime', 'get_packages', 'get_shell',
            'get_terminal', 'get_cpu', 'get_gpu', 'get_ram', 'get_disk',
        )
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(app, 'load_cache', return_value=cache))
            stack.enter_context(mock.patch.object(app, 'save_cache'))
            stack.enter_context(mock.patch.object(app, 'festive_cat', return_value=None))
            for name in collectors_to_patch:
                stack.enter_context(mock.patch.object(app, name, return_value=f'fresh {name}'))
            output = io.StringIO()
            stack.enter_context(contextlib.redirect_stdout(output))
            app.main('cyan')
        self.assertIn('fresh get_os', output.getvalue())
        self.assertIn('fresh get_kernel', output.getvalue())
        self.assertNotIn('bad cached value', output.getvalue())
        self.assertNotIn('future cached value', output.getvalue())


class CollectorTests(unittest.TestCase):
    def test_skip_header_removes_heading_separator_and_blank_rows(self):
        filt = collectors._FILTERS['skip_header']
        self.assertFalse(filt('Name                 Id'))
        self.assertFalse(filt('Package              Version'))
        self.assertFalse(filt('-----------------------'))
        self.assertFalse(filt('   '))
        self.assertTrue(filt('Example Package'))
        self.assertTrue(filt('packagekit'))

    def test_a_failed_collector_does_not_stop_output(self):
        def broken():
            raise RuntimeError('collector failed')

        with mock.patch.object(app, 'get_os', side_effect=broken), \
                mock.patch.object(app, 'load_cache', return_value={}), \
                mock.patch.object(app, 'save_cache'), \
                mock.patch.object(app, 'festive_cat', return_value=None), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            app.main('cyan')
        self.assertIn('Kernel', output.getvalue())

    def test_windows_cpu_values_ignore_wmic_headings(self):
        responses = {
            ('powershell', '-Command',
             '(Get-CimInstance Win32_Processor).Name'): 'Example CPU',
            ('wmic', 'cpu', 'get', 'NumberOfCores'): 'NumberOfCores\n8',
            ('wmic', 'cpu', 'get', 'NumberOfLogicalProcessors'):
                'NumberOfLogicalProcessors\n16',
            ('wmic', 'cpu', 'get', 'MaxClockSpeed'): 'MaxClockSpeed\n4200',
        }

        with mock.patch.object(collectors, '_SYS', 'Windows'), \
                mock.patch.object(
                    collectors, 'run', side_effect=lambda *args: responses.get(args, '')
                ):
            value = collectors.get_cpu()

        self.assertEqual(value, 'Example CPU @ 4.2GHz (8C/16T)')


class OutputTests(unittest.TestCase):
    def test_redirected_output_contains_no_ansi_sequences(self):
        stream = io.StringIO()
        with mock.patch.object(app, 'load_cache', return_value={}), \
                mock.patch.object(app, 'save_cache'), \
                mock.patch.object(app, 'festive_cat', return_value=None), \
                contextlib.redirect_stdout(stream):
            app.main('bright_cyan')
        self.assertNotIn('\033[', stream.getvalue())


class InstallTests(unittest.TestCase):
    def test_manual_install_copies_package_to_permanent_location(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            package = source / 'meowfetch'
            package.mkdir(parents=True)
            (package / '__init__.py').write_text('', encoding='utf-8')
            (package / '__main__.py').write_text('def cli(): pass\n', encoding='utf-8')
            (package / 'installer.py').write_text('', encoding='utf-8')
            fake_utils = package / 'utils.py'
            fake_utils.write_text('', encoding='utf-8')
            home = root / 'home'
            home.mkdir()

            with mock.patch.object(utils, '__file__', str(fake_utils)), \
                    mock.patch.object(utils, '_SYS', 'Linux'), \
                    mock.patch.dict(os.environ, {'HOME': str(home)}):
                utils.install()

            installed = home / '.local/share/meowfetch/meowfetch/__main__.py'
            launcher = home / '.local/bin/meowfetch'
            self.assertTrue(installed.is_file())
            self.assertTrue(launcher.is_file())
            self.assertNotIn(str(source), launcher.read_text(encoding='utf-8'))



if __name__ == '__main__':
    unittest.main()
