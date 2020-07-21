touch docs/source/*.rst
mv docs html
cd html
make html
cd ..
mv html docs
