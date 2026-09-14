import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_lifecycle', TOOLS / 'build_lifecycle.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pirate-lifecycle-test-')
        self.root = Path(self.temp.name).resolve()
        for name in ['src', 'static', 'node_modules', 'tools', 'build']:
            (self.root / name).mkdir()
        (self.root / 'src/game.ts').write_text('const game = true;')
        (self.root / 'static/asset.png').write_bytes(b'original-asset')
        (self.root / 'static/manifest.webmanifest').write_text('{"name":"fixture"}')
        (self.root / 'build/previous.txt').write_text('original known-good package')
        for name in ['package.json', 'svelte.config.js', 'vite.config.ts', 'tsconfig.json', '.npmrc']:
            (self.root / name).write_text('{}')
        (self.root / 'tools/build-context.mjs').write_text('// fixture')
        self.lifecycle = module.Lifecycle(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def build(self, mode='success', release=None):
        with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink):
            with self.lifecycle.lock() as fd:
                self.lifecycle.build(fd, release=release, command=[sys.executable, '-B',
                                     str(TOOLS / 'tests/fixture_worker.py'), mode])

    def driver(self, mode):
        return subprocess.Popen([sys.executable, '-B', str(TOOLS / 'tests/fixture_driver.py'),
                                 str(self.root), mode], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def wait_ready(self, process):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if (self.root / 'worker-ready').exists():
                return int((self.root / 'worker-ready').read_text())
            if process.poll() is not None:
                self.fail(process.stderr.read().decode())
            time.sleep(0.02)
        self.fail('Worker did not start')

    def assert_empty_jobs(self):
        self.assertEqual(list((self.root / '.build-work/jobs').iterdir()), [])

    def test_success_migrates_previous_without_changing_bytes(self):
        self.build()
        self.assert_empty_jobs()
        self.assertTrue((self.root / 'build/index.html').is_file())
        previous = list((self.root / '.build-artifacts/preserved').glob('*/package/previous.txt'))
        self.assertEqual(len(previous), 1)
        self.assertEqual(previous[0].read_text(), 'original known-good package')
        self.assertEqual((self.root / 'static/asset.png').read_bytes(), b'original-asset')

    def test_failure_and_invalid_output_keep_previous_package(self):
        for mode in ['fail', 'invalid']:
            with self.assertRaises(RuntimeError):
                self.build(mode)
            self.assert_empty_jobs()
            self.assertEqual((self.root / 'build/previous.txt').read_text(), 'original known-good package')

    def test_failure_after_success_keeps_exact_pointer(self):
        self.build()
        before = os.readlink(self.root / 'build')
        with self.assertRaises(RuntimeError):
            self.build('fail')
        self.assertEqual(os.readlink(self.root / 'build'), before)

    def test_signal_cleanup_and_concurrent_build_protection(self):
        for signum in [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]:
            with self.subTest(signum=signum):
                (self.root / 'worker-ready').unlink(missing_ok=True)
                process = self.driver('hold')
                try:
                    self.wait_ready(process)
                    other = self.driver('clean')
                    _, error = other.communicate(timeout=10)
                    self.assertNotEqual(other.returncode, 0)
                    self.assertIn(b'active', error)
                    self.assertEqual(len(list((self.root / '.build-work/jobs').iterdir())), 1)
                    process.send_signal(signum)
                    process.communicate(timeout=10)
                    self.assertNotEqual(process.returncode, 0)
                    self.assert_empty_jobs()
                    self.assertTrue((self.root / 'build/previous.txt').is_file())
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()

    def test_sigkill_parent_keeps_orphan_lock_then_recovers(self):
        process = self.driver('hold')
        worker = self.wait_ready(process)
        try:
            process.kill()
            process.communicate(timeout=10)
            other = self.driver('clean')
            _, error = other.communicate(timeout=10)
            self.assertNotEqual(other.returncode, 0)
            self.assertIn(b'active', error)
            self.assertEqual(len(list((self.root / '.build-work/jobs').iterdir())), 1)
        finally:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(worker, signal.SIGKILL)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            cleanup = self.driver('clean')
            _, error = cleanup.communicate(timeout=10)
            if cleanup.returncode == 0:
                break
            time.sleep(0.05)
        self.assertEqual(cleanup.returncode, 0, error)
        self.assert_empty_jobs()
        self.assertTrue((self.root / 'build/previous.txt').is_file())

    def test_retention_logs_releases_and_symbols(self):
        self.build('symbols', release='v1')
        release = self.root / '.build-artifacts/releases/v1/package/index.html'
        original = release.read_bytes()
        # Tiny fixtures exercise count boundaries without rebuilding large assets.
        for _ in range(11):
            self.build('verbose')
        self.assertEqual(len(list((self.root / '.build-artifacts/dev').iterdir())), 2)
        logs = list((self.root / '.build-artifacts/logs').glob('*/raw.log'))
        self.assertEqual(len(logs), 10)
        self.assertTrue(all(p.stat().st_size <= module.LIMIT for p in logs))
        self.assertTrue(all(b'LOG-END' in p.read_bytes() for p in logs))
        self.assertEqual(release.read_bytes(), original)
        self.assertEqual(len(list((self.root / '.build-artifacts/symbols').glob('*/compiler.js.map'))), 1)
        self.assertTrue(list((self.root / '.build-artifacts/preserved').iterdir()))
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            self.build(release='v1')

    def test_unknown_and_symlink_entries_are_never_deleted(self):
        with self.lifecycle.lock():
            parent = self.root / '.build-work/jobs'
            unknown = parent / '1234567890123456-aaaaaaaaaaaa'
            unknown.mkdir()
            (unknown / 'keep').write_text('unknown')
            linked = parent / '1234567890123456-bbbbbbbbbbbb'
            linked.symlink_to(self.root / 'static', target_is_directory=True)
            with contextlib.redirect_stderr(io.StringIO()) as output:
                self.lifecycle.recover()
            self.assertIn(str(unknown), output.getvalue())
            self.assertIn(str(linked), output.getvalue())
            self.assertTrue((unknown / 'keep').exists())
            self.assertTrue((self.root / 'static/asset.png').exists())

    def test_symlink_workspace_root_is_rejected(self):
        (self.root / '.build-work').symlink_to(self.root / 'static', target_is_directory=True)
        with self.assertRaises(RuntimeError):
            with self.lifecycle.lock():
                self.fail('Acquired lock in unowned workspace')

    def test_cleanup_failure_warns_with_remaining_path(self):
        with self.lifecycle.lock():
            job = self.root / '.build-work/jobs/1234567890123456-cccccccccccc'
            self.lifecycle.initialize(job, 'job')
            with patch.object(module.shutil, 'rmtree', side_effect=PermissionError('test denied')):
                with contextlib.redirect_stderr(io.StringIO()) as output:
                    self.lifecycle.recover()
            self.assertIn(str(job), output.getvalue())
            self.assertIn('WARNING', output.getvalue())
            self.assertTrue(job.exists())

    def test_power_loss_migration_journal_restores_legacy_pointer(self):
        with self.lifecycle.lock():
            run_id = '1234567890123456-dddddddddddd'
            legacy = self.root / '.build-artifacts/preserved' / run_id
            self.lifecycle.initialize(legacy, 'preserved')
            module.atomic_json(self.root / '.build-work/legacy-migration.json',
                               self.lifecycle.metadata('migration', id=run_id))
            os.replace(self.root / 'build', legacy / 'package')
            self.lifecycle.recover()
            self.assertEqual((self.root / 'build/previous.txt').read_text(), 'original known-good package')
            self.assertFalse((self.root / '.build-work/legacy-migration.json').exists())


if __name__ == '__main__':
    unittest.main()
