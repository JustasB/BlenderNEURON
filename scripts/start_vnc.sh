#!/bin/bash
set -e

export DISPLAY="${DISPLAY:-:0}"
RESOLUTION="${RESOLUTION:-1280x760}"
VNC_PASSWORD="${VNC_PASSWORD:-blender}"
XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-root}"

mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
export XDG_RUNTIME_DIR

Xvfb "$DISPLAY" -screen 0 "${RESOLUTION}x24" -nolisten tcp &
sleep 1

openbox-session >/tmp/openbox.log 2>&1 &
xterm -geometry 100x30+10+10 >/tmp/xterm.log 2>&1 &

x11vnc -passwd "$VNC_PASSWORD" -display "$DISPLAY" -rfbport 5920 -forever -shared
