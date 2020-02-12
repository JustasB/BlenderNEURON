rm -rf htmlcov
coverage erase

python tests/test_coverage.py && \
python tests/test_CommNode.py && \
python tests/test_blender_node.py && \
python tests/test_cell_import_export.py && \
python tests/test_layer_confinement.py && \
python tests/test_synapse_former.py

coverage combine
coverage html
coverage report
