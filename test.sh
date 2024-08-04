rm -rf htmlcov
coverage erase

export COVERAGE_PROCESS_START=.coveragerc
coverage run -m unittest discover -v --start-directory tests

coverage combine
coverage html
coverage report
