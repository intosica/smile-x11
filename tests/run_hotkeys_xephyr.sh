#!/bin/bash
# Phase 4: XGrabKey daemon in an isolated Xephyr + <WM>: Super+period, Super+semicolon, lock-key combos, BadAccess.
# usage: tests/run_hotkeys_xephyr.sh [wm] [display]   (default openbox :82)
set -u
cd "$(dirname "$0")/.."
WM=${1:-openbox}; D=${2:-:82}
Xephyr $D -screen 1024x700 -ac >/dev/null 2>&1 & XP=$!
sleep 1
export XDG_DATA_HOME=$(mktemp -d) DISPLAY=$D GSETTINGS_SCHEMA_DIR=$PWD/.dev/share/glib-2.0/schemas XDG_DATA_DIRS=$PWD/.dev/share:/usr/share GTK_USE_PORTAL=0 SMILE_DEBUG=1 NO_AT_BRIDGE=1
export WM
dbus-run-session --config-file=tests/session.conf -- bash -c '
  $WM >/dev/null 2>&1 &
  WMP=$!
  sleep 1
  vis() { xdotool search --onlyvisible --pid $SP 2>/dev/null | wc -l; }
  chk() { [ "$2" = "$3" ] && echo "PASS $1" || { echo "FAIL $1 (got $3, want $2)"; FAILS=1; }; }
  FAILS=0
  # 1. a foreign client holds Super+period -> daemon must report BadAccess and still grab Super+semicolon
  /usr/bin/python3 tests/hold_grab.py 60 >/tmp/hold.log 2>&1 &
  HOLD=$!; sleep 1
  .dev/bin/smile-panel --daemon >/tmp/sp-hk1.log 2>&1 &
  SP=$!
  for i in $(seq 300); do grep -q "hotkeys active\|cannot grab" /tmp/sp-hk1.log && break; sleep 0.2; done
  grep -q "cannot grab Super+period: BadAccess" /tmp/sp-hk1.log && echo "PASS BadAccess diagnostic" || { echo "FAIL BadAccess diagnostic"; FAILS=1; }
  xdotool key super+semicolon; sleep 0.8; chk "Super+; opens" 1 $(vis)
  xdotool key Escape; sleep 0.5; chk "Escape closes" 0 $(vis)
  kill $HOLD; wait $HOLD 2>/dev/null
  # 2. restart daemon with free keys: Super+period, with Caps/Num lock variants
  kill $SP; sleep 1
  .dev/bin/smile-panel --daemon >/tmp/sp-hk.log 2>&1 &
  SP=$!
  for i in $(seq 300); do grep -q "hotkeys active\|cannot grab" /tmp/sp-hk.log && break; sleep 0.2; done
  ! grep -q BadAccess /tmp/sp-hk.log && echo "PASS no BadAccess when free" || { echo "FAIL unexpected BadAccess"; FAILS=1; }
  xdotool key super+period; sleep 0.8; chk "Super+. opens" 1 $(vis)
  xdotool key super+period; sleep 0.5; chk "Super+. toggles closed" 0 $(vis)
  xdotool key Caps_Lock; sleep 0.2
  xdotool key super+period; sleep 0.8; chk "Super+. with CapsLock" 1 $(vis)
  xdotool key Escape; sleep 0.4
  xdotool key Caps_Lock; xdotool key Num_Lock; sleep 0.2
  xdotool key super+semicolon; sleep 0.8; chk "Super+; with NumLock toggled" 1 $(vis)
  xdotool key Escape; sleep 0.4; xdotool key Num_Lock
  kill $SP $WMP; exit $FAILS'
RC=$?
kill $XP
exit $RC
