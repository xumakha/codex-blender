import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codex_blender import config, launcher
from unittest.mock import MagicMock


class CodexRuntimeTests(unittest.TestCase):
    def test_launcher_does_not_reuse_old_server(self):
        with patch.object(launcher,'source_revision',return_value='new'):
            with patch.object(launcher,'server_info',return_value={'application':'frame-studio'}):
                self.assertFalse(launcher.ready())
            with patch.object(launcher,'server_info',return_value={'application':'frame-studio','server_revision':'old'}):
                self.assertFalse(launcher.ready())
            with patch.object(launcher,'server_info',return_value={'application':'frame-studio','server_revision':'new'}):
                self.assertTrue(launcher.ready())

    def test_stale_server_restart_checks_process_ownership_and_busy_work(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(launcher,'DATA',Path(directory)):
            root=Path(directory)
            (root/'server.pid').write_text('1234')
            process=MagicMock()
            process.cwd.return_value=str(config.ROOT)
            process.cmdline.return_value=['python','-m','unrelated.service']
            with patch.object(launcher.psutil,'Process',return_value=process):
                with self.assertRaisesRegex(RuntimeError,'xác minh'):launcher.stop_stale_server()
                process.terminate.assert_not_called()
                process.cmdline.return_value=['python','-m','codex_blender.cli','studio']
                folder=root/'projects'/'test';folder.mkdir(parents=True)
                (folder/'project.json').write_text('{"state":"planning"}')
                with self.assertRaisesRegex(RuntimeError,'tác vụ'):launcher.stop_stale_server()
                process.terminate.assert_not_called()
                (folder/'project.json').write_text('{"state":"ready"}')
                launcher.stop_stale_server()
                process.terminate.assert_called_once()

    def test_native_executable_does_not_require_npm(self):
        with patch.dict(os.environ, {'CODEX_PATH': 'C:/Apps/Codex/codex.exe'}), patch.object(config.shutil, 'which', return_value=None):
            self.assertEqual(config.codex_command(), ['C:/Apps/Codex/codex.exe'])

    def test_npm_wrapper_uses_node_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / 'node_modules/@openai/codex/bin/codex.js'
            entry.parent.mkdir(parents=True)
            entry.touch()
            with patch.dict(os.environ, {'CODEX_PATH': str(root / 'codex.cmd')}), patch.object(config.shutil, 'which', return_value='node'):
                self.assertEqual(config.codex_command(), ['node', str(entry)])

    @unittest.skipUnless(os.name == 'nt', 'Windows extension layout')
    def test_discovers_vscode_bundled_cli_without_path(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            binary = home / '.vscode/extensions/openai.chatgpt-test/bin/windows-x86_64/codex.exe'
            binary.parent.mkdir(parents=True)
            binary.touch()
            with patch.dict(os.environ, {'CODEX_PATH': ''}), patch.object(config.shutil, 'which', return_value=None), patch.object(config.Path, 'home', return_value=home):
                self.assertEqual(config.codex_command(), [str(binary)])
