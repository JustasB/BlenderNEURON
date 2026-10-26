set -e

rm -rf htmlcov
coverage erase

export COVERAGE_PROCESS_START=.coveragerc

# Run all tests under [repo]/tests
# To run single test, see: test_with_coverage.py
test_status=0
python test_with_coverage.py || test_status=$?
if [ "$test_status" -ne 0 ] && [ "${BLENDERNEURON_TEST_KEEP_GOING:-0}" != 1 ]; then
  exit "$test_status"
fi

coverage_status=0
coverage combine || coverage_status=$?
coverage xml || coverage_status=$?
coverage html || coverage_status=$?
coverage report -m || coverage_status=$?
if [ "$test_status" -eq 0 ]; then
  test_status=$coverage_status
fi
exit "$test_status"
