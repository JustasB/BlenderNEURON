"""One interpreter for an explicitly audited batch; parent owns the watchdog."""
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))


class ProgressResult(unittest.TextTestResult):
    def startTest(self, test):
        os.write(PROGRESS_FD, (test.id() + '\n').encode('utf-8'))
        super().startTest(test)


if __name__ == '__main__':
    PROGRESS_FD = int(sys.argv[1])
    suite = unittest.defaultTestLoader.loadTestsFromNames(sys.argv[2:])
    result = unittest.TextTestRunner(resultclass=ProgressResult,
                                     failfast=os.environ.get('BLENDERNEURON_TEST_KEEP_GOING') != '1',
                                     verbosity=2).run(suite)
    if result.wasSuccessful():
        os.write(PROGRESS_FD, b'COMPLETE\n')
    sys.exit(0 if result.wasSuccessful() else 1)
