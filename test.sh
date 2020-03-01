rm -rf htmlcov
coverage erase

python -m unittest discover --start-directory tests

coverage combine
coverage html
coverage report
