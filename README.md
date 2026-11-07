# smile-panel — a Windows-style emoji panel for X11

A fork of [SMILE](https://github.com/mijorus/smile) (2.12.3) turned into a `Win+.`-style overlay for
X11 desktops: one global shortcut, a compact panel that takes search input immediately, and the picked
emoji **typed straight into the application you were using** — without ever touching the clipboard.

```
Super+.  ──▶  ┌──────────────────────────┐
              │ 🔍 search…               │   panel is a persistent overlay:
              ├──────────────────────────┤   pick, type, pick again — it stays open
              │  😀 😃 😄 😁 😆 😅 😂 🤣  │
              │  🥲 🥹 ☺️ 😊 😇 🙂 🙃 😉  │   Esc / click outside / Super+. closes it
              ├──────────────────────────┤
              │ Emoji Kaomoji Symbols 📋 │
              └──────────────────────────┘
                       ↓ XTest (no clipboard)
                  your focused app
```

## Why this fork

SMILE is a great picker, but it is built around *copy the emoji, then paste it* (clipboard or a
`Ctrl+V` sent to the app). This fork replaces that with X11-only input injection, adds persistent-overlay
behaviour, and drops the Wayland/Flatpak code paths that cannot do the same thing.

| Upstream SMILE | smile-panel |
|---|---|
| copies to the clipboard, then pastes | types with XTest, **clipboard untouched** |
| window closes after each pick | stays open for continuous picking (`keep-open-after-insert`) |
| GNOME/Wayland/Flatpak oriented | X11 only, any WM/DE, native meson install |
| Emoji only | Emoji, Kaomoji, Symbols, Clipboard history tabs |
| — | per-emoji skin-tone memory, Recents + Frequently used |

## Requirements

* X11/Xorg session (Wayland is not supported — XTest typing does not work there)
* Python 3.10+, PyGObject, GTK 4.10+, libadwaita 1.4+
* `python3-xlib` (XTest, XGrabKey, XInput2)
* `meson` + `ninja` to build
* optional: `xclip`/`xsel` (test scripts), `pyatspi` + a running AT-SPI bus (caret positioning; the panel
  falls back to the mouse pointer when it is missing)

Debian/Ubuntu:

```sh
sudo apt install meson ninja-build python3-gi python3-xlib \
     gir1.2-gtk-4.0 gir1.2-adw-1 libgtk-4-bin
# optional
sudo apt install python3-pyatspi at-spi2-core xclip
```

## Build and install

```sh
meson setup build --prefix="$HOME/.local"
meson install -C build
```

`--prefix` can be `/usr` for a system install. The launcher is a small shell script
(`bin/smile-panel`) that starts the Python package from `$prefix/share/smile-panel`.

## Usage

```sh
smile-panel --toggle     # show/hide the running instance (starts it if needed; this is what you bind)
smile-panel --daemon     # resident process that owns the built-in global hotkey
smile-panel              # same as --toggle, but opens the panel if the app is not running
smile-panel --version
```

`--toggle` is designed to be bound in your DE/WM shortcut editor. It talks to the running instance over
D-Bus (`local.winpanel.Smile`, `org.freedesktop.Application.ActivateAction`) and takes ~35–90 ms wall
clock (see [docs/REPORT.md](docs/REPORT.md)). A `.desktop` entry, a D-Bus service file and an XDG
autostart entry for `--daemon` are installed.

### Global hotkey

`smile-panel --daemon` grabs `Super+period` and `Super+semicolon` with `XGrabKey` for every
NumLock/CapsLock/ScrollLock combination. If another client already owns the key (GNOME Shell, IBus, the
Flatpak SMILE, another daemon) the grab fails with `BadAccess` and the daemon prints how to fix it:
stop the other owner or bind `smile-panel --toggle` in your desktop's shortcut editor instead.
See [docs/COMPAT.md](docs/COMPAT.md) for per-desktop notes (GNOME, openbox, fluxbox, icewm, IBus).

On GNOME the shell owns `Super+.` itself, so the recommended setup is a custom shortcut:

```sh
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/ command 'smile-panel --toggle'
```

## Keyboard and mouse

| Input | Action |
|---|---|
| type | searches the current tab, panel already has focus |
| `Down` | leaves the search bar, enters the result grid; arrows navigate |
| `Enter` / click | insert and **keep the panel open** |
| `Shift+Enter` / `Shift+click` | insert and **close** (inverts `keep-open-after-insert`) |
| `Tab` / `Shift+Tab` | next/previous tab (Emoji → Kaomoji → Symbols → Clipboard) |
| `Alt+←` / `Alt+→` | previous/next emoji category |
| `Alt+E` | skin-tone selector for the highlighted emoji |
| `Alt+T` / middle click | custom tags for the highlighted emoji |
| `Escape`, click outside, `Super+.` | close the panel |
| `Ctrl+Q` | quit the resident process |

## Clipboard policy

Inserting **never** writes to, reads from, or depends on `CLIPBOARD` or `PRIMARY`. There is no
copy-then-paste fallback, not even as an option: if injection fails you get a desktop notification with
the reason and your clipboard is left exactly as it was.

The **Clipboard** tab only *reads* the clipboard to build a history:

* in memory by default, never written to disk;
* `clipboard-persist` (off by default, labelled as unencrypted) stores it in
  `~/.local/share/smile-panel/clipboard_history.json` (mode 0600);
* entries flagged by password managers are skipped: the KDE `x-kde-passwordManagerHint` property on the
  selection owner as well as the `x-kde-passwordManagerHint`, `org.nspasteboard.ConcealedType`,
  `org.nspasteboard.TransientType`, `org.nspasteboard.AutoGeneratedType`, `x-gnome-secret` and
  `application/x-gnome-keyring-secret` mime types;
* picking an entry types its text with XTest — it is **not** written back to the clipboard.

## Configuration

`Preferences` (menu button → Preferences) covers the switches; the same values live in GSettings under
`local.winpanel.Smile`:

| Key | Default | Meaning |
|---|---|---|
| `keep-open-after-insert` | `true` | keep the panel open after inserting (`Shift+Enter` inverts it) |
| `key-delay-ms` | `8` | delay between keycode remap and XTest events (raise it if a target app drops characters) |
| `clipboard-history-enabled` | `true` | monitor the clipboard for the Clipboard tab |
| `clipboard-persist` | `false` | save the clipboard history to disk |
| `skintone-modifier`, `haircut-modifier` | `""` | default tone, overridden per emoji |
| `emoji-size-class`, `tags-locale`, `merge-english-tags`, `use-localized-tags` | — | appearance and tag search |

Per-emoji skin-tone choices and usage counters are kept in `~/.config/smile-panel/*.json`.

```sh
gsettings set local.winpanel.Smile keep-open-after-insert false
```

## How it works

* `src/input_x11.py` — Unicode typing through XTest. Each code point is temporarily bound to a spare,
  unused keycode (`ChangeKeyboardMapping`, keysym `0x01000000 + codepoint`), pressed and released, then
  the binding is restored in a `finally` block. Multi-codepoint emoji (ZWJ, skin tones, flags, U+FE0F)
  are typed code point by code point; held modifiers (e.g. the `Super` of the shortcut) are released
  first. Bindings survive 0.5 s after the last insertion because Qt/Chromium rebuild their keymap from
  the server's current state — restoring immediately made them drop characters.
* `src/window_x11.py` — the overlay. GTK4 has no popup windows, so the XID is taken from
  `Gdk.X11Surface` and the EWMH hints are applied with Xlib: `_NET_WM_WINDOW_TYPE_UTILITY`,
  `_NET_WM_STATE_ABOVE/SKIP_TASKBAR/SKIP_PAGER`, undecorated 360×480 at the pointer (clamped to
  `_NET_WORKAREA` and the monitor geometry). It tracks the last non-panel `_NET_ACTIVE_WINDOW`, refocuses
  the target via `_NET_ACTIVE_WINDOW` (then `XSetInputFocus`) before every insertion, guards the
  resulting focus changes with `self._refocusing`, and closes on an outside pointer press detected with
  XInput2 `XI_RawButtonPress` — no pointer grab, so other apps keep receiving input.
* `src/hotkey_x11.py` — `XGrabKey` on a background Xlib connection, events forwarded to the GTK loop with
  `GLib.idle_add`, `BadAccess` reported per shortcut.
* `src/main.py` — a single-instance `Adw.Application`; `--toggle` either activates the running instance
  over D-Bus or starts the panel.

## Tests and documents

Run from the source tree (`tests/`):

```sh
python3 tests/test_inject_targets.py   # Phase 2: Unicode injection into GTK3/4, Qt5, xterm, alacritty, Firefox
tests/run_overlay_xephyr.sh [wm]  # Phase 3: overlay behaviour in Xephyr + openbox/fluxbox/icewm
tests/run_hotkeys_xephyr.sh [wm]  # Phase 4: XGrabKey daemon
tests/run_phase5_xephyr.sh        # Phase 5: tabs, clipboard history, skintone memory, Shift+Enter
```

All of them compare `CLIPBOARD`/`PRIMARY` sentinels with `xclip -o` before and after. Results and
anomalies: [docs/COMPAT.md](docs/COMPAT.md). Architecture, benchmarks and known limits:
[docs/REPORT.md](docs/REPORT.md).

## License

GPL-3.0-or-later, like upstream SMILE. Original work © mijorus; X11 panel fork © the smile-panel
contributors.
