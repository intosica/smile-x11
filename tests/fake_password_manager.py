"""Own CLIPBOARD the way password managers do: serve the text but flag the selection with the
x-kde-passwordManagerHint property on the owner window, so clipboard managers can skip it.
usage: fake_password_manager.py TEXT [SECONDS]
"""
import sys
import time

import Xlib.display
import Xlib.X
import Xlib.Xatom
from Xlib.protocol import event

text = sys.argv[1].encode()
seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 60

d = Xlib.display.Display()
root = d.screen().root
atom = d.intern_atom
CLIPBOARD, UTF8, TEXT, TARGETS = atom('CLIPBOARD'), atom('UTF8_STRING'), atom('text/plain;charset=utf-8'), atom('TARGETS')
HINT = atom('x-kde-passwordManagerHint')

win = root.create_window(0, 0, 1, 1, 0, d.screen().root_depth, Xlib.X.InputOutput, Xlib.X.CopyFromParent)
win.change_property(HINT, atom('STRING'), 8, b'secret')    # the password-manager marker
win.set_selection_owner(CLIPBOARD, Xlib.X.CurrentTime)
d.flush()

deadline = time.time() + seconds
while time.time() < deadline:
    while d.pending_events():
        e = d.next_event()
        if e.type != Xlib.X.SelectionRequest:
            continue
        prop = e.property or e.target
        ok = True
        if e.target == TARGETS:
            win.change_property(prop, Xlib.Xatom.ATOM, 32, [TARGETS, UTF8, TEXT, HINT])
        elif e.target in (UTF8, TEXT):
            win.change_property(prop, e.target, 8, text)
        else:
            ok = False
        notify = event.SelectionNotify(time=e.time, requestor=e.requestor, selection=e.selection,
                                      target=e.target, property=prop if ok else Xlib.X.NONE)
        e.requestor.send_event(notify)
        d.flush()
    time.sleep(0.01)
