#!/bin/bash
set -e
# This will .zip files with the latest version of source files (.py, .hoc, .json)
# build pip wheels, and attempt to upload them to pypi (cancelable)
# Requires build and twine, install them with `pip install build twine`

function find_python {
    if [ -n "$PYTHON" ]; then
        echo "$PYTHON"
    elif command -v python >/dev/null 2>&1; then
        command -v python
    elif command -v python3 >/dev/null 2>&1; then
        command -v python3
    else
        echo "Could not find python or python3. Set PYTHON=/path/to/python and try again." >&2
        return 1
    fi
}

function require_python_module {
    python_bin="$1"
    module="$2"

    if ! "$python_bin" -m "$module" --help >/dev/null 2>&1; then
        echo "Missing Python module: $module" >&2
        echo "Install release dependencies with:" >&2
        echo "  \"$python_bin\" -m pip install build twine" >&2
        return 1
    fi
}


function update_version_in_pyproject {
    python_bin=$(find_python)
    require_python_module "$python_bin" build
    require_python_module "$python_bin" twine

    version=$(awk -F'"' '/^version = "/ { print $2; exit }' pyproject.toml)
    echo "Current version is: $version"
    echo "Type in the new version"
    read new_version

    # Update the version in pyproject.toml
    tmp_pyproject=$(mktemp "${TMPDIR:-/tmp}/pyproject.toml.XXXXXX")
    awk -v old_version="$version" -v new_version="$new_version" '
        $0 == "version = \"" old_version "\"" && !updated {
            print "version = \"" new_version "\""
            updated = 1
            next
        }
        { print }
    ' pyproject.toml > "$tmp_pyproject"
    mv "$tmp_pyproject" pyproject.toml

    # Display the updated version
    echo "Updated version to: $new_version"

    file=releases/BlenderNEURON-v$new_version.zip
    file_latest=releases/BlenderNEURON-latest.zip

    # Create addon zip
    zip -q -r "$file" blenderneuron -i '*.py' '*.json' '*.hoc'
    cp "$file" "$file_latest"

    # Create wheels and upload to pip
    rm -R dist/* || true

    "$python_bin" -m build

    echo "Built Addon .zip file:" "$file"

    echo "Getting ready to upload to PyPI. Username=`__token__` and password=`pypi-[pypi token here]`"
    "$python_bin" -m twine upload dist/*
}

while true; do
    read -p "This will build and upload to PyPI. Continue? [y/n]: " yn
    case $yn in
        [Yy]* ) update_version_in_pyproject; break;;
        [Nn]* ) exit;;
        * ) echo "Please answer yes or no.";;
    esac
done
