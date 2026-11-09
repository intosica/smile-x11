"""Optional custom colour-emoji font (e.g. the iOS-style NotoColorEmoji.ttf) for the panel only.

The font is registered with fontconfig for this process (system fonts and other apps are untouched)
under the unique family ``Smile Emoji``, because a system "Noto Color Emoji" would otherwise win the
name match. A CSS provider then puts that family first on the emoji buttons.
This only changes how the panel *draws* emoji; the receiving app renders typed emoji with its own font.
"""
import ctypes
import os

import gi
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gdk, Gtk, PangoCairo

FAMILY = 'Smile Emoji'
_RULE = ('<fontconfig><match target="scan"><test name="file"><string>%s</string></test>'
         '<edit name="family" mode="assign"><string>' + FAMILY + '</string></edit></match></fontconfig>')
_CLASSES = ['emoji-button', 'emoji-button-lg', 'emoji-button-xl', 'emoji-button-xxl']

_fc = ctypes.CDLL('libfontconfig.so.1')
_fc.FcConfigParseAndLoadFromMemory.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
_fc.FcConfigGetCurrent.restype = ctypes.c_void_p
_fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
_fc.FcConfigAppFontClear.argtypes = [ctypes.c_void_p]

_pc = ctypes.CDLL('libpangoft2-1.0.so.0')
_pc.pango_fc_font_map_config_changed.argtypes = [ctypes.c_void_p]
_ptr = ctypes.pythonapi.PyCapsule_GetPointer
_ptr.restype = ctypes.c_void_p
_ptr.argtypes = [ctypes.py_object, ctypes.c_char_p]

_provider = Gtk.CssProvider()
_loaded: str | None = None


def _refresh_pango():
    # make an already running Pango font map re-read fontconfig so a change applies without restart
    _pc.pango_fc_font_map_config_changed(_ptr(PangoCairo.FontMap.get_default().__gpointer__, None))


def apply(path: str) -> bool:
    """Use the font file at ``path`` ('' = back to the system font). Returns False if it can't be loaded."""
    global _loaded
    display = Gdk.Display.get_default()
    Gtk.StyleContext.remove_provider_for_display(display, _provider)
    if not path:
        _loaded = None
        _refresh_pango()
        return True
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        return False
    if _loaded != path:
        _fc.FcConfigAppFontClear(None)
        _fc.FcConfigParseAndLoadFromMemory(_fc.FcConfigGetCurrent(), (_RULE % path).encode(), 1)
        if not _fc.FcConfigAppFontAddFile(None, path.encode()):
            return False
        _loaded = path
        _refresh_pango()
    _provider.load_from_string(', '.join('.' + c for c in _CLASSES) + ' { font-family: "%s", "Noto Color Emoji", emoji; }' % FAMILY)
    Gtk.StyleContext.add_provider_for_display(display, _provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
    return True
