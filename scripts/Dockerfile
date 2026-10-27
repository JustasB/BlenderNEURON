# Start with a compiled NEURON + Python 3
FROM ubuntu:24.04
ARG TARGETARCH

COPY *.py /
COPY link_addon.sh /
COPY start_vnc.sh /

# Install Blender dependencies
# RUN apt-get update && apt-get install -y libglu1 libxi6 libxrender1
RUN apt-get update && apt-get install -y curl zip libglu1-mesa libxi6 libxrender1 xvfb libxkbcommon-x11-0 openmpi-bin
# NEURON's MPI loader looks up the unversioned ``libmpi.so`` name, while the
# runtime package supplies only the versioned OpenMPI shared object.
RUN mpi_runtime_library=$(find /usr/lib -name 'libmpi.so.*' -print -quit) && \
    ln -s "$mpi_runtime_library" /usr/local/lib/libmpi.so && ldconfig
RUN apt-get upgrade -y
RUN case "$TARGETARCH" in \
        amd64) conda_arch=x86_64 ;; \
        arm64) conda_arch=aarch64 ;; \
        *) echo "Unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac && \
    curl -L -o miniconda.sh "https://repo.anaconda.com/miniconda/Miniconda3-py37_23.1.0-1-Linux-${conda_arch}.sh"
SHELL ["bash", "-c"]
RUN chmod +x miniconda.sh && ./miniconda.sh -b -p $HOME/miniconda && source $HOME/miniconda/bin/activate && conda init --all
ENV PATH=$PATH:/root/miniconda/bin/

RUN case "$TARGETARCH" in \
        amd64) python install_blender.py ;; \
        arm64) apt-get update && apt-get install -y blender python3-numpy python3-coverage ;; \
        *) echo "Unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac



# Add blender to path
ENV PATH=$PATH:/blender/

# Make the package available to NEURON python
ENV PYTHONPATH=/BlenderNEURON
ENV BLENDER_SYSTEM_SCRIPTS=/BlenderNEURON/blender_scripts

# Code coverage and debugging packages for NEURON python
RUN pip install pydevd-pycharm coverage neuron pydevd-pycharm sphinx sphinx_rtd_theme build twine

# Install packages for Blender python
RUN if [ "$TARGETARCH" = "amd64" ]; then \
        /blender/5.2/python/bin/python3.13 -m pip install coverage==7.12 pydevd-pycharm; \
    fi
ENV COVERAGE_PROCESS_START=.coveragerc

#Expose port 5920 to view display using VNC Viewer
RUN apt-get update
RUN apt-get install -y x11vnc xvfb openbox menu xterm mesa-utils
EXPOSE 5920
ENV DISPLAY=:0
ENV RESOLUTION=1280x760
ENV XDG_RUNTIME_DIR=/tmp/runtime-root
ENV GDK_BACKEND=x11
ENV QT_QPA_PLATFORM=xcb

## Link the addon and enable it in Blender, then start a VNC server with a window manager
CMD ["sh", "-c", "\
     ./link_addon.sh;\
     ./start_vnc.sh;\
"]
