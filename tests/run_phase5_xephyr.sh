#!/bin/bash
# Phase 5 acceptance in an isolated Xephyr + openbox (never touches the real session).
set -u
cd "$(dirname "$0")/.."
D=:82
pkill Xephyr 2>/dev/null; sleep 0.3
Xephyr $D -screen 1280x800 -ac >/dev/null 2>&1 & XP=$!
sleep 1
export XDG_DATA_HOME=$(mktemp -d) XDG_CONFIG_HOME=$(mktemp -d) DISPLAY=$D \
  GSETTINGS_SCHEMA_DIR=$PWD/.dev/share/glib-2.0/schemas XDG_DATA_DIRS=$PWD/.dev/share:/usr/share \
  GTK_USE_PORTAL=0 NO_AT_BRIDGE=1 GTK_A11Y=none
dbus-run-session --config-file=tests/session.conf -- bash -c '
  openbox >/dev/null 2>&1 & WM=$!
  sleep 1
  .dev/bin/smile-panel --daemon >/tmp/sp-p5.log 2>&1 &
  SP=$!
  for i in $(seq 200); do grep -q "hotkeys active" /tmp/sp-p5.log && break; sleep 0.2; done
  /usr/bin/python3 -u tests/test_phase5.py
  RC=$?
  kill $SP $WM 2>/dev/null
  exit $RC'
RC=$?
kill $XP 2>/dev/null
exit $RC
