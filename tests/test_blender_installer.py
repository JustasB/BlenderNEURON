"""Verify archive integrity and bundled-Python setup in the shared installer."""
import hashlib
import importlib.util
import io
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('blender_installer', ROOT / 'scripts/install_blender.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class TestBlenderInstaller(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.destination = self.root / 'installed'
        self.archive = self.root / 'fixture.tar.xz'
        uncompressed = self.root / 'fixture.tar'
        with tarfile.open(str(uncompressed), 'w') as archive:
            content = b'fixture executable'
            info = tarfile.TarInfo('blender-5.2.3-linux-x64/blender')
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        subprocess.check_call(['xz', str(uncompressed)])
        self.checksum = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.calls = []
        self.real_check_call = subprocess.check_call

    def fake_download(self, command):
        self.calls.append(command)
        if command[0] != 'curl':
            return self.real_check_call(command)
        if command[-3].endswith('.tar.xz'):
            shutil.copy2(str(self.archive), command[-1])
        else:
            Path(command[-1]).write_text(self.checksum + '  blender-5.2.3-linux-x64.tar.xz\n')
        return 0

    def test_verified_archive_is_installed_without_wrapper_directory(self):
        with patch.object(installer.subprocess, 'check_call', side_effect=self.fake_download):
            installer.install('5.2.3', self.destination)
        self.assertEqual((self.destination / 'blender').read_bytes(), b'fixture executable')
        self.assertFalse(any(path.name.startswith('tmp') for path in self.root.iterdir()))

    def test_checksum_failure_does_not_extract_or_leave_installation(self):
        self.checksum = '0' * 64
        with patch.object(installer.subprocess, 'check_call', side_effect=self.fake_download):
            with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                installer.install('5.2.3', self.destination)
        self.assertFalse(self.destination.exists())
        self.assertFalse(any(command[0] == 'tar' for command in self.calls))

    def test_coverage_uses_the_bundled_interpreter_and_supported_version(self):
        for series, python, coverage in [('2.93', '3.9', '7.10.7'), ('5.2', '3.13', '7.12')]:
            with self.subTest(series=series):
                destination = self.root / series
                bundled = destination / series / 'python/bin' / ('python' + python)
                bundled.parent.mkdir(parents=True)
                bundled.touch()
                with patch.object(installer.subprocess, 'check_call') as call:
                    installer.install(series + '.0', destination, with_coverage=True)
                self.assertEqual(call.call_args_list[0][0][0], [str(bundled), '-m', 'ensurepip'])
                self.assertEqual(call.call_args_list[1][0][0],
                                 [str(bundled), '-m', 'pip', 'install', 'coverage==' + coverage])


if __name__ == '__main__':
    unittest.main()
