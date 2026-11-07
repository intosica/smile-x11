# smile-panel — final report

Fork of SMILE 2.12.3 into a Windows `Win+.`-style emoji panel for X11. This report covers the
architecture decisions, measured performance, and what is known *not* to work.

## 1. Goal and what was kept

Goal: one global shortcut opens a transient overlay that already has keyboard focus, the picked emoji is
**typed into the previously focused application**, the panel stays open for continuous picking, and the
clipboard is never involved. X11 only (any WM), native meson install.

Kept from upstream: the emoji dataset and search/tag engine, the Libadwaita visual language, custom tags,
localized tags, preferences, skin-tone data, `.desktop`/gschema/D-Bus packaging.

Removed: clipboard copy + auto-paste (both the D-Bus `SendPaste` service and the xdotool variant),
multi-select buffer, Wayland/portal code paths, Flatpak manifest and the extension/update machinery,
"load hidden on startup"/"iconify on Esc"/"open on mouse position"/"mouse multi-select" options.

Added: XTest typing (`input_x11.py`), persistent overlay + focus management (`window_x11.py`), XGrabKey
daemon (`hotkey_x11.py`), Kaomoji/Symbols/Clipboard tabs, per-emoji skin-tone memory, Recents and
Frequently-used categories, `--toggle`/`--daemon` CLI.

## 2. Architecture decisions

### 2.1 Typing instead of pasting

The hard requirement — "never touch the clipboard" — rules out the `Ctrl+V` shortcut every picker uses.
XTest is the only mechanism that types arbitrary Unicode into *any* X11 client, including terminals
where IME-style commits are unavailable. There is no clipboard fallback even as a hidden option: if the
target is gone or the server rejects the remap, the user gets a notification and nothing is typed.

Unicode is typed by temporarily binding `0x01000000 + codepoint` to a spare keycode. The alternative
(IBus/fcitx commit APIs) would fail exactly where an emoji panel matters most — terminals and apps with
input methods disabled — and the alternative (X11 `XSendEvent`) is ignored by modern toolkits.

### 2.2 Keycode restoration is lazy, not immediate

The first implementation restored the original keymap right after the key release. Qt5 then lost 2 of 4
test sequences and doubled a third: Qt and Chromium rebuild their keymap from the server's *current*
state when they process the `MappingNotify`, so a keycode restored 5 ms after use resolves to
`NoSymbol`. Bindings now survive 0.5 s after the last insertion, are reused across calls per character,
and are restored on exceptions and at exit. That single change is the difference between "works in
GTK" and "works everywhere".

### 2.3 Overlay without GTK popup windows

GTK4 removed `GTK_WINDOW_POPUP` and `Gtk.Window.move()`. The overlay is a normal `Adw.ApplicationWindow`
whose XID is fetched from `Gdk.X11Surface`; EWMH hints (`_NET_WM_WINDOW_TYPE_UTILITY`, `_NET_WM_STATE`
`ABOVE|SKIP_TASKBAR|SKIP_PAGER`) and the position are set with Xlib after the surface exists, then
re-applied 60 ms after mapping because WMs move/size new windows.

Dismissal does **not** use GTK focus-out: every insertion deliberately moves focus to the target app, so
focus-out fires on each pick. Instead the panel listens for `XI_RawButtonPress` on the root window
(XInput2), compares the pointer position against the union of its own toplevels, and hides only for
outside presses. No pointer grab is taken, so clicks still reach the other applications.

Target tracking uses root `PropertyNotify` for `_NET_ACTIVE_WINDOW`; own windows (`_NET_WM_PID` == our
pid) are filtered out. Before each insertion the target is re-activated with a `_NET_ACTIVE_WINDOW`
client message (source 2, pager) and the panel waits up to 200 ms for the focus to land on it, falling
back to `XSetInputFocus` on the target's focused child (reparenting WMs leave the focus on a child, so
the check walks the parent chain).

### 2.4 Single instance and hotkeys

`--toggle` is a D-Bus round trip to the resident `Adw.Application` (`ActivateAction('toggle')` through
`org.freedesktop.Application`), with a pure-Python fallback that starts the app if D-Bus is unavailable.
The launcher (`bin/smile-panel.in`) prefers `gdbus call` over importing PyGObject, which cut the toggle
latency in half.

