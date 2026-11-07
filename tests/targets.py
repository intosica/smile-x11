"""Tiny text-sink apps used by test_inject_targets.py: each writes its buffer to OUT on every change.
usage: targets.py {gtk4|gtk3|qt5} OUT
"""
import sys

kind, out = sys.argv[1], sys.argv[2]


def dump(text):
    with open(out, 'w', encoding='utf-8') as f:
        f.write(text)


if kind == 'gtk4':
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk, GLib
    app = Gtk.Application(application_id='local.winpanel.test.gtk4')

    def act(app):
        w = Gtk.ApplicationWindow(application=app, title='target-gtk4', default_width=400, default_height=200)
        tv = Gtk.TextView()
        tv.get_buffer().connect('changed', lambda b: dump(b.get_text(b.get_start_iter(), b.get_end_iter(), False)))
        w.set_child(tv)
        w.present()
        tv.grab_focus()
    app.connect('activate', act)
    app.run([])
elif kind == 'gtk3':
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    w = Gtk.Window(title='target-gtk3', default_width=400, default_height=200)
    tv = Gtk.TextView()
    tv.get_buffer().connect('changed', lambda b: dump(b.get_text(b.get_start_iter(), b.get_end_iter(), False)))
    w.add(tv)
    w.connect('destroy', Gtk.main_quit)
    w.show_all()
    Gtk.main()
elif kind == 'qt5':
    from PyQt5.QtWidgets import QApplication, QPlainTextEdit
    app = QApplication([])
    w = QPlainTextEdit()
    w.setWindowTitle('target-qt5')
    w.resize(400, 200)
    w.textChanged.connect(lambda: dump(w.toPlainText()))
    w.show()
    app.exec_()
