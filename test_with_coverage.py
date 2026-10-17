import ctypes
import os
import signal
import subprocess
import sys
import unittest

from tests.process_utils import reap_descendants, stop_process_group


def iter_tests(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from iter_tests(test)
        else:
            yield test


def test_file(test):
    module = test.__class__.__module__.rsplit('.', 1)[-1]
    return os.path.join('tests', module + '.py')


def interrupted(signum, frame):
    raise KeyboardInterrupt


def main():
    # Docker runs Linux. Adopt orphaned grandchildren so they can be killed and
    # reaped even if a test crashes or exits without closing its context managers.
    if not sys.platform.startswith('linux'):
        raise RuntimeError('Run this test runner in Docker (Linux required)')
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'Could not enable child subreaper')
    signal.signal(signal.SIGTERM, interrupted)
    timeout = float(os.environ.get('BLENDERNEURON_TEST_TIMEOUT', '30'))
    suite = unittest.TestLoader().discover(start_dir='tests')
    for test in iter_tests(suite):
        test_name = test.id().rsplit('.', 2)[-2] + '.' + test._testMethodName
        print('Running %s (timeout %ss)' % (test.id(), timeout), flush=True)
        process = subprocess.Popen([sys.executable, test_file(test), test_name],
                                   start_new_session=True)
        try:
            try:
                status = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                print('TIMEOUT: %s' % test.id(), file=sys.stderr, flush=True)
                status = 124
        finally:
            try:
                stop_process_group(process)
            finally:
                reap_descendants()
        if status:
            return status
    return 0


if __name__ == '__main__':
    sys.exit(main())
