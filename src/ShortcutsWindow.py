import gi

gi.require_version('Gtk', '4.0')

from gi.repository import Gtk  # noqa


class ShortcutsWindow():
    def __init__(self):
        builder = Gtk.Builder()
        builder.add_from_resource('/local/winpanel/Smile/ui/shortcuts.ui')
        self.shortcut_window = builder.get_object('shortcuts')
        self.shortcut_window.set_default_size(600, 400)
        builder.get_object('shift-left-click-label').set_label(_('Insert the emoji and toggle keeping the panel open'))
        builder.get_object('left-click-label').set_label(_('Insert the emoji'))

    def open(self):
        self.shortcut_window.present()
