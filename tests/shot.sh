#!/bin/bash
# Visual check helper: isolated Xephyr + openbox, opens the panel, saves /tmp/shot.png, optionally
# cycles tabs (arg: number of Tab presses) or types a query (arg: text after 'q:').
set -u
cd "$(dirname "$0")/.."
pkill Xephyr 2>/dev/null; sleep 0.3
Xephyr :81 -screen 480x620 -ac >/dev/null 2>&1 & XP=$!
sleep 1
export XDG_DATA_HOME=$(mktemp -d) DISPLAY=:81 GSETTINGS_SCHEMA_DIR=$PWD/.dev/share/glib-2.0/schemas \
  XDG_DATA_DIRS=$PWD/.dev/share:/usr/share GTK_USE_PORTAL=0 NO_AT_BRIDGE=1 GTK_A11Y=none
dbus-run-session --config-file=tests/session.conf -- bash -c '
  openbox >/dev/null 2>&1 & sleep 1
  .dev/bin/smile-panel --daemon >/tmp/shot-sp.log 2>&1 & sleep 2
  for i in $(seq 100); do grep -q "hotkeys active" /tmp/shot-sp.log && break; sleep 0.2; done
  xdotool mousemove 240 300
  .dev/bin/smile-panel --toggle; sleep 1
  case "${1:-}" in
    q:*) xdotool type --delay 40 "${1#q:}"; sleep 1 ;;
    [0-9]*) for i in $(seq "${1}"); do xdotool key Tab; sleep 0.4; done ;;
  esac
  sleep 0.4
  /usr/bin/python3 -c "
from PIL import ImageGrab
ImageGrab.grab(xdisplay=\":81\").save(\"/tmp/shot.png\")"
  pkill -f "[s]mile-panel --daemon"
' _ "${1:-}"
kill $XP 2>/dev/null
