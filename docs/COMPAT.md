# Compatibility notes

## Injection matrix (Phase 2) — `tests/test_inject_targets.py`
Private Xvfb (no WM), samples `😄 👍🏽 🏳️‍🌈 👨‍👩‍👧` typed one `type_text()` call each, `key-delay-ms=8`.
CLIPBOARD and PRIMARY are pre-seeded with sentinels and compared byte-for-byte (`xclip -o`) afterwards.

| Target | Toolkit | Result | Time, 4 sequences |
|---|---|---|---|
| GtkTextView | GTK4 (4.14) | PASS | ~85 ms |
| GtkTextView | GTK3 | PASS | ~70 ms |
| QPlainTextEdit | Qt 5.15 (PyQt5) | PASS | ~70 ms |
| xterm (`-u8`) | Xt | PASS | ~70 ms |
| Alacritty | winit/X11 | PASS | ~70 ms |
| Firefox `<textarea>` | Gecko/GTK3 | PASS | ~70 ms |
| GTK4 text view on real GNOME Shell 46/mutter (X11 session) | GTK4 | PASS | — |
| Chromium / Electron | — | not tested (not installed on the dev host) | — |

Clipboard + primary: byte-identical in every run.

### Anomalies / design consequences
* **Qt drops keys if the keymap is restored right after typing.** Qt (and Chromium) rebuild their
  keymap from the server's *current* state when they get to the `MappingNotify`, so a keycode
  restored 5 ms after use resolves to `NoSymbol`; with immediate restore Qt lost 2 of 4 sequences and
  doubled another (reused keycodes). Fix: bindings stay for 0.5 s after the last insertion
  (`_Injector.RESTORE_AFTER`), are reused across calls, and each distinct code point gets one keycode
  for the whole text. Restoration is also forced on any exception and at interpreter exit.
* Spare keycodes are found by scanning for all-`NoSymbol` keycodes that are not modifiers; up to 32 are
  held at once. Texts with more distinct characters are typed in rounds with a 30 ms settle between.
* Held modifiers (Super from `Super+.`, Shift from Shift+Click) are fake-released before typing.

## Phase 3 — overlay behaviour (tests/test_overlay_session.py)

Run on a live X11 session (`tests/test_overlay_session.py`, needs a running `smile-panel --daemon`) and in an
isolated Xephyr (`tests/run_overlay_xephyr.sh [wm]`). Both use a GTK4 text sink as target and compare
CLIPBOARD/PRIMARY sentinels with `xclip -o`.

| Check | GNOME Shell (mutter, X11) | Openbox (Xephyr) |
|---|---|---|
| panel opens near pointer, 360x480, UTILITY/ABOVE/SKIP_* | pass | pass |
| 3 emoji clicks → 3 emoji typed, panel stays mapped | pass | pass |
| click inside panel (empty grid) keeps it open | pass | pass |
| click in other app closes it (XI2 raw button, no grab) | pass | pass |
| Escape / `--toggle` close it | pass | pass |
| search + Shift+Enter inserts first hit and closes | pass | pass |
| clipboard + primary byte-identical | pass | pass |

Anomalies found while testing:
* Reparenting WMs: the X input focus sits on a *child* of the client window, so "target is focused" walks
  the focus window's parent chain (`_focus_in`) instead of comparing it to the toplevel directly.
* GTK4 drops key events that arrive before it processed FocusIn; insertion therefore waits for both
  `_NET_ACTIVE_WINDOW` and `XGetInputFocus` to name the target (≤200 ms, then XSetInputFocus fallback).
* GtkText only emits `activate` for plain Enter; Shift+Enter is handled in the key controller.
* GTK4 creates hidden leader windows with the same title; test targets are picked by `WM_STATE`.

## Phase 4 — global hotkeys (`smile-panel --daemon`, tests/run_hotkeys_xephyr.sh)

`hotkey_x11.py` grabs Super+period and Super+semicolon on the root window with XGrabKey, once for each of
the 8 NumLock/CapsLock/ScrollLock combinations, on a background thread (own Xlib connection) that calls
`GLib.idle_add` to toggle the panel. Keymap changes (MappingNotify) re-grab. A grab refused with BadAccess
is logged with instructions and the other key still works.

| Desktop / WM | Super+. | Super+; | Lock-key variants | Notes |
|---|---|---|---|---|
| Openbox (Xephyr) | pass (built-in grab) | pass | pass (CapsLock, NumLock) | |
| Fluxbox (Xephyr) | pass (built-in grab) | pass | pass | |
| GNOME Shell / mutter, X11 | pass via GNOME custom shortcut → `smile-panel --toggle` | same (custom1) | n/a | mutter handles the key before our XGrabKey; the daemon's grab is harmless and never fires (checked with debug log), so no double toggle |
| IceWM (Xephyr) | **fails** | **fails** | – | IceWM takes an active keyboard grab when Super is pressed (`XGrabKeyboard` from another client returns AlreadyGrabbed), so no Super+key reaches any client. Bind `smile-panel --toggle` in `~/.icewm/keys`, e.g. `key "Super+period" smile-panel --toggle` |

Overlay behaviour (tests/run_overlay_xephyr.sh): openbox, fluxbox, icewm all pass the Phase 3 checks.

### Hotkey conflicts and how to resolve them
* **Another `smile-panel --daemon` or the old SMILE** holding Super+period → BadAccess message; stop it.
* **Flatpak SMILE (`it.mijorus.smile`)** — on this host it was bound through GNOME custom shortcut `custom0`
  (`flatpak run it.mijorus.smile`). Repointed to `~/.local/bin/smile-panel --toggle`; undo with
  `REVERT-GNOME-BINDING.sh`.
* **IBus emoji picker** — `org.freedesktop.ibus.panel.emoji hotkey` defaults to `['<Super>semicolon', '<Super>period']`.
  On IBus-driven desktops it holds the same keys. Disable with
  `gsettings set org.freedesktop.ibus.panel.emoji hotkey "[]"`.
* **GNOME Shell**: no built-in emoji shortcut under X11 beyond IBus's; Super+period/semicolon can be used with
  custom shortcuts as above (the shell, not our daemon, services them).
* **KDE/Plasma, XFCE, Cinnamon**: default configs don't bind Super+period/semicolon (not tested here); if a
  DE shortcut already uses them, remove it or use `smile-panel --toggle` from the DE's shortcut editor.
* When the DE/WM owns the shortcut, the daemon process is still required only for fast startup; the D-Bus
  service file starts it on demand.
