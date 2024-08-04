rm -rf htmlcov
coverage erase

coverage run -m unittest discover -v --start-directory tests

coverage combine
coverage html
coverage report
