import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Gio, Gdk, Adw, GLib  # noqa

from .utils import make_option
from .Picker import Picker
from .ShortcutsWindow import ShortcutsWindow
from .Settings import Settings
from .hotkey_x11 import HotkeyDaemon
from .lib import emoji_font

APP_ID = 'local.winpanel.Smile'


class SmilePanel(Adw.Application):
    """Single-instance (D-Bus unique name) resident application.

    Remote actions: `app.toggle`, `app.show`, `app.hide` (also reachable through
    org.freedesktop.Application.ActivateAction, which the launcher's fast path uses).
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.add_main_option_entries([
            make_option('toggle', description='Show/hide the panel (starts it if needed)'),
            make_option('daemon', description='Run resident in the background with the global hotkey'),
            make_option('version', description='Print version'),
        ])
        self.datadir = kwargs['datadir']
        self.version = kwargs['version']
        self.window: Picker | None = None
        self.hotkeys: HotkeyDaemon | None = None
        self.start_hidden = False

    def do_handle_local_options(self, options):
        if options.contains('version'):
            print(self.version)
            return 0

        self.register(None)
        if self.get_is_remote():
            if options.contains('daemon'):
                print('smile-panel is already running', file=sys.stderr)
            else:
                self.activate_action('toggle' if options.contains('toggle') else 'show', None)
            return 0

        self.start_hidden = options.contains('daemon')
        return -1

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.hold()  # stay resident while the panel is hidden

        css_provider = Gtk.CssProvider()
        css_provider.load_from_resource('/local/winpanel/Smile/assets/style.css')
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.settings = Gio.Settings.new(APP_ID)
        apply_font = lambda *_: emoji_font.apply(self.settings.get_string('emoji-font-file')) or print('smile-panel: cannot load emoji font', file=sys.stderr)
        apply_font()
        self.settings.connect('changed::emoji-font-file', apply_font)

        self.create_action('toggle', lambda *_: self.panel().overlay_ctl.toggle())
        self.create_action('show', lambda *_: self.panel().overlay_ctl.show())
        self.create_action('hide', lambda *_: self.panel().overlay_ctl.hide())
        self.create_action('preferences', lambda *_: Settings(APP_ID, transient_for=self.window).present())
        self.create_action('open_shortcuts', lambda *_: ShortcutsWindow().open())
        self.create_action('about', self.on_about_action)
        self.create_action('quit', lambda *_: self.quit())
        self.set_accels_for_action('app.quit', ['<Ctrl>q'])

    def panel(self) -> Picker:
        if not self.window:
            self.window = Picker(application=self)
        return self.window

    def do_activate(self):
        panel = self.panel()
        if self.start_hidden:
            panel.overlay_ctl.prepare()
            self.start_hidden = False  # only the very first activation of --daemon stays hidden
            self.hotkeys = HotkeyDaemon(lambda: self.activate_action('toggle', None))
            self.hotkeys.start()
        else:
            panel.overlay_ctl.show()

    def create_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect('activate', callback)
        self.add_action(action)

    def on_about_action(self, *_):
        about = Adw.AboutWindow(
            version=self.version,
            comments='Windows-style emoji panel for X11 — fork of SMILE',
            application_name='Smile Panel',
            application_icon=APP_ID,
            developer_name='Fork of SMILE by Lorenzo Paderi',
            copyright='(C) 2022 Lorenzo Paderi\n\nLocalized tags by milesj/emojibase, licensed under the MIT License',
            transient_for=self.window,
        )
        about.add_credit_section('Icon by', ['Roman Morozov'])
        about.present()


def main(version: str, datadir: str) -> int:
    return SmilePanel(version=version, datadir=datadir).run(sys.argv)
