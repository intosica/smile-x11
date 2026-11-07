"""X11 glue for the overlay window: XID lookup, EWMH hints, show/hide/toggle.

GTK4 has no GTK_WINDOW_POPUP, move() or skip-taskbar API, so window-manager
interaction goes through python-xlib on the toplevel's XID.
"""
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('GdkX11', '4.0')

from gi.repository import Gdk, GdkX11, GLib  # noqa
from Xlib import X, display, protocol  # noqa

PANEL_SIZE = (360, 480)


class OverlayController:
    def __init__(self, window):
        self.window = window
        self.xdpy = display.Display()
        self._hinted = False
        window.set_decorated(False)
        window.set_resizable(False)
        window.set_default_size(*PANEL_SIZE)
        window.connect('map', self._on_map)
        window.connect('close-request', self._on_close_request)

    # -- X helpers -----------------------------------------------------------
    def xid(self) -> int:
        return GdkX11.X11Surface.get_xid(self.window.get_surface())

    def _atom(self, name):
        return self.xdpy.intern_atom(name)

    def _apply_hints(self):
        """Window type before map (WM reads it at map time); state via client message."""
        xwin = self.xdpy.create_resource_object('window', self.xid())
        xwin.change_property(self._atom('_NET_WM_WINDOW_TYPE'), self._atom('ATOM'), 32,
                             [self._atom('_NET_WM_WINDOW_TYPE_UTILITY')])
        self.xdpy.flush()

    def _send_wm_state(self):
        root = self.xdpy.screen().root
        for name in ('_NET_WM_STATE_ABOVE', '_NET_WM_STATE_SKIP_TASKBAR', '_NET_WM_STATE_SKIP_PAGER'):
            ev = protocol.event.ClientMessage(
                window=self.xdpy.create_resource_object('window', self.xid()),
                client_type=self._atom('_NET_WM_STATE'),
                data=(32, [1, self._atom(name), 0, 1, 0]))  # _NET_WM_STATE_ADD, source=application
            root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        self.xdpy.flush()

    # -- GTK signals -----------------------------------------------------------
    def _on_map(self, _w):
        self._send_wm_state()

    def _on_close_request(self, _w):
        self.hide()  # WM close (Alt+F4) hides; the resident instance keeps running
        return True

    # -- public API ------------------------------------------------------------
    def is_visible(self) -> bool:
        return self.window.get_visible()

    def prepare(self):
        """Realize the (hidden) window and set map-time hints so the first show is fast."""
        if not self._hinted:
            self.window.realize()
            self._apply_hints()
            self._hinted = True

    def show(self):
        self.prepare()
        self.window.present()

    def hide(self):
        self.window.set_visible(False)

    def toggle(self):
        self.hide() if self.is_visible() else self.show()
