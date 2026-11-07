"""X11 glue for the overlay window.

GTK4 has no GTK_WINDOW_POPUP, no Gtk.Window.move() and no skip-taskbar API, so window-manager
interaction goes through python-xlib on the toplevel's XID:

* EWMH hints: _NET_WM_WINDOW_TYPE_UTILITY (pre-map), _NET_WM_STATE ABOVE/SKIP_TASKBAR/SKIP_PAGER.
* Positioning: AT-SPI caret (optional) -> pointer, clamped to the monitor work area.
* Target tracking: root PropertyNotify on _NET_ACTIVE_WINDOW (only while the panel is visible).
* Insertion: re-activate the target (_NET_ACTIVE_WINDOW, XSetInputFocus fallback), wait for it to be
  focused, type through XTest, give focus back to the panel. `_refocusing` masks those programmatic
  focus flips; GTK focus-out is never used to dismiss the panel.
* Outside-click dismissal: XInput2 XI_RawButtonPress on the root window. No pointer grab, so clicks
  reach the clicked application untouched.

The Xlib connection is read from the GLib main loop (no threads).
"""
import logging
import os
import time
from typing import Callable, Optional

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkX11', '4.0')

from gi.repository import Gdk, GdkX11, GLib, Gtk  # noqa
from Xlib import X, Xatom, display, error as xerror, protocol  # noqa
from Xlib.ext import xinput  # noqa

from . import input_x11

log = logging.getLogger('smile-panel.window')

GENERIC_EVENT = 35
PANEL_SIZE = (360, 480)
HIT_MARGIN = 4          # px of slack around the panel for "inside" tests (borders/shadow)
FOCUS_TIMEOUT = 0.2     # s to wait for the target to report focus
REFOCUS_GUARD_MS = 300  # how long programmatic focus changes are ignored after an insertion
SOURCE_PAGER = 2        # EWMH source indication "direct user action": accepted by focus-stealing prevention


