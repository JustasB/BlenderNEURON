#!/bin/bash

echo "Starting BlenderNEURON Docker container..."
container_id=$(docker run \
    -it \
    -v $(readlink -f ../):/BlenderNEURON \
    -p 5920:5920 \
    --detach \
    blenderneuron:2.0.0)

echo "Starting VNC client..."
sleep 1
while ! nc -z localhost 5920; do
  sleep 0.1 # sec
done

vinagre --vnc-scale :5920

echo "Stopping BlenderNEURON container"
docker stop -t 0 $container_id