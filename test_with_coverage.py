import coverage
import unittest

# Start coverage
cov = coverage.Coverage()
cov.start()


# Load the specific test case
# test_suite = unittest.defaultTestLoader.loadTestsFromName('tests.test_serializer.TestSerialization')

# Discover and run tests in "test" dir
test_suite = unittest.TestLoader().discover(start_dir="tests")


test_runner = unittest.TextTestRunner(verbosity=2, failfast=True)
result = test_runner.run(test_suite)

# Stop and save coverage data
try:
    cov.stop()
except AssertionError:
    # cov.stop() sometimes fails even though it saved the coverage data
    # Not sure what's the actual cause, but this is a hackaround
    # It probably has something to do with multiprocessing, and not killing
    # blender/nrn processes gracefully at end of each unit test
    pass

cov.save()

# Report the coverage results
cov.html_report(directory="htmlcov")
cov.report()

# Exit with appropriate status code
if not result.wasSuccessful():
    exit(1)
