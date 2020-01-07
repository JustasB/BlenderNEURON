# Start with a compiled NEURON + Python 3.7
FROM neuron:7.7

# Install Blender 2.79
RUN apt-get install -y curl


COPY *.py /
RUN echo Getting Blender && \
    python install_blender.py

RUN rm blender.tar.bz2

# Install Blender dependencies
RUN apt-get install -y libglu1 libxi6 libxrender1

# Add blender to path
ENV PATH=$PATH:/blender/

# Make the package available to NEURON python
ENV PYTHONPATH=/BlenderNEURON

# Code coverage and debugging packages for NEURON python
RUN pip install pydevd coverage

# Install pip and some packages for Blender python
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
    /blender/2.79/python/bin/python3.5m get-pip.py && \
    rm get-pip.py && \
    /blender/2.79/python/bin/pip install coverage pydevd

ENV COVERAGE_PROCESS_START=.coveragerc

# Link the addon and enable it in Blender
ENTRYPOINT ln -s /BlenderNEURON/blenderneuron /blender/2.79/scripts/addons/blenderneuron && \
    blender/blender --python enable_addon.py --background -noaudio && \
    /bin/bash

# cd /BlenderNEURON && coverage run tests/test_coverage.py; rm -r htmlcov; coverage combine; coverage html; coverage report;




