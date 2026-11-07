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
