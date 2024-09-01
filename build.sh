#!/bin/bash
set -e
# This will .zip files with the latest version of source files (.py, .hoc, .json)
# build pip wheels, and attempt to upload them to pypi (cancelable)
# Requires build and twine, install them with `pip install build twine`


function update_version_in_pyproject {
    version=$(grep -oP '(?<=version = ")[^"]*' pyproject.toml)
    echo "Current version is: $version"
    echo "Type in the new version"
    read new_version

    # Update the version in pyproject.toml
    sed -i "s/version = \"$version\"/version = \"$new_version\"/" pyproject.toml

    # Display the updated version
    echo "Updated version to: $new_version"

    file=releases/BlenderNEURON-v$new_version.zip
    file_latest=releases/BlenderNEURON-latest.zip

    # Create addon zip
    zip -q -r $file blenderneuron -i '*.py' '*.json' '*.hoc'
    cp $file $file_latest

    # Create wheels and upload to pip
    rm -R dist/* || true

    python -m build

    echo "Built Addon .zip file:" $file

    echo "Getting ready to upload to PyPI. Username=`__token__` and password=`pypi-[pypi token here]`"
    twine upload dist/*
}

while true; do
    read -p "This will build and upload to PyPI. Continue? [y/n]: " yn
    case $yn in
        [Yy]* ) update_version_in_pyproject; break;;
        [Nn]* ) exit;;
        * ) echo "Please answer yes or no.";;
    esac
done