The optional `--daemon` owns `Super+period`/`Super+semicolon` through `XGrabKey` for all eight
NumLock/CapsLock/ScrollLock combinations, on a background Xlib connection whose events are forwarded with
`GLib.idle_add`. Where the desktop environment owns the shortcut (GNOME/mutter, IBus), the grab fails with
`BadAccess` and is reported per shortcut; the DE binding calls `--toggle`, the daemon is still useful for
fast startup via the D-Bus service file.

## 3. Performance

Measured on the dev host: X11 GNOME Shell 46 / mutter, Ryzen-class CPU, 2×1920×1080.

| Metric | Result |
|---|---|
| `smile-panel --toggle` → panel visible, pure PyGObject launcher | min 61 / median 88 / max 147 ms (30 runs) |
| same, `gdbus` fast path | min 31 / median 35 / max 86 ms (30 runs) |
| typing 4 emoji sequences (😄 👍🏽 🏳️‍🌈 👨‍👩‍👧) | 70–85 ms total, `key-delay-ms=8` |
| keycode remap → key events | 8 ms default, configurable |
| refocus target before insertion | 5–40 ms (bounded at 200 ms, then fallback) |
| memory / CPU while hidden | resident daemon, no polling, no timers |

Acceptance for Phase 1 (< 150 ms) is met with the fallback path and comfortably with the fast path.

## 4. Test coverage

| Harness | Environment | Result |
|---|---|---|
| `tests/run_inject_xvfb.sh` | private Xvfb, GTK4, GTK3, Qt5, xterm, alacritty, Firefox | pass, clipboard byte-identical |
| `tests/test_overlay_session.py` | live GNOME X11 session | pass |
| `tests/run_overlay_xephyr.sh [wm]` | Xephyr + openbox / fluxbox / icewm | pass |
| `tests/run_hotkeys_xephyr.sh [wm]` | Xephyr + openbox / fluxbox / icewm | pass (icewm needs its own binding) |
| `tests/run_phase5_xephyr.sh` | Xephyr + openbox, clipboard owner + fake password manager | 15/15 pass, twice |

Details, per-target anomalies and hotkey conflicts: [COMPAT.md](COMPAT.md).

## 5. Known limitations

1. **X11 only.** On Wayland XTest cannot inject into other clients; the launcher forces
   `GDK_BACKEND=x11`, which only works under XWayland-wrapped sessions for native X11 clients. Not fixed
   by design.
2. **Chromium / Electron untested.** Neither is installed on the dev host. The keymap-restore delay exists
   because of the same code path Chromium uses, and Qt (which shares the failure mode) passes, but this is
   inferred rather than measured.
3. **IceWM + Super.** IceWM takes an active keyboard grab when Super goes down, so no `Super+key`
   combination reaches clients at all. Use IceWM's own key file.
4. **GNOME/mutter and IBus own `Super+.`/`Super+;`.** The daemon cannot grab them there; the panel is
   started through the DE shortcut instead. This is the documented setup on the dev host.
5. **Caret positioning is untested on this host.** `src/caret_atspi.py` implements the optional AT-SPI
   lookup (15 % time budget, walks the accessibility tree for the focused accessible with a text
   interface, returns `getCharacterExtents(caretOffset)`), but `pyatspi` is not installed and the AT-SPI
   bus is not running here, so every measurement used the `XQueryPointer` fallback (panel opens slightly
   up-right of the cursor, clamped to the monitor work area).
6. **Multi-line clipboard entries** type a real `Return` per newline, so picking a multi-line snippet in
   a terminal submits each line. Single-line entries are the intended case.
7. **Terminals with bracketed paste / IME quirks** receive raw key events; emoji arrive as typed text
   (verified with xterm and alacritty), but a terminal that intercepts a keysym for its own shortcuts
   could swallow it.
8. **Clipboard history persistence is unencrypted** when explicitly enabled; it is off by default and
   labelled in Preferences. Sensitive entries are filtered by the KDE property and the vendor mime types
   listed in COMPAT.md; an application that marks secrets in some other proprietary way is not detected.
9. **One insertion at a time.** The XTest connection is process-global with lazy restore; concurrent
   insertions from two panels (impossible with a single instance) would interleave.
