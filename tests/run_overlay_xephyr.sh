#!/bin/bash
# Phase 3 acceptance in an isolated Xephyr + <WM> (default openbox): does not touch the real session.
# usage: tests/run_overlay_xephyr.sh [wm]   (needs `make install`-ed .dev prefix)
set -u
cd "$(dirname "$0")/.."
WM=${1:-openbox}; D=:81
Xephyr $D -screen 1280x800 -ac >/dev/null 2>&1 & XP=$!
sleep 1
export DISPLAY=$D GSETTINGS_SCHEMA_DIR=$PWD/.dev/share/glib-2.0/schemas XDG_DATA_DIRS=$PWD/.dev/share:/usr/share GTK_USE_PORTAL=0 SMILE_DEBUG=1 NO_AT_BRIDGE=1
dbus-run-session -- bash -c '
  '"$WM"' >/dev/null 2>&1 &
  sleep 1
  .dev/bin/smile-panel --daemon >/tmp/sp-xephyr.log 2>&1 &
  SP=$!
  for i in $(seq 100); do gdbus call --session --dest local.winpanel.Smile --object-path /local/winpanel/Smile --method org.freedesktop.DBus.Peer.Ping >/dev/null 2>&1 && break; sleep 0.2; done
  /usr/bin/python3 -u tests/test_overlay_session.py
  RC=$?; kill $SP; kill %1; exit $RC'
RC=$?
kill $XP
exit $RC
