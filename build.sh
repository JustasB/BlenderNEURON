set -e

function install
{
    version=$(cat releases/latest.txt)

    echo Current version is: $version
    echo Type in the new version
    read version

    file=releases/BlenderNEURON-v$version.zip
    file_latest=releases/BlenderNEURON-latest.zip

    # Update version file
    echo $version > releases/latest.txt

    # Create addon zip
    zip -q -r $file blenderneuron -i '*.py' '*.json' '*.hoc'
    cp $file $file_latest

    # Create wheels and upload to pip
    rm -R dist/* || true

    /home/justas/anaconda2/envs/pb35/bin/python setup.py sdist bdist_wheel
    /home/justas/anaconda2/envs/p27/bin/python setup.py sdist bdist_wheel

    echo 'Built Addon .zip file:' $file

    echo Getting ready to upload to pypi
    /home/justas/anaconda2/envs/p27/bin/python -m twine upload dist/*

}

while true; do
    read -p "This will build and upload to pip. Continue?" yn
    case $yn in
        [Yy]* ) install; break;;
        [Nn]* ) exit;;
        * ) echo "Please answer yes or no.";;
    esac
done

