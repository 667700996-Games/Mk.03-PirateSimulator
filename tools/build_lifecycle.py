#!/usr/bin/env python3
"""Owned, locked build workspaces. Python 3.9+, macOS/Linux (including CI/WSL)."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time
import uuid

try:
    import fcntl
except ImportError:
    raise SystemExit('Build lifecycle requires POSIX locks: use macOS, Linux or WSL with Python 3.9+.')

SCHEMA = 'piratesimulator-build-v1'
LIMIT = 1024 * 1024
ID = re.compile(r'^[0-9]{16,20}-[0-9a-f]{12}$')


def warn(path, error):
    print(f'WARNING: cleanup/preservation incomplete; remaining path: {path}: {error}', file=sys.stderr)


def read_json(path):
    if path.is_symlink():
        raise RuntimeError(f'Refusing symlink metadata: {path}')
    return json.loads(path.read_text())


def atomic_json(path, data):
    temp = path.with_name(path.name + '.new')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    sync_dir(path.parent)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def plain_dir(path):
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise RuntimeError(f'Refusing non-directory/symlink: {path}')
    path.mkdir(mode=0o700, exist_ok=True)


class Lifecycle:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.work = self.root / '.build-work'
        self.artifacts = self.root / '.build-artifacts'
        self.warnings = 0

    def metadata(self, kind, **extra):
        return dict(schema=SCHEMA, root=str(self.root), kind=kind, **extra)

    def owned(self, path, kind):
        if path.is_symlink() or not path.is_dir():
            return False
        try:
            data = read_json(path / '.owner.json')
            return all(data.get(k) == v for k, v in self.metadata(kind).items())
        except (OSError, ValueError, RuntimeError):
            return False

    def initialize(self, path, kind):
        # An existing unmarked directory is never adopted or recursively removed.
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            if not self.owned(path, kind):
                raise RuntimeError(f'Unowned directory; inspect manually: {path}')
        else:
            atomic_json(path / '.owner.json', self.metadata(kind))

    @contextlib.contextmanager
    def lock(self, shared=False):
        self.initialize(self.work, 'workspace-root')
        fd = os.open(self.work / 'lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError(f'Another build/preview/cleanup is active; kept all files: {self.work}')
            self.initialize(self.artifacts, 'artifact-root')
            for name in ['dev', 'releases', 'preserved', 'symbols', 'logs']:
                plain_dir(self.artifacts / name)
            plain_dir(self.work / 'jobs')
            # Do not unlink the lock file: its inode is the cross-process authority.
            yield fd
        finally:
            os.close(fd)

    def warning(self, path, error):
        self.warnings += 1
        warn(path, error)

    def remove_owned(self, path, parent, kind):
        if path.parent != parent or not ID.fullmatch(path.name) or not self.owned(path, kind):
            self.warning(path, 'not a recognized owned entry; preserved')
            return False
        try:
            # rmtree does not follow child symlinks. Reject mount points as well.
            device = parent.stat().st_dev
            for base, dirs, _ in os.walk(path, followlinks=False):
                for name in dirs:
                    child = Path(base) / name
                    if not child.is_symlink() and child.stat().st_dev != device:
                        raise RuntimeError(f'mounted filesystem within workspace: {child}')
            shutil.rmtree(path)
            print(f'Cleaned owned {kind}: {path}')
            return True
        except OSError as error:
            self.warning(path, error)
            return False

    def current(self):
        link = self.root / 'build'
        return link.resolve() if link.exists() else None

    def recover(self):
        # The exclusive OS lock also remains held by an orphan Vite worker.
        self.recover_migration()
        for path in sorted((self.work / 'jobs').iterdir()):
            if self.owned(path, 'job'):
                try:
                    self.archive_symbols(path, path.name)
                except (OSError, RuntimeError) as error:
                    self.warning(path, f'cannot preserve symbols: {error}')
                    continue
            self.remove_owned(path, self.work / 'jobs', 'job')
        self.prune()

    def prune(self):
        for kind, count in [('dev', 2), ('logs', 10)]:
            parent = self.artifacts / kind
            entries = []
            for path in parent.iterdir():
                if not ID.fullmatch(path.name) or not self.owned(path, kind):
                    self.warning(path, 'unknown artifact; preserved')
                    continue
                data = read_json(path / '.owner.json')
                if kind == 'dev' and data.get('status') != 'success':
                    if self.current() != path / 'package':
                        self.remove_owned(path, parent, kind)
                    continue
                entries.append(path)
            for path in sorted(entries, reverse=True)[count:]:
                if self.current() == path / 'package':
                    self.warning(path, 'current package is pinned; retained beyond quota')
                    continue
                self.remove_owned(path, parent, kind)

    def archive_symbols(self, job, run_id):
        maps = []
        for base, dirs, files in os.walk(job, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(base) / d).is_symlink()]
            maps.extend(Path(base) / f for f in files if f.endswith('.map'))
        if not maps:
            return
        dest = self.artifacts / 'symbols' / run_id
        if not dest.exists():
            self.initialize(dest, 'symbols')
        elif not self.owned(dest, 'symbols'):
            raise RuntimeError(f'Unowned symbol archive: {dest}')
        for source in maps:
            if source.is_symlink():
                raise RuntimeError(f'Symbol symlink requires review: {source}')
            target = dest / source.relative_to(job)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and digest(target) != digest(source):
                raise RuntimeError(f'Symbol archive conflict: {target}')
            shutil.copy2(source, target)

    def snapshot(self, job):
        project = job / 'project'
        project.mkdir()
        # Only the small source/config tree is copied. Large original assets and
        # installed dependencies are read through links, never copied or cleaned.
        shutil.copytree(self.root / 'src', project / 'src', symlinks=True)
        for name in ['package.json', 'svelte.config.js', 'vite.config.ts', 'tsconfig.json', '.npmrc']:
            shutil.copy2(self.root / name, project / name)
        for source in self.root.glob('.env*'):
            if source.is_file():
                shutil.copy2(source, project / source.name)
        (project / 'tools').mkdir()
        shutil.copy2(self.root / 'tools/build-context.mjs', project / 'tools/build-context.mjs')
        for name in ['static', 'node_modules']:
            (project / name).symlink_to(self.root / name, target_is_directory=True)
        (job / 'tmp').mkdir()
        return project

    def validate(self, package):
        for rel in ['index.html', 'service-worker.js', 'manifest.webmanifest', '_app/version.json']:
            path = package / rel
            if path.is_symlink() or not path.is_file() or not path.stat().st_size:
                raise RuntimeError(f'Missing/empty package component: {path}')
        json.loads((package / 'manifest.webmanifest').read_text())
        json.loads((package / '_app/version.json').read_text())
        if not list((package / '_app/immutable').rglob('*.js')):
            raise RuntimeError('Package has no application JavaScript')
        for source in (self.root / 'static').rglob('*'):
            if source.is_file() and source.name != '.DS_Store':
                target = package / source.relative_to(self.root / 'static')
                if not target.is_file() or digest(source) != digest(target):
                    raise RuntimeError(f'Static asset missing/changed: {target}')
        return {str(p.relative_to(package)): digest(p) for p in package.rglob('*') if p.is_file()}

    def switch_link(self, target):
        temp = self.work / 'next-build'
        if temp.is_symlink():
            temp.unlink()
        elif temp.exists():
            raise RuntimeError(f'Unexpected pointer staging file: {temp}')
        # Link is ultimately placed in the project root, so its target is root-relative.
        temp.symlink_to(target.relative_to(self.root), target_is_directory=True)
        os.replace(temp, self.root / 'build')
        sync_dir(self.root)

    def recover_migration(self):
        journal = self.work / 'legacy-migration.json'
        if not journal.exists():
            return
        data = read_json(journal)
        if data.get('schema') != SCHEMA or data.get('root') != str(self.root) or not ID.fullmatch(data.get('id', '')):
            raise RuntimeError(f'Unknown migration journal: {journal}')
        legacy = self.artifacts / 'preserved' / data['id'] / 'package'
        link = self.root / 'build'
        if not link.exists() and not link.is_symlink() and legacy.is_dir():
            self.switch_link(legacy)
        if not link.exists():
            raise RuntimeError(f'Migration needs manual recovery: {journal}')
        journal.unlink()

    def publish(self, job, run_id, manifest, release=None):
        kind = 'releases' if release else 'dev'
        dest = self.artifacts / kind / (release or run_id)
        if dest.exists() or dest.is_symlink():
            raise RuntimeError(f'Will not overwrite existing archive: {dest}')
        self.initialize(dest, kind)
        atomic_json(dest / '.owner.json', self.metadata(kind, status='incomplete', id=run_id))
        atomic_json(dest / 'manifest.json', manifest)
        os.replace(job / 'package', dest / 'package')
        atomic_json(dest / '.owner.json', self.metadata(kind, status='success', id=run_id))
        link = self.root / 'build'
        if link.is_symlink():
            target = link.resolve()
            if not target.is_relative_to(self.artifacts) or not target.is_dir():
                raise RuntimeError(f'Unmanaged build symlink; preserved: {link}')
        elif link.exists():
            if not link.is_dir():
                raise RuntimeError(f'Unmanaged build file; preserved: {link}')
            legacy = self.artifacts / 'preserved' / run_id
            self.initialize(legacy, 'preserved')
            atomic_json(legacy / 'manifest.json', {
                'reason': 'Pre-policy build: release/rollback status unknown; never auto-delete',
                'sha256': {str(p.relative_to(link)): digest(p) for p in link.rglob('*') if p.is_file()}
            })
            atomic_json(self.work / 'legacy-migration.json', self.metadata('migration', id=run_id))
            os.replace(link, legacy / 'package')
            sync_dir(legacy)
            # Establish the preserved version first; a crash is recoverable via journal.
            self.switch_link(legacy / 'package')
            (self.work / 'legacy-migration.json').unlink()
        self.switch_link(dest / 'package')
        print(f'Published validated package: {link} -> {dest / "package"}')

    def build(self, lock_fd, release=None, command=None):
        if release and (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', release) or release in ['.', '..']):
            raise RuntimeError('Release name must be a simple identifier, not a path')
        if release and (self.artifacts / 'releases' / release).exists():
            raise RuntimeError('Release already exists; immutable archives cannot be overwritten')
        self.recover()
        run_id = f'{time.time_ns()}-{uuid.uuid4().hex[:12]}'
        job = self.work / 'jobs' / run_id
        self.initialize(job, 'job')
        atomic_json(job / '.owner.json', self.metadata('job', pid=os.getpid(), id=run_id))
        log = self.artifacts / 'logs' / run_id
        self.initialize(log, 'logs')
        try:
            project = self.snapshot(job)
            env = dict(os.environ, PIRATE_BUILD_JOB=str(job), PIRATE_BUILD_ROOT=str(self.root),
                       TMPDIR=str(job / 'tmp'), TMP=str(job / 'tmp'), TEMP=str(job / 'tmp'))
            cmd = command or ['node', str(self.root / 'tools/build-worker.mjs')]
            result = run_child(cmd, project, env, lock_fd, log / 'raw.log')
            if result:
                raise RuntimeError(f'Build failed/interrupted (exit {result}); previous build preserved. Log: {log}')
            manifest = {'id': run_id, 'type': 'release' if release else 'development',
                        'sha256': self.validate(job / 'package')}
            git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=self.root, capture_output=True, text=True)
            manifest['git_commit'] = git.stdout.strip() if git.returncode == 0 else None
            manifest['source_sha256'] = {str(p.relative_to(project)): digest(p)
                                        for p in (project / 'src').rglob('*') if p.is_file()}
            self.archive_symbols(job, run_id)
            self.publish(job, run_id, manifest, release)
        finally:
            try:
                self.archive_symbols(job, run_id)
            except (OSError, RuntimeError) as error:
                self.warning(job, f'symbol preservation failed; workspace retained: {error}')
            else:
                self.remove_owned(job, self.work / 'jobs', 'job')
            self.prune()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def run_child(command, cwd, env, lock_fd, log_path=None):
    """The child inherits the flock FD; killing only this supervisor cannot unlock it."""
    child = None
    interrupted = None
    deadline = None

    def stop(signum, _frame):
        nonlocal interrupted, deadline
        interrupted = signum
        deadline = time.monotonic() + 5
        if child is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child.pid, signum)

    previous = {s: signal.signal(s, stop) for s in [signal.SIGINT, signal.SIGTERM, signal.SIGHUP]}
    tail = bytearray()
    try:
        child = subprocess.Popen(command, cwd=cwd, env=env, pass_fds=(lock_fd,),
                                 start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if interrupted:
            stop(interrupted, None)
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            while selector.get_map():
                if deadline and time.monotonic() >= deadline:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(child.pid, signal.SIGKILL)
                    deadline = None
                for key, _ in selector.select(timeout=0.1):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    with contextlib.suppress(BrokenPipeError, OSError):
                        sys.stdout.buffer.write(chunk)
                        sys.stdout.buffer.flush()
                    if log_path:
                        tail.extend(chunk)
                        del tail[:-LIMIT]
                        with log_path.open('wb') as stream:
                            stream.write(tail)
            result = child.wait()
        return 128 + interrupted if interrupted else result
    finally:
        # Exceptions (including disk full) must stop the worker before removing its files.
        if child is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            child.stdout.close()
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'clean', 'preview'])
    parser.add_argument('--release', help='Immutable explicitly named release archive; no automatic expiry')
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=4173)
    args = parser.parse_args()
    lifecycle = Lifecycle(Path(__file__).resolve().parent.parent)
    try:
        with lifecycle.lock(shared=args.action == 'preview') as fd:
            if args.action == 'clean':
                lifecycle.recover()
            elif args.action == 'build':
                lifecycle.build(fd, args.release)
            else:
                package = lifecycle.current()
                if package is None:
                    raise RuntimeError('No successful build. Run npm run build first.')
                return run_child(['node', str(lifecycle.root / 'tools/preview.mjs'), str(package),
                                  args.host, str(args.port)], lifecycle.root, os.environ, fd)
        return 1 if lifecycle.warnings else 0
    except (OSError, RuntimeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
