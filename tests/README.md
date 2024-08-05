Under Construction...

# Unit Test Files
This folder contains unit tests.  
Tests are run automatically using a Circle CI pipeline.

Tests can also be run locally on your device to test functions when updating add-on. Below are the requirements for that.

## Running locally
### Requirements:
- Python 3.7
- Blender in PATH ('Blender' command should work)
    - Instructions by OS: https://docs.blender.org/manual/en/latest/advanced/command_line/index.html

- NEURON installed
- BlenderNEURON installed
- Blender installed with BlenderNEURON add-on
- coverage installed

### Instructions:
- Download repository
- In terminal:
- `cd BlenderNEURON`
- `sh test.sh`  

This script also checks code coverage.  
During test execution you should see movement within the Blender window. Printed messages
are normal. At the end there should be coverage table, and above it it should say
`Ran N tests in YY.ZZs`. An `OK` indicates all unit tests ran successfully.

### To run individual files:
- `python tests/filename.py`
### To run single test in file:
- `python tests/filename.py classname.functionname`
