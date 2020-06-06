# Start openbox window manager on vnc shell session start
echo 'openbox-session 2> /dev/null &' >> /root/.bashrc

# Start VNC server
x11vnc -nopw -create -rfbport 5920 -forever -geometry $RESOLUTION
