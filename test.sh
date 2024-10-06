set -e

rm -rf htmlcov
coverage erase

export COVERAGE_PROCESS_START=.coveragerc

# Run all tests under [repo]/tests
# To run single test, see: test_with_coverage.py
python test_with_coverage.py

coverage combine
coverage xml
coverage html
coverage report
