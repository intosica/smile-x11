#!/usr/bin/env bash
# smile-panel installer (X11 only, native meson install - no Flatpak).
#
#   ./install.sh                      # per-user install into ~/.local
#   PREFIX=/usr sudo -E ./install.sh  # system install (also pass SYSCONFDIR=/etc)
#   PYTHON=/usr/bin/python3 ./install.sh
#
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"
SYSCONFDIR="${SYSCONFDIR:-}"
PYTHON="${PYTHON:-/usr/bin/python3}"
BUILD="${BUILD:-build}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }
say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

command -v meson >/dev/null || die "meson not found - install it: sudo apt install meson ninja-build"
command -v ninja >/dev/null || die "ninja not found - install it: sudo apt install ninja-build"
[ -x "$PYTHON" ] || die "python interpreter '$PYTHON' not found (override with PYTHON=...)"

say "checking runtime dependencies with $PYTHON"
"$PYTHON" - <<'EOF' || die "missing Python modules (see README: python3-gi, python3-xlib)"
import sys
try:
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Gtk, Adw, Gdk, GLib
except Exception as e:
    sys.exit(f'  PyGObject / GTK4 / libadwaita: {e}')
try:
    import Xlib.display, Xlib.ext.xtest  # noqa
except Exception as e:
    sys.exit(f'  python-xlib (with XTest): {e}')
if Gdk.Display.get_default() is None:      # no display: can't query, assume fine
    pass
print('  PyGObject, GTK4, libadwaita, python-xlib: ok')
EOF

[ -n "${DISPLAY:-}" ] || say "warning: no DISPLAY - installing anyway, but smile-panel needs an X11 session"

say "configuring $BUILD (prefix: $PREFIX)"
opts=(-Dpython_path="$PYTHON")
[ -n "$SYSCONFDIR" ] && opts+=(-Dsysconfdir="$SYSCONFDIR")
if [ -d "$SRC/$BUILD" ]; then
  meson setup --reconfigure "$SRC/$BUILD" --prefix="$PREFIX" "${opts[@]}"
else
  meson setup "$SRC/$BUILD" --prefix="$PREFIX" "${opts[@]}"
fi
meson install -C "$SRC/$BUILD"

if [ "$PREFIX" = "$HOME/.local" ] || [ "$(readlink -f "$PREFIX")" = "$(readlink -f "$HOME/.local")" ]; then
  say "installing the autostart entry (starts the resident daemon, and with it the built-in Super+. grab)"
  mkdir -p "$HOME/.config/autostart"
  cp "$SRC/$BUILD/data/local.winpanel.Smile.autostart.desktop" \
     "$HOME/.config/autostart/local.winpanel.Smile.desktop"
  BIN="$PREFIX/bin/smile-panel"
else
  say "system install: the autostart entry is in $PREFIX/etc/xdg/autostart"
  BIN="$(command -v smile-panel || echo "$PREFIX/bin/smile-panel")"
fi

"$PREFIX/bin/smile-panel" --version >/dev/null 2>&1 || say "warning: $PREFIX/bin/smile-panel does not start (check $PYTHON and the modules above)"

cat <<EOF

$(say "installed smile-panel 3.0.0 -> $PREFIX")

Next steps:
  1. start the resident daemon (or log out and back in, the autostart entry does it):
       $PREFIX/bin/smile-panel --daemon &
  2. bind Super+period in your desktop to:
       $PREFIX/bin/smile-panel --toggle
     GNOME:
       gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/ name 'Emoji'
       gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/ binding '<Super>period'
       gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/ command '$PREFIX/bin/smile-panel --toggle'
     (add the same custom0 path to org.gnome.settings-daemon.plugins.media-keys custom-keybindings if it is empty)
  3. conflicts with Super+period: IBus emoji picker (org.freedesktop.ibus.panel.emoji hotkey),
     the Flatpak SMILE, or another daemon - see docs/COMPAT.md.

Typing goes through XTest: the clipboard and primary selection are never touched.
EOF
