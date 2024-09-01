# This will regenerate html files hosted on docs.blenderneuron.org
# from .rst files under [repo]/docs/source folder
# This requires sphinx and sphinx_rtd_theme python packages installed
# Install them with `pip install sphinx sphinx_rtd_theme`
# Once the html files are regenerated, check them into github and merge into the master branch
# Once merged, github will deploy them, via Github Pages, to docs.blenderneuron.org

touch docs/source/*.rst
mv docs html
cd html
make html
cd ..
mv html docs
