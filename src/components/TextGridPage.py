"""Tab page for plain-text pickables (kaomoji, symbols): group bar + searchable FlowBox."""
from typing import Callable

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Pango  # noqa

from ..lib.emoji_history import get_history

RECENT = 'recent'
RECENT_LIMIT = 30


class TextGridPage(Gtk.Box):
    def __init__(self, groups: dict[str, list[tuple[str, str]]], group_labels: dict[str, str],
                 history_file: str, columns: int, on_pick: Callable[[str, bool, str], None],
                 shift_held: Callable[[], bool], empty_recent_text: str):
        """groups: name -> [(text, search tags)]. on_pick(text, invert_close, history_file)."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        # a group is either a string of characters or a list of (text, search tags)
        groups = {name: [(i, '') if isinstance(i, str) else tuple(i) for i in items] for name, items in groups.items()}
        self.groups, self.history_file, self.on_pick, self.shift_held = groups, history_file, on_pick, shift_held
        self.query = ''
        self.group = next(iter(groups))
        self.tags = {text: tags for items in groups.values() for text, tags in items}

        self.flow = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE, homogeneous=True, activate_on_single_click=True,
            min_children_per_line=columns, max_children_per_line=columns, valign=Gtk.Align.START,
            row_spacing=2, column_spacing=2, margin_start=4, margin_end=4,
        )
        self.flow.connect('child-activated', lambda _f, child: child.pick(self.shift_held()))
        scrolled = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled.set_child(self.flow)

        self.tip = Gtk.Label(label=empty_recent_text, css_classes=['dim-label'], justify=Gtk.Justification.CENTER,
                             vexpand=True, visible=False)
        overlay = Gtk.Overlay(child=scrolled)
        overlay.add_overlay(self.tip)
        self.append(overlay)

        bar = Gtk.Box(halign=Gtk.Align.CENTER, hexpand=True, name='emoji_categories_box')
        self.group_buttons: dict[str, Gtk.Button] = {}
        for name in [RECENT, *groups]:
            b = Gtk.Button(label=group_labels[name], tooltip_text=name.capitalize(), valign=Gtk.Align.CENTER)
            b.connect('clicked', lambda _b, n=name: self.set_group(n))
            bar.append(b)
            self.group_buttons[name] = b
        self.append(bar)
        self.set_group(self.group)

    def set_group(self, name: str):
        self.group = name
        for n, b in self.group_buttons.items():
            (b.add_css_class if n == name else b.remove_css_class)('selected')
        self.refresh()

    def _items(self) -> list[str]:
        if self.query:
            q = self.query.lower()
            return [t for t, tags in self.tags.items() if q in t.lower() or q in tags.lower() or q in self.names.get(t, '')]
        if self.group == RECENT:
            hist = get_history(self.history_file)
            return sorted(hist, key=lambda t: hist[t]['lastUsage'], reverse=True)[:RECENT_LIMIT]
        return [t for t, _ in self.groups[self.group]]

    names: dict[str, str] = {}  # optional text -> extra searchable name (symbols: Unicode names)

    def refresh(self):
        while (child := self.flow.get_first_child()) is not None:
            self.flow.remove(child)
        items = self._items()
        for text in items:
            label = Gtk.Label(label=text, ellipsize=Pango.EllipsizeMode.END, css_classes=['text-pick'],
                              tooltip_text=text, margin_top=4, margin_bottom=4, margin_start=4, margin_end=4)
            child = Gtk.FlowBoxChild(child=label, css_classes=['text-pick-child'])
            child.pick_text = text
            child.pick = lambda invert, t=text: self.on_pick(t, invert, self.history_file)
            self.flow.append(child)
        self.tip.set_visible(self.group == RECENT and not self.query and not items)

    def set_filter(self, query: str):
        self.query = query.strip()
        self.refresh()

    def first_text(self):
        child = self.flow.get_first_child()
        return child.pick_text if child else None

    def pick_first(self, invert: bool) -> bool:
        child = self.flow.get_first_child()
        if child:
            child.pick(invert)
        return child is not None

    def focus_first(self):
        child = self.flow.get_first_child()
        if child:
            child.grab_focus()
