rm .coverage
rm .coverage.*

./test.sh

coverage combine
coverage report
coverage html