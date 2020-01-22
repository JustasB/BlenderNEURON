#xhost +local:root

docker run \
    -it \
    -v $(readlink -f ../):/BlenderNEURON \
    -p 5920:5920 \
    blenderneuron:2.0.0

#    -v /tmp/.X11-unix:/tmp/.X11-unix \
#    -e DISPLAY=$DISPLAY \
#    --device=/dev/dri:/dev/dri \
#xhost -local:root
