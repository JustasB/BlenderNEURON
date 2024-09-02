rm -rf htmlcov
coverage erase

export COVERAGE_PROCESS_START=.coveragerc

# Run all tests under [repo]/tests
coverage run -m unittest discover -v --start-directory tests

# Single test example:
#coverage run -m unittest tests.test_blender_node.TestBlenderNode.test_add_remove_group_and_cells

coverage combine
coverage xml
coverage html
coverage report
