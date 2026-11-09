# Screenshot protocol (for agents and contributors)

Never screenshot the user's real desktop. `tests/screenshots.py` runs the panel in an isolated
Xephyr + openbox + private D-Bus session with a throw-away `XDG_*` tree and keyfile GSettings, so the
user's session, settings and clipboard are untouched.

## 1. Dev install (once, and after every source change)

```sh
meson setup /tmp/sp-build --prefix="$PWD/.dev"   # only the first time
meson install -C /tmp/sp-build
glib-compile-schemas .dev/share/glib-2.0/schemas
```

## 2. Take screenshots

```sh
/usr/bin/python3 tests/screenshots.py [--font FILE.ttf] [--out DIR] [scenario ...]
```

* use the **system** python (needs `python3-pil`, `Xephyr`, `openbox`, `xdotool`, `dbus-run-session`);
* no scenario = all; one `name path` line is printed per PNG, exit code 1 if any scenario failed;
* images are cropped to the window, default output `docs/screenshots/`;
* `--font` sets the `emoji-font-file` setting first (e.g. the iOS `NotoColorEmoji.ttf`) — put those
  shots in a separate `--out` directory (`docs/screenshots/ios/`).

Scenarios: `emoji`, `search` (query `heart`), `kaomoji`, `symbols`, `clipboard`, `preferences`,
`preferences-font` (Preferences scrolled to the Emoji font row) and `new-<word>` which searches one of
the Unicode 16/17 emoji (`fingerprint orca trombone harp leafless root vegetable landslide distorted bags`).
Add a scenario by adding a line to `SCENARIOS` in `tests/screenshots.py`
(steps: `type`, `key`, `pref`, `scroll`).

## 3. Check them

Open each PNG (an agent: with the image `read` tool) before committing. Tofu boxes showing a hex code
(`1F\nACD`) instead of a picture mean the font lacks that emoji — expected for `new-*` with the system
font, a bug with `--font` pointing at a font that has them.

## 4. Rules

* Keep PNGs small (panel-sized crops, no full-screen grabs); do not commit fonts.
* Regenerate only the shots affected by your change, and mention which in the commit message.
* The panel needs `GDK_BACKEND=x11`; the `libEGL ... DRI3` warnings in Xephyr are harmless.
* Debugging a hang: panel log is `/tmp/screenshots-panel.log`.
