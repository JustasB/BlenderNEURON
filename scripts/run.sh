xhost +local:root

docker run \
    -it \
    -v $(readlink -f ../):/BlenderNEURON \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e DISPLAY=$DISPLAY \
    --device=/dev/dri:/dev/dri \
    blenderneuron:2.0.0

xhost -local:root
