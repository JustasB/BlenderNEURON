import ctypes
import os
import select
import signal
import subprocess
import sys
import time
import unittest

from tests.process_utils import reap_descendants, stop_process_group


# Only audited, process-independent classes may share an interpreter. New classes
# remain isolated by default; NEURON/MPI/lifecycle classes are deliberately absent.
BATCH_CLASSES = frozenset(('test_serializer.TestSerialization', 'test_rdp.TestRDP',
                           'test_datablock_names.TestNameEncoder'))


def test_batches(tests):
    pending = []
    for test in tests:
        batchable = (os.environ.get('BLENDERNEURON_TEST_BATCH', '1') != '0'
                     and test.id().rsplit('.', 1)[0] in BATCH_CLASSES)
        if pending and (not batchable or
                        pending[0].id().rsplit('.', 1)[0] != test.id().rsplit('.', 1)[0]):
            yield pending
            pending = []
        if batchable:
            pending.append(test)
        else:
            yield [test]
    if pending:
        yield pending


def run_batch(tests, timeout):
    """Reuse Python, not the deadline: each start event resets the watchdog."""
    read_fd, write_fd = os.pipe()
    process = None
    try:
        process = subprocess.Popen(
            [sys.executable, 'tests/batch_worker.py', str(write_fd)] + [test.id() for test in tests],
            pass_fds=(write_fd,), start_new_session=True)
        os.close(write_fd)
        write_fd = None
        deadline = time.monotonic() + timeout  # Also bound imports/startup.
        current = 'batch startup'
        pending = b''
        complete = False
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                print('TIMEOUT: %s' % current, file=sys.stderr, flush=True)
                return 124
            ready, _, _ = select.select([read_fd], [], [], min(.05, remaining))
            if ready:
                chunk = os.read(read_fd, 65536)
                if not chunk:
                    # EOF is not completion: a worker can close its pipe and hang.
                    process.wait(timeout=max(.001, deadline - time.monotonic()))
                    break
                pending += chunk
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    if line == b'COMPLETE':
                        complete = True
                        continue
                    current = line.decode('utf-8')
                    deadline = time.monotonic() + timeout
                    print('Running %s (batched; timeout %ss)' % (current, timeout), flush=True)
        if process.returncode == 0 and not complete:
            print('ERROR: batch exited without completing its tests', file=sys.stderr, flush=True)
            return 1
        return process.returncode
    except subprocess.TimeoutExpired:
        print('TIMEOUT: batch exit', file=sys.stderr, flush=True)
        return 124
    finally:
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)
        if process is not None:
            try:
                stop_process_group(process)
            finally:
                reap_descendants()


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
    for batch in test_batches(iter_tests(suite)):
        if len(batch) > 1:
            status = run_batch(batch, timeout)
            if status:
                return status
            continue
        test = batch[0]
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
