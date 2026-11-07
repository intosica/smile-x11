"""Global hotkeys via XGrabKey: Super+period and Super+semicolon.

A background thread owns its own Xlib connection, grabs each key on the root window once per
NumLock/CapsLock/ScrollLock combination (X matches grabs on the exact modifier state), and hands
KeyPress events to the GLib main loop through ``GLib.idle_add``. Only one client can hold a given
grab: if another program (GNOME's media-keys, IBus' emoji hotkey, a second daemon...) already has it,
the server answers BadAccess and we say so instead of failing silently.
"""
import itertools
import logging
import os
import select
import threading
from typing import Callable

from gi.repository import GLib
from Xlib import X, XK, display, error as xerror

log = logging.getLogger('smile-panel.hotkey')

KEYS = (('period', 'Super+period'), ('semicolon', 'Super+semicolon'))
HINT = ('Stop the other grabber (e.g. a running `smile-panel --daemon`, the old SMILE, '
        'IBus `org.freedesktop.ibus.panel.emoji` hotkey, or a DE shortcut for Super+period), '
        'or leave this daemon alone and bind `smile-panel --toggle` in your WM/DE shortcuts.')


class HotkeyDaemon:
    def __init__(self, on_trigger: Callable[[], None]):
        self.on_trigger = on_trigger
        self.failed: list[str] = []
        self._thread: threading.Thread | None = None
        self._stop_r, self._stop_w = os.pipe()
        self._ready = threading.Event()

    def start(self, timeout: float = 2.0) -> list[str]:
        """Start grabbing; returns the names of keys that could not be grabbed."""
        self._thread = threading.Thread(target=self._run, name='hotkeys', daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        return self.failed

    def stop(self) -> None:
        os.write(self._stop_w, b'x')
        if self._thread:
            self._thread.join(1)

    # -- worker thread --------------------------------------------------------------------------------
    @staticmethod
    def _lock_masks(d) -> list[int]:
        """All subsets of {CapsLock, NumLock, ScrollLock} as modifier masks."""
        singles = [X.LockMask]
        for name in ('Num_Lock', 'Scroll_Lock'):
            kc = d.keysym_to_keycode(XK.string_to_keysym(name))
            for i, codes in enumerate(d.get_modifier_mapping()):
                if kc and kc in codes:
                    singles.append(1 << i)
                    break
        masks = set()
        for r in range(len(singles) + 1):
            for combo in itertools.combinations(singles, r):
                masks.add(sum(combo))
        return sorted(masks)

    def _grab_all(self, d, root, locks) -> list[str]:
        failed = []
        for keyname, label in KEYS:
            kc = d.keysym_to_keycode(XK.string_to_keysym(keyname))
            if not kc:
                failed.append(label)
                log.warning('no keycode for %s in this keyboard layout; cannot grab %s', keyname, label)
                continue
            errors = []
            for m in locks:
                root.grab_key(kc, X.Mod4Mask | m, False, X.GrabModeAsync, X.GrabModeAsync,
                              onerror=lambda e, _req, errors=errors: errors.append(e))
            d.sync()
            if any(isinstance(e, xerror.BadAccess) for e in errors):
                failed.append(label)
                log.warning('cannot grab %s: BadAccess, another client already holds it. %s', label, HINT)
                for m in locks:     # drop the partial grabs of this key
                    root.ungrab_key(kc, X.Mod4Mask | m)
                d.sync()
        return failed

    def _run(self) -> None:
        try:
            d = display.Display()
            root = d.screen().root
            locks = self._lock_masks(d)
            self.failed = self._grab_all(d, root, locks)
        except Exception:  # noqa
            log.exception('hotkey thread failed to start')
            self.failed = [label for _, label in KEYS]
            self._ready.set()
            return
        if len(self.failed) < len(KEYS):
            log.info('hotkeys active: %s', ', '.join(l for _, l in KEYS if l not in self.failed))
        self._ready.set()
        if len(self.failed) == len(KEYS):
            return
        grabbed = {d.keysym_to_keycode(XK.string_to_keysym(k)) for k, l in KEYS if l not in self.failed}
        fd = d.fileno()
        while True:
            while d.pending_events():
                ev = d.next_event()
                if ev.type == X.KeyPress and ev.detail in grabbed:
                    log.debug('hotkey keycode %d state 0x%x', ev.detail, ev.state)
                    GLib.idle_add(self._fire)
                elif ev.type == X.MappingNotify and ev.request == X.MappingKeyboard:
                    for kc in grabbed:   # layout changed: keycodes may differ now
                        for m in locks:
                            root.ungrab_key(kc, X.Mod4Mask | m)
                    d.refresh_keyboard_mapping(ev)
                    self.failed = self._grab_all(d, root, locks)
                    grabbed = {d.keysym_to_keycode(XK.string_to_keysym(k)) for k, l in KEYS if l not in self.failed}
            r, _, _ = select.select([fd, self._stop_r], [], [])
            if self._stop_r in r:
                break
        for kc in grabbed:
            for m in locks:
                root.ungrab_key(kc, X.Mod4Mask | m)
        d.close()

    def _fire(self) -> bool:
        self.on_trigger()
        return GLib.SOURCE_REMOVE
