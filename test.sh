rm -rf htmlcov
coverage erase

python -m unittest discover -v --start-directory tests

coverage combine
coverage html
coverage report
