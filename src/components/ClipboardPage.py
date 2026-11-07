"""Clipboard History tab. Strictly read-only towards the system clipboard: it only listens to
Gdk.Clipboard 'changed' and reads text; picking a row types it through XTest (never copied back)."""
from typing import Callable

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa

from ..lib.clipboard_history import ClipboardHistory, SENSITIVE_MIME_TYPES, clipboard_marked_sensitive

PREVIEW_CHARS = 200


class ClipboardPage(Gtk.Box):
    def __init__(self, history: ClipboardHistory, on_pick: Callable[[str, bool], None],
                 shift_held: Callable[[], bool]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.history, self.on_pick, self.shift_held = history, on_pick, shift_held
        self.enabled = True
        self.query = ''

        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, activate_on_single_click=True,
                                   css_classes=['clipboard-list'])
        self.listbox.connect('row-activated', lambda _l, row: row.pick(self.shift_held()))
        scrolled = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled.set_child(self.listbox)

        self.tip = Gtk.Label(justify=Gtk.Justification.CENTER, css_classes=['dim-label'], vexpand=True,
                             visible=False, wrap=True, margin_start=20, margin_end=20)
        overlay = Gtk.Overlay(child=scrolled)
        overlay.add_overlay(self.tip)
        self.append(overlay)

        bar = Gtk.Box(name='emoji_categories_box', margin_start=8, margin_end=8)
        self.status = Gtk.Label(hexpand=True, xalign=0, css_classes=['dim-label', 'caption'], ellipsize=Pango.EllipsizeMode.END)
        clear = Gtk.Button(icon_name='edit-clear-all-symbolic', tooltip_text=_('Clear unpinned entries'), css_classes=['flat'])
        clear.connect('clicked', lambda _b: (self.history.clear_unpinned(), self.refresh()))
        bar.append(self.status)
        bar.append(clear)
        self.append(bar)

        self.clipboard = Gdk.Display.get_default().get_clipboard()
        self.clipboard.connect('changed', self._on_clipboard_changed)
        self._read_current()   # whatever is on the clipboard right now
        self.refresh()

    # -- monitoring (read-only) --------------------------------------------------------------------
    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        if enabled:
            self._read_current()
        self.refresh()

    def _on_clipboard_changed(self, clipboard: Gdk.Clipboard):
        if clipboard.is_local():       # our own writes (e.g. a text entry copy) are not history
            return
        self._read_current()

    def _read_current(self):
        if not self.enabled:
            return
        if clipboard_marked_sensitive():
            return                     # KDE-style password manager flag: never record it
        formats = self.clipboard.get_formats()
        if any(formats.contain_mime_type(m) for m in SENSITIVE_MIME_TYPES):
            return                     # apps that advertise the flag as a mime type
        if formats.to_string() and not formats.contain_mime_type('text/plain'):
            return                     # image/file-only clip: nothing to record
        # formats can still be empty right after 'changed' (X11 resolves targets asynchronously) -
        # the read below asks the owner directly, so it works either way
        self.clipboard.read_text_async(None, self._on_text)

    def _on_text(self, clipboard: Gdk.Clipboard, result: Gio.AsyncResult):
        try:
            text = clipboard.read_text_finish(result)
        except GLib.Error:
            return
        if text and self.history.add(text):
            self.refresh()

    # -- UI ---------------------------------------------------------------------------------------------------
    def refresh(self):
        while (row := self.listbox.get_first_child()) is not None:
            self.listbox.remove(row)
        q = self.query.lower()
        entries = [e for e in self.history.ordered() if q in e['text'].lower()]
        for entry in entries:
            self.listbox.append(self._make_row(entry))
        total = len(self.history.entries)
        self.status.set_text(_('{n} entries').format(n=total) + (_(' · saved to disk') if self.history.persist else ''))
        if not self.enabled:
            self.tip.set_text(_('Clipboard history is turned off in Preferences.'))
        elif not entries:
            self.tip.set_text(_('Nothing found.') if q else _('Text you copy appears here.\nPick an entry to type it.'))
        self.tip.set_visible(not entries)

    def _make_row(self, entry: dict) -> Gtk.ListBoxRow:
        text = entry['text']
        shown = ' '.join(text[:PREVIEW_CHARS].split()) or text[:PREVIEW_CHARS]
        box = Gtk.Box(spacing=4, margin_start=6, margin_end=2, margin_top=2, margin_bottom=2)
        label = Gtk.Label(label=shown, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END, lines=2, wrap=True,
                          wrap_mode=Pango.WrapMode.WORD_CHAR, tooltip_text=text[:1000])
        pin = Gtk.ToggleButton(label='📌', active=entry['pinned'], css_classes=['flat', 'clipboard-pin'],
                               tooltip_text=_('Pin (keeps the entry; Ctrl+P)'), valign=Gtk.Align.CENTER)
        pin.connect('toggled', lambda _b: self._toggle_pin(text))
        delete = Gtk.Button(icon_name='edit-delete-symbolic', css_classes=['flat'], tooltip_text=_('Remove (Delete)'),
                            valign=Gtk.Align.CENTER)
        delete.connect('clicked', lambda _b: self._remove(text))
        for w in (label, pin, delete):
            box.append(w)
        row = Gtk.ListBoxRow(child=box)
        row.pick_text = text
        row.pick = lambda invert, t=text: self.on_pick(t, invert)
        row.toggle_pin = lambda t=text: self._toggle_pin(t)
        row.remove_entry = lambda t=text: self._remove(t)
        return row

    def _toggle_pin(self, text: str):
        self.history.toggle_pin(text)
        GLib.idle_add(self.refresh)

    def _remove(self, text: str):
        self.history.remove(text)
        self.refresh()

    def set_filter(self, query: str):
        self.query = query.strip()
        self.refresh()

    def first_text(self):
        row = self.listbox.get_row_at_index(0)
        return row.pick_text if row else None

    def pick_first(self, invert: bool) -> bool:
        row = self.listbox.get_row_at_index(0)
        if row:
            row.pick(invert)
        return row is not None

    def focus_first(self):
        row = self.listbox.get_row_at_index(0)
        if row:
            row.grab_focus()
