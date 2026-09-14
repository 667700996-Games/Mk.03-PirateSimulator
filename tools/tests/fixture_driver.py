import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_lifecycle import Lifecycle  # noqa: E402

lifecycle = Lifecycle(sys.argv[1])
try:
    with lifecycle.lock() as fd:
        if sys.argv[2] == 'clean':
            lifecycle.recover()
        else:
            lifecycle.build(fd, command=[sys.executable, '-B',
                                         str(Path(__file__).with_name('fixture_worker.py')), sys.argv[2]])
except RuntimeError as error:
    print(error, file=sys.stderr)
    sys.exit(1)
