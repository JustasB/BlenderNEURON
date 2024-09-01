# Start with a compiled NEURON + Python 3
FROM ubuntu:20.04

COPY *.py /
COPY link_addon.sh /
COPY start_vnc.sh /

# Install Blender dependencies
# RUN apt-get update && apt-get install -y libglu1 libxi6 libxrender1
RUN apt-get update && apt-get install -y curl libglu1-mesa libxi6 libxrender1 xvfb libxkbcommon-x11-0
RUN apt-get upgrade -y
RUN curl -L -o miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-py37_23.1.0-1-Linux-x86_64.sh
SHELL ["bash", "-c"]
RUN chmod +x miniconda.sh && ./miniconda.sh -b -p $HOME/miniconda && source $HOME/miniconda/bin/activate && conda init --all
ENV PATH=$PATH:/root/miniconda/bin/

RUN echo Getting Blender && \
    python install_blender.py && \
    rm blender.tar.xz



# Add blender to path
ENV PATH=$PATH:/blender/

# Make the package available to NEURON python
ENV PYTHONPATH=/BlenderNEURON

# Code coverage and debugging packages for NEURON python
RUN pip install pydevd-pycharm coverage neuron pydevd-pycharm sphinx sphinx_rtd_theme build twine

# Install packages for Blender python
RUN /blender/3.5/python/bin/python3.10 -m pip install coverage pydevd-pycharm
ENV COVERAGE_PROCESS_START=.coveragerc

#Expose port 5920 to view display using VNC Viewer
RUN apt-get update
RUN apt-get install -y x11vnc xvfb openbox menu
EXPOSE 5920
ENV DISPLAY=:0
ENV RESOLUTION=1280x760

## Link the addon and enable it in Blender, then start a VNC server with a window manager
CMD ["sh", "-c", "\
     ./link_addon.sh;\
     ./start_vnc.sh;\
"]