class OverlayController:
    def __init__(self, window: Gtk.Window):
        self.window = window
        self.xdpy = display.Display()
        self.root = self.xdpy.screen().root
        self.target: Optional[int] = None       # last non-panel active window
        self._refocusing = False                # True while WE are moving focus around
        self._refocus_timer = 0
        self._hinted = False
        self._watch = 0
        self._xi_ok = False
        self.on_shown: Optional[Callable[[], None]] = None   # hooks installed by the Picker
        self.on_hidden: Optional[Callable[[], None]] = None
        self.atoms: dict[str, int] = {}

        window.set_decorated(False)
        window.set_resizable(False)
        window.set_default_size(*PANEL_SIZE)
        window.connect('map', self._on_map)
        window.connect('unmap', self._on_unmap)
        window.connect('close-request', self._on_close_request)

    # -- X helpers -----------------------------------------------------------------------------
    def xid(self) -> int:
        return GdkX11.X11Surface.get_xid(self.window.get_surface())

    def atom(self, name: str) -> int:
        if name not in self.atoms:
            self.atoms[name] = self.xdpy.intern_atom(name)
        return self.atoms[name]

    def _win(self, xid: int):
        return self.xdpy.create_resource_object('window', xid)

    def _prop(self, win, name: str, ptype=X.AnyPropertyType, length=1024):
        try:
            p = win.get_full_property(self.atom(name), ptype, length)
        except xerror.XError:
            return None
        return p.value if p is not None else None

    def _apply_hints(self) -> None:
        """Window type must be set before the window is mapped (the WM reads it at map time)."""
        self._win(self.xid()).change_property(
            self.atom('_NET_WM_WINDOW_TYPE'), Xatom.ATOM, 32, [self.atom('_NET_WM_WINDOW_TYPE_UTILITY')])
        self.xdpy.flush()

    def _client_message(self, win: int, mtype: str, data: list[int]) -> None:
        ev = protocol.event.ClientMessage(window=self._win(win), client_type=self.atom(mtype), data=(32, data))
        self.root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        self.xdpy.flush()

    def _send_wm_state(self) -> None:
        for name in ('_NET_WM_STATE_ABOVE', '_NET_WM_STATE_SKIP_TASKBAR', '_NET_WM_STATE_SKIP_PAGER'):
            self._client_message(self.xid(), '_NET_WM_STATE', [1, self.atom(name), 0, 1, 0])  # _NET_WM_STATE_ADD

    def _pid(self, xid: int) -> Optional[int]:
        v = self._prop(self._win(xid), '_NET_WM_PID', Xatom.CARDINAL)
        return int(v[0]) if v is not None and len(v) else None

    def _is_own(self, xid: int) -> bool:
        return xid == self.xid() or self._pid(xid) == os.getpid()

    def _ewmh_active_supported(self) -> bool:
        sup = self._prop(self.root, '_NET_SUPPORTED', Xatom.ATOM, 4096)
        return sup is not None and self.atom('_NET_ACTIVE_WINDOW') in list(sup)

    # -- target window ----------------------------------------------------------------------------
    def _toplevel_of(self, xid: int) -> Optional[int]:
        """Climb from an arbitrary (child) window to the toplevel directly under the root."""
        try:
            win = self._win(xid)
            while True:
                parent = win.query_tree().parent
                if isinstance(parent, int) or parent.id == self.root.id:
                    return win.id
                win = parent
        except xerror.XError:
            return None

    def _current_active(self) -> Optional[int]:
        """The window the user is working in: _NET_ACTIVE_WINDOW, or the input focus without EWMH."""
        if self._ewmh_active_supported():
            v = self._prop(self.root, '_NET_ACTIVE_WINDOW', Xatom.WINDOW)
            return int(v[0]) if v is not None and len(v) and v[0] else None
        try:
            f = self.xdpy.get_input_focus().focus
        except xerror.XError:
            return None
        return None if isinstance(f, int) else self._toplevel_of(f.id)

    def _focus_in(self, xid: int) -> bool:
        """True if the X input focus is ``xid`` or one of its descendants (toolkits focus child windows)."""
        try:
            w = self.xdpy.get_input_focus().focus
            while not isinstance(w, int):
                if w.id == xid:
                    return True
                w = w.query_tree().parent
        except xerror.XError:
            pass
        return False

    def _window_exists(self, xid: int) -> bool:
        try:
            self._win(xid).get_attributes()
            return True
        except xerror.XError:
            return False

    def _fallback_target(self) -> Optional[int]:
        """Topmost normal window that is not ours (used when the tracked target is gone)."""
        v = self._prop(self.root, '_NET_CLIENT_LIST_STACKING', Xatom.WINDOW, 8192)
        bad = {self.atom(f'_NET_WM_WINDOW_TYPE_{t}') for t in ('DOCK', 'DESKTOP', 'SPLASH', 'MENU', 'TOOLTIP', 'NOTIFICATION')}
        for xid in reversed(list(v if v is not None else [])):
            if self._is_own(xid):
                continue
            types = self._prop(self._win(xid), '_NET_WM_WINDOW_TYPE', Xatom.ATOM)
            if types is not None and bad & set(types):
                continue
            return int(xid)
        return None

    def _remember_target(self) -> None:
        w = self._current_active()
        if w and not self._is_own(w):
            self.target = w

    # -- activation / insertion -----------------------------------------------------------------
    def _begin_refocus(self) -> None:
        self._refocusing = True
        if self._refocus_timer:
            GLib.source_remove(self._refocus_timer)
            self._refocus_timer = 0

    def _end_refocus_later(self) -> None:
        """Focus/property events caused by us arrive asynchronously: keep ignoring them briefly."""
        def clear():
            self._refocusing = False
            self._refocus_timer = 0
            return GLib.SOURCE_REMOVE
        self._refocus_timer = GLib.timeout_add(REFOCUS_GUARD_MS, clear)

    def _activate(self, xid: int) -> None:
        if self._ewmh_active_supported():
            self._client_message(xid, '_NET_ACTIVE_WINDOW', [SOURCE_PAGER, X.CurrentTime, 0, 0, 0])
        else:
            self._set_input_focus(xid)

    def _set_input_focus(self, xid: int) -> None:
        try:
            self._win(xid).set_input_focus(X.RevertToParent, X.CurrentTime)
            self.xdpy.sync()
        except xerror.XError as e:
            log.debug('XSetInputFocus failed: %s', e)

    def _wait_active(self, xid: int, timeout: float = FOCUS_TIMEOUT) -> bool:
        deadline = time.monotonic() + timeout
        while self._current_active() != xid:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.005)
        return True

    def insert_text(self, text: str, delay_ms: float) -> None:
        """Type ``text`` into the target app, then return keyboard focus to the panel."""
        self._begin_refocus()
        try:
            tgt = self.target
            if not tgt or not self._window_exists(tgt):
                tgt = self._fallback_target()
                if not tgt:
                    raise input_x11.InjectionError('no window to type into (the target window was closed)')
                log.info('target window gone, falling back to 0x%x', tgt)
                self.target = tgt
            self._activate(tgt)
            ok = self._wait_active(tgt)
            log.debug('target 0x%x focused=%s', tgt, ok)
            if not ok:
                log.debug('target 0x%x did not report focus in %.0f ms; forcing XSetInputFocus', tgt, FOCUS_TIMEOUT * 1000)
                self._set_input_focus(tgt)
                time.sleep(0.02)
            input_x11.type_text(text, delay_ms)
        finally:
            if self.is_visible():
                self._activate(self.xid())
            self._end_refocus_later()

    # -- positioning ---------------------------------------------------------------------------------
    def _caret_rect(self) -> Optional[tuple[int, int, int, int]]:
        try:
            from . import caret_atspi
        except ImportError:
            return None
        return caret_atspi.caret_rect()

    def _pointer(self) -> tuple[int, int]:
        p = self.root.query_pointer()
        return p.root_x, p.root_y

    def _work_area(self, x: int, y: int) -> tuple[int, int, int, int]:
        """Work area of the monitor containing (x, y): monitor rect ∩ _NET_WORKAREA (struts)."""
        mons = Gdk.Display.get_default().get_monitors()
        rects = []
        for i in range(mons.get_n_items()):
            m = mons.get_item(i)
            g, s = m.get_geometry(), m.get_scale_factor()
            rects.append((g.x * s, g.y * s, g.width * s, g.height * s))
        scr = self.xdpy.screen()
        mon = next((r for r in rects if r[0] <= x < r[0] + r[2] and r[1] <= y < r[1] + r[3]), None)
        if mon is None:
            mon = rects[0] if rects else (0, 0, scr.width_in_pixels, scr.height_in_pixels)
        wa = self._prop(self.root, '_NET_WORKAREA', Xatom.CARDINAL, 64)
        if wa is not None and len(wa) >= 4:
            ax, ay, aw, ah = (int(v) for v in wa[:4])
            l, t = max(mon[0], ax), max(mon[1], ay)
            r, b = min(mon[0] + mon[2], ax + aw), min(mon[1] + mon[3], ay + ah)
            if r > l and b > t:
                return l, t, r - l, b - t
        return mon

    def compute_position(self) -> tuple[int, int]:
        w, h = PANEL_SIZE
        caret = self._caret_rect()
        if caret:
            cx, cy, _cw, ch = caret
            x, y = cx, cy + ch + 4
            above = cy - h - 4
        else:
            px, py = self._pointer()
            x, y = px - 24, py + 16
            above = py - h - 16
        ax, ay, aw, ah = self._work_area(x, y)
        if y + h > ay + ah and above >= ay:
            y = above                      # no room below the caret/pointer: open above it
        x = min(max(x, ax), ax + aw - w)
        y = min(max(y, ay), ay + ah - h)
        return x, y

    def _move(self, x: int, y: int) -> None:
        self._win(self.xid()).configure(x=x, y=y)
        self.xdpy.flush()

    def _fix_position_after_map(self, x: int, y: int) -> bool:
        """The WM may place the window itself on map; correct it once via _NET_MOVERESIZE_WINDOW."""
        if self.is_visible():
            try:
                pos = self.root.translate_coords(self._win(self.xid()), 0, 0)
                cur = (pos.x, pos.y)
                log.debug('position after map: wanted %d,%d got %d,%d', x, y, *cur)
                if abs(cur[0] - x) > 2 or abs(cur[1] - y) > 2:
                    flags = 1 | (1 << 8) | (1 << 9) | (SOURCE_PAGER << 12)  # NorthWest gravity, x+y valid, pager source
                    self._client_message(self.xid(), '_NET_MOVERESIZE_WINDOW', [flags, x, y, 0, 0])
                    self._move(x, y)
            except xerror.XError:
                pass
        return GLib.SOURCE_REMOVE

    # -- outside-click dismissal / events ------------------------------------------------------------
    def _start_watch(self) -> None:
        if self._watch:
            return
        self.root.change_attributes(event_mask=X.PropertyChangeMask)
        try:
            self.xdpy.xinput_query_version()
            self.root.xinput_select_events([(xinput.AllMasterDevices, xinput.RawButtonPressMask)])
            self._xi_ok = True
        except Exception as e:  # noqa
            log.warning('XInput2 unavailable (%s): outside clicks will not close the panel', e)
        self.xdpy.flush()
        self._watch = GLib.io_add_watch(self.xdpy.fileno(), GLib.PRIORITY_DEFAULT, GLib.IO_IN, self._on_x_ready)

    def _stop_watch(self) -> None:
        if not self._watch:
            return
        GLib.source_remove(self._watch)
        self._watch = 0
        try:
            self.root.change_attributes(event_mask=0)
            if self._xi_ok:
                self.root.xinput_select_events([(xinput.AllMasterDevices, 0)])
            self.xdpy.flush()
        except xerror.XError:
            pass
        while self.xdpy.pending_events():   # drop whatever was queued
            self.xdpy.next_event()

    def _on_x_ready(self, _fd, _cond) -> bool:
        try:
            while self._watch and self.xdpy.pending_events():
                ev = self.xdpy.next_event()
                if ev.type == X.PropertyNotify and ev.window.id == self.root.id and ev.atom == self.atom('_NET_ACTIVE_WINDOW'):
                    if not self._refocusing:
                        self._remember_target()
                elif ev.type == GENERIC_EVENT and getattr(ev, 'evtype', None) == xinput.RawButtonPress:
                    self._on_raw_button_press()
        except Exception:  # noqa
            log.exception('X event handling failed')
        return GLib.SOURCE_CONTINUE

    def _own_rects(self) -> list[tuple[int, int, int, int]]:
        """Root-relative rectangles of every visible window of this app (panel, popovers, dialogs)."""
        rects = []
        for w in Gtk.Window.list_toplevels():
            surf = w.get_surface()
            if not w.get_visible() or not isinstance(surf, GdkX11.X11Surface):
                continue
            try:
                win = self._win(GdkX11.X11Surface.get_xid(surf))
                g = win.get_geometry()
                o = self.root.translate_coords(win, 0, 0)
                rects.append((o.x, o.y, g.width, g.height))
            except xerror.XError:
                continue
        return rects

    def _on_raw_button_press(self) -> None:
        px, py = self._pointer()      # raw events carry no window coordinates: ask for the pointer now
        log.debug('raw button press at %d,%d; own rects %s', px, py, self._own_rects())
        for x, y, w, h in self._own_rects():
            if x - HIT_MARGIN <= px < x + w + HIT_MARGIN and y - HIT_MARGIN <= py < y + h + HIT_MARGIN:
                return                # click inside the panel (or one of its popups): keep open
        log.debug('outside click at %d,%d: hiding', px, py)
        self.hide()

    # -- GTK signals -------------------------------------------------------------------------------------
    def _on_map(self, _w) -> None:
        self._send_wm_state()

    def _on_unmap(self, _w) -> None:
        """Every way of becoming hidden (our hide(), WM close/minimize, Esc) ends here."""
        self._stop_watch()
        if self.on_hidden:
            self.on_hidden()

    def _on_close_request(self, _w) -> bool:
        self.hide()  # WM close (Alt+F4) hides; the resident instance keeps running
        return True

    # -- public API ------------------------------------------------------------------------------------------
    def is_visible(self) -> bool:
        return self.window.get_visible()

    def prepare(self) -> None:
        """Realize the (hidden) window and set map-time hints so the first show is fast."""
        if not self._hinted:
            self.window.realize()
            self._apply_hints()
            self._hinted = True

    def show(self) -> None:
        self.prepare()
        if not self.is_visible():
            self._remember_target()
            x, y = self.compute_position()
            log.debug('show: pointer %s -> panel at %d,%d', self._pointer(), x, y)
            self._move(x, y)
            self._start_watch()
            self.window.present()
            GLib.timeout_add(60, self._fix_position_after_map, x, y)
        GLib.timeout_add(80, self._steal_focus)
        if self.on_shown:
            self.on_shown()

    def _steal_focus(self) -> bool:
        """present() carries no user timestamp when triggered over D-Bus: ask the WM explicitly."""
        if self.is_visible():
            self._begin_refocus()
            self._activate(self.xid())
            self._end_refocus_later()
        return GLib.SOURCE_REMOVE

    def hide(self) -> None:
        if self.is_visible():
            self.window.set_visible(False)  # -> 'unmap' -> _on_unmap

    def toggle(self) -> None:
        self.hide() if self.is_visible() else self.show()
