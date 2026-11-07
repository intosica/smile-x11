"""Set CLIPBOARD to TEXT for N seconds, optionally also advertising an extra MIME type (e.g. a
password-manager flag) so the test can check that such clips are never recorded.
usage: set_clip.py TEXT [EXTRA_MIME] [SECONDS]
"""
import sys
import time

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk  # noqa

text, extra = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else '')
seconds = float(sys.argv[3]) if len(sys.argv) > 3 else 6

Gtk.init()
clipboard = Gdk.Display.get_default().get_clipboard()
providers = [Gdk.ContentProvider.new_for_bytes('text/plain;charset=utf-8', GLib.Bytes.new(text.encode()))]
if extra:
    providers.append(Gdk.ContentProvider.new_for_bytes(extra, GLib.Bytes.new(b'')))
clipboard.set_content(Gdk.ContentProvider.new_union(providers))

deadline = time.time() + seconds
ctx = GLib.MainContext.default()
while time.time() < deadline:      # keep serving the selection
    ctx.iteration(False)
    time.sleep(0.02)
