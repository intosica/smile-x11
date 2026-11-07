"""Clipboard-free text injection through XTest.

Every code point is typed as keysym ``0x01000000 + cp`` (X11 "Unicode keysyms"),
temporarily bound to an *unused* keycode with ChangeKeyboardMapping, pressed and
released through XTest, and the mapping is restored afterwards. The clipboard and
the primary selection are never read or written.

Run ``python3 input_x11.py --self-test`` for the keymap-restoration check.
"""
import atexit
import logging
import threading
import time
from collections import OrderedDict
from typing import Optional

from Xlib import X, XK, display as xdisplay, error as xerror
from Xlib.ext import xtest

log = logging.getLogger('smile-panel.input')

UNICODE_KEYSYM_BASE = 0x01000000
MAX_POOL = 32  # max spare keycodes held at once; text with more distinct chars is typed in rounds

# Control characters that have a real key instead of a Unicode keysym
_SPECIAL = {'\n': XK.XK_Return, '\r': XK.XK_Return, '\t': XK.XK_Tab}

_conn: Optional[xdisplay.Display] = None


class InjectionError(Exception):
    """Text could not be typed. The clipboard is deliberately NOT used as a fallback."""


def _display() -> xdisplay.Display:
    global _conn
    if _conn is None:
        try:
            d = xdisplay.Display()
        except Exception as e:  # noqa
            raise InjectionError(f'cannot open X display: {e}') from e
        if not d.has_extension('XTEST'):
            d.close()
            raise InjectionError('the X server has no XTEST extension')
        _conn = d
    return _conn


def keysym_for(ch: str) -> int:
    return _SPECIAL.get(ch, UNICODE_KEYSYM_BASE + ord(ch))


def find_spare_keycodes(d: xdisplay.Display, limit: int = MAX_POOL) -> list[int]:
    """Keycodes whose every column is NoSymbol, i.e. nothing else depends on them."""
    lo, hi = d.display.info.min_keycode, d.display.info.max_keycode
    mapping = d.get_keyboard_mapping(lo, hi - lo + 1)
    mods = {kc for row in d.get_modifier_mapping() for kc in row if kc}
    spare = [lo + i for i, syms in enumerate(mapping) if not any(syms) and (lo + i) not in mods]
    return spare[::-1][:limit]  # high keycodes first: least likely to be touched by layouts


def release_held_modifiers(d: xdisplay.Display) -> None:
    """Fake-release every held modifier key (e.g. the Super of the invoking shortcut)
    so the target does not see Super+<char>."""
    pressed = d.query_keymap()
    for row in d.get_modifier_mapping():
        for kc in row:
            if kc and pressed[kc >> 3] & (1 << (kc & 7)):
                xtest.fake_input(d, X.KeyRelease, kc)
    d.sync()


class _Injector:
    """Keeps Unicode keysyms bound to spare keycodes for ``RESTORE_AFTER`` seconds after the last
    insertion, then restores the keymap (all-NoSymbol, which is what spare keycodes were).

    Restoring immediately breaks lazy clients: Qt/Chromium rebuild their keymap from the *server's
    current* state when they get around to MappingNotify, so a key typed 5 ms ago would resolve
    against the already-restored keymap and vanish. Bindings are also reused across calls, so rapid
    successive insertions cause no remap churn.
    """
    RESTORE_AFTER = 0.5

    def __init__(self):
        self.lock = threading.RLock()
        self.owned: 'OrderedDict[int, str]' = OrderedDict()  # keycode -> char, least recently used first
        self.timer: Optional[threading.Timer] = None
        atexit.register(self.restore)

    def restore(self) -> None:
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
            if not self.owned or _conn is None:
                self.owned.clear()
                return
            try:
                width = len(_conn.get_keyboard_mapping(_conn.display.info.min_keycode, 1)[0])
                for kc in self.owned:
                    _conn.change_keyboard_mapping(kc, [[X.NoSymbol] * width])
                _conn.sync()
            except Exception as e:  # noqa
                log.error('could not restore keymap: %s', e)
            finally:
                self.owned.clear()

    def _rounds(self, chars: list[str], capacity: int):
        """Split into contiguous runs that need at most ``capacity`` distinct keycodes."""
        run, seen = [], set()
        for ch in chars:
            if ch not in seen and len(seen) == capacity:
                yield run
                run, seen = [], set()
            run.append(ch)
            seen.add(ch)
        if run:
            yield run

    def type(self, text: str, delay: float) -> None:
        d = _display()
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
            try:
                free = find_spare_keycodes(d, MAX_POOL)
                capacity = len(free) + len(self.owned)
                if not capacity:
                    raise InjectionError('no unused keycode available for Unicode remapping')
                width = len(d.get_keyboard_mapping(d.display.info.min_keycode, 1)[0])  # keysyms per keycode
                release_held_modifiers(d)
                first_round = True
                for run in self._rounds(list(text), capacity):
                    by_char = {ch: kc for kc, ch in self.owned.items()}
                    remapped = False
                    for ch in dict.fromkeys(run):
                        if ch in by_char:
                            self.owned.move_to_end(by_char[ch])
                            continue
                        if free:
                            kc = free.pop()
                        else:  # evict the least recently used binding that this run does not need
                            kc = next(k for k, c in self.owned.items() if c not in run)
                            del self.owned[kc]
                        # same keysym in every column so a held Shift/AltGr cannot change it
                        d.change_keyboard_mapping(kc, [[keysym_for(ch)] * width])
                        self.owned[kc] = ch
                        by_char[ch] = kc
                        remapped = True
                    d.sync()
                    if remapped:
                        time.sleep(delay if first_round else max(delay, 0.03))  # clients process MappingNotify
                    first_round = False
                    for ch in run:
                        kc = by_char[ch]
                        xtest.fake_input(d, X.KeyPress, kc)
                        xtest.fake_input(d, X.KeyRelease, kc)
                    d.sync()
                    time.sleep(delay)
            except BaseException as e:  # guarantee restoration on any failure
                self.restore()
                if isinstance(e, InjectionError) or not isinstance(e, (xerror.XError, OSError)):
                    raise
                raise InjectionError(f'XTest injection failed: {e}') from e
            self.timer = threading.Timer(self.RESTORE_AFTER, self.restore)
            self.timer.daemon = True
            self.timer.start()


_injector = _Injector()


def type_text(text: str, delay_ms: float = 8.0) -> None:
    """Type ``text`` into the currently focused X window. Raises InjectionError."""
    if text:
        _injector.type(text, max(delay_ms, 0) / 1000.0)


def _self_test() -> None:
    d = _display()
    lo, hi = d.display.info.min_keycode, d.display.info.max_keycode
    before = d.get_keyboard_mapping(lo, hi - lo + 1)
    spare = find_spare_keycodes(d)
    assert spare, 'no spare keycodes'
    type_text('\U0001F604\U0001F44D\U0001F3FD\U0001F3F3\uFE0F\u200D\U0001F308' * 3)
    assert before != d.get_keyboard_mapping(lo, hi - lo + 1), 'bindings should persist briefly'
    time.sleep(_Injector.RESTORE_AFTER + 0.3)
    assert before == d.get_keyboard_mapping(lo, hi - lo + 1), 'keymap not restored'
    print(f'ok: keymap identical after typing; {len(spare)} spare keycodes')


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--self-test']:
        _self_test()
    elif len(sys.argv) > 1:
        type_text(' '.join(sys.argv[1:]))
