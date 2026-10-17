"""Bounded cleanup for processes owned by the integration-test harness."""
import os
import signal
import subprocess
import time


def stop_process_group(process, timeout=3):
    """Stop the whole session, even when its original leader already exited."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        pass
    # A launcher can exit before its children, so always signal the group.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=timeout)


def descendants(pid):
    """Return Linux descendants, including children adopted by a subreaper."""
    parents = {}
    for entry in os.listdir('/proc'):
        if entry.isdigit():
            try:
                with open('/proc/%s/stat' % entry) as stream:
                    fields = stream.read().rsplit(')', 1)[1].split()
                parents[int(entry)] = int(fields[1])
            except (OSError, ValueError, IndexError):
                pass
    found = {pid}
    while True:
        added = {child for child, parent in parents.items() if parent in found} - found
        if not added:
            return found - {pid}
        found.update(added)


def reap_descendants(timeout=3):
    """Clean up orphaned test children; caller must be a Linux subreaper."""
    deadline = time.monotonic() + timeout
    while True:
        children = descendants(os.getpid())
        for pid in children:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
            except ChildProcessError:
                break
        if not descendants(os.getpid()):
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Test descendants did not exit after SIGKILL')
        time.sleep(0.05)
