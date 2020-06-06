# Start with a compiled NEURON + Python 3
FROM jbirgio/neuron:7.7

# Install Blender 2.79
RUN apt-get install -y curl


COPY *.py /
COPY link_addon.sh /
COPY start_vnc.sh /

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
