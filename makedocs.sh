touch docs/source/*.md
mv docs html
cd html
make html
cd ..
mv html docs
