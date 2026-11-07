# main.py
#
# Copyright 2021 Lorenzo Paderi
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import gi
import re
from typing import Optional

from .ShortcutsWindow import ShortcutsWindow
from .components.CustomTagEntry import CustomTagEntry
from .components.SkintoneSelector import SkintoneSelector
from .components.EmojiItem import EmojiItem
from .components.EmojiButton import EmojiButton
from .lib.custom_tags import get_custom_tags
from .lib.localized_tags import get_localized_tags
from .lib.emoji_history import record_usage, get_history, get_skintone_memory, remember_skintone
from .lib.clipboard_history import ClipboardHistory
from .components.TextGridPage import TextGridPage
from .components.ClipboardPage import ClipboardPage
from .utils import tag_list_contains, debounce, idle
from .window_x11 import OverlayController
from . import input_x11  # noqa: F401  (InjectionError)
from .assets.emoji_list import emojis, emoji_categories
from .assets.kaomoji import KAOMOJI_GROUPS, GROUP_LABELS as KAOMOJI_GROUP_LABELS
from .assets.symbols import SYMBOL_GROUPS, GROUP_LABELS as SYMBOL_GROUP_LABELS, symbol_name

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Gio, Gdk, Adw, GLib, Pango  # noqa

class Picker(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(title="Smile Panel", *args, **kwargs)
        self.overlay_ctl = OverlayController(self)
        self.overlay_ctl.on_shown = lambda: self.set_focus(self.search_entry)
        self.overlay_ctl.on_hidden = self.reset_state

        self.EMOJI_GRID_COL_N = 5

        self.settings: Gio.Settings = Gio.Settings.new('local.winpanel.Smile')

        self.search_entry = Gtk.SearchEntry(hexpand=True, width_request=200)
        self.list_model = Gio.ListStore(item_type=EmojiItem)
        factory = Gtk.SignalListItemFactory()
        factory.connect('setup', self.on_setup)
        factory.connect('bind', self.on_bind)
        self.selection_model = Gtk.SingleSelection(model=self.list_model)
        self.grid_view = Gtk.GridView(
            model=self.selection_model,
            enable_rubberband=False,
            single_click_activate=False,
            factory=factory,
            min_columns=self.EMOJI_GRID_COL_N,
            max_columns=self.EMOJI_GRID_COL_N,
        )



        self.emoji_items: list[EmojiItem] = []
        self.refresh_emoji_items()

        self.data_dir = Gio.Application.get_default().datadir
        self.selected_category_index = 0
        self.selected_category = 'smileys-emotion'
        self.categories_count = 0
        self.skintone_selector: Optional[SkintoneSelector] = None

        event_controller_keys = Gtk.EventControllerKey()
        event_controller_keys.connect('key-pressed', self.handle_window_key_press)
        self.add_controller(event_controller_keys)

        # GtkText inside GtkSearchEntry eats Up/Down for cursor movement before the bubble-phase
        # handler sees them, so grabbing them needs the capture phase.
        self.search_nav_controller = Gtk.EventControllerKey()
        self.search_nav_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.search_nav_controller.connect('key-pressed', self.handle_search_nav)
        self.add_controller(self.search_nav_controller)

        self.settings.connect('changed::skintone-modifier', self.update_emoji_skintones)
        self.settings.connect('changed::emoji-size-class', self.update_emoji_size)

        self.viewport_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=['viewport'], vexpand=True)

        self.list_tip_revealer = Gtk.Revealer(
            reveal_child=False,
            transition_type=Gtk.RevealerTransitionType.NONE,
            css_classes=['solid-overlay'],
            visible=False
        )

        self.list_tip_label = Gtk.Label(
            label= _("Whoa, it's still empty! \nYour most used emojis will show up here\n"),
            css_classes=['dim-label'],
            justify=Gtk.Justification.CENTER
        )

        self.list_tip_revealer.set_child(self.list_tip_label)

        self.refresh_emoji_list()
        self.category_picker_widgets: list[Gtk.Button] = []
        self.category_picker = self.create_category_picker()

        scrolled_emoji_window = Gtk.ScrolledWindow(
            vexpand=True
        )

        scrolled_emoji_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_emoji_window.set_child(self.grid_view)

        emoji_list_overlay_container = Gtk.Overlay(child=scrolled_emoji_window)

        emoji_list_overlay_container.add_overlay(self.list_tip_revealer)

        emoji_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        emoji_page.append(emoji_list_overlay_container)
        emoji_page.append(self.category_picker)

        # Kaomoji / Symbols / Clipboard
        self.kaomoji_page = TextGridPage(
            groups=KAOMOJI_GROUPS, group_labels=KAOMOJI_GROUP_LABELS, history_file='kaomoji_history',
            columns=4, on_pick=self.on_text_pick, shift_held=self.shift_held,
            empty_recent_text=_("Kaomoji you insert show up here"))
        self.symbols_page = TextGridPage(
            groups=SYMBOL_GROUPS, group_labels=SYMBOL_GROUP_LABELS, history_file='symbols_history',
            columns=10, on_pick=self.on_text_pick, shift_held=self.shift_held,
            empty_recent_text=_("Symbols you insert show up here"))
        self.symbols_page.names = {ch: symbol_name(ch) for chars in SYMBOL_GROUPS.values() for ch in chars}
        self.clipboard_history = ClipboardHistory(persist=self.settings.get_boolean('clipboard-persist'))
        self.clipboard_page = ClipboardPage(history=self.clipboard_history, on_pick=self.on_clipboard_pick,
                                            shift_held=self.shift_held)
        self.clipboard_page.set_enabled(self.settings.get_boolean('clipboard-history-enabled'))

        self.stack = Adw.ViewStack()
        self.stack.add_titled_with_icon(emoji_page, 'emoji', _('Emoji'), 'face-smile-symbolic')
        self.stack.add_titled_with_icon(self.kaomoji_page, 'kaomoji', _('Kaomoji'), 'emoji-people-symbolic')
        self.stack.add_titled_with_icon(self.symbols_page, 'symbols', _('Symbols'), 'emoji-symbols-symbolic')
        self.stack.add_titled_with_icon(self.clipboard_page, 'clipboard', _('Clipboard'), 'edit-paste-symbolic')
        self.pages = {'kaomoji': self.kaomoji_page, 'symbols': self.symbols_page, 'clipboard': self.clipboard_page}
        self.stack.connect('notify::visible-child', lambda *_: self.apply_search_filter())

        self.viewport_box.append(self.stack)
        self.viewport_box.append(Adw.ViewSwitcherBar(stack=self.stack, reveal=True))

        # Create search entry
        search_container = Gtk.Box(hexpand=True)

        self.search_entry.connect('search_changed', self.search_emoji)
        self.search_entry.connect('activate', self.handle_search_entry_activate)
        search_container.append(self.search_entry)

        search_controller_key = Gtk.EventControllerKey()
        search_controller_key.connect(
            'key-pressed',
            self.handle_search_entry_keypress
        )

        self.search_entry.add_controller(search_controller_key)

        top_bar = Gtk.Box(spacing=4, css_classes=['panel-topbar'])
        top_bar.append(search_container)
        top_bar.append(self.create_menu_button())
        self.viewport_box.prepend(top_bar)

        self.overlay = Adw.ToastOverlay()
        self.overlay.set_child(self.viewport_box)

        # Windows-style: show what you used last time first (when there is any history)
        history = get_history()
        default_category = 'recents' if history else 'smileys-emotion'
        logging.getLogger('smile-panel').debug('default category %s (%d history entries)',
                                               default_category, len(history))
        self.set_active_category(default_category)
        self.selected_category = default_category
        if history:
            self.refresh_emoji_list()

        self.settings.connect('changed::clipboard-history-enabled',
                              lambda s, _k: self.clipboard_page.set_enabled(s.get_boolean('clipboard-history-enabled')))
        self.settings.connect('changed::clipboard-persist',
                              lambda s, _k: self.clipboard_history.set_persist(s.get_boolean('clipboard-persist')))

        tab_controller = Gtk.EventControllerKey()
        tab_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        tab_controller.connect('key-pressed', self.handle_tab_cycle)
        self.add_controller(tab_controller)

        self.set_child(self.overlay)
        self.search_entry.grab_focus()

    TAB_ORDER = ('emoji', 'kaomoji', 'symbols', 'clipboard')

    def handle_tab_cycle(self, controller, keyval: int, keycode: int, state: Gdk.ModifierType) -> bool:
        if keyval not in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab):
            return False
        back = keyval == Gdk.KEY_ISO_Left_Tab or bool(state & Gdk.ModifierType.SHIFT_MASK)
        i = self.TAB_ORDER.index(self.stack.get_visible_child_name())
        self.stack.set_visible_child_name(self.TAB_ORDER[(i - 1 if back else i + 1) % len(self.TAB_ORDER)])
        return True

    # Create stuff
    def create_menu_button(self):
        builder = Gtk.Builder()
        builder.add_from_resource('/local/winpanel/Smile/ui/menu.ui')
        menu = builder.get_object('primary_menu')

        return Gtk.MenuButton(menu_model=menu, icon_name='open-menu-symbolic', css_classes=['flat'])

    def create_category_picker(self) -> Gtk.Box:
        box = Gtk.Box(spacing=0, halign=Gtk.Align.CENTER, hexpand=True, name='emoji_categories_box')

        categories = {'recents': emoji_categories['recents'], 'frequent': {'icon': 'bookmark-new-symbolic'},
                      **{k: v for k, v in emoji_categories.items() if k != 'recents'}}
        categories['symbols'] = {'icon': 'emoji-symbols-symbolic'}   # 'input-keyboard-numlock-symbolic' is not in Adwaita

        i = 0
        for c, cat in categories.items():
            if not 'icon' in cat:
                continue

            button = Gtk.Button(icon_name=cat['icon'], valign=Gtk.Align.CENTER)
            button.connect('clicked', self.filter_for_category)

            button.category = c
            button.index = i

            box.append(button)
            self.category_picker_widgets.append(button)
            i += 1

        self.categories_count = i

        return box

    def refresh_emoji_list(self):
        self.list_model.remove_all()
        history = get_history()
        filter_for_recents = self.selected_category == 'recents'
        filter_for_frequent = self.selected_category == 'frequent'
        tags_locale = self.settings.get_string('tags-locale')
        merge_english_tags = self.settings.get_boolean('merge-english-tags')
        tags_locale_is_en = (tags_locale == 'en')
        use_localised_tags = False
        query = self.search_entry.get_text().strip()

        if query:
            use_localised_tags = self.settings.get_boolean('use-localized-tags')

        emoji_items: list[EmojiItem] = []
        for emoji_item in self.emoji_items:
            emoji = emoji_item.emoji
            is_recent = (emoji['hexcode'] in history)

            if query:
                localized_tags = []
                filter_result = True

                if use_localised_tags and not tags_locale_is_en:
                    localized_tags = get_localized_tags(tags_locale, emoji['hexcode'], self.data_dir)

                custom_tags = ''
                if query != emoji['emoji']:
                    custom_tags = get_custom_tags(emoji['hexcode'], cache=True)

                if query == emoji['emoji']:
                    filter_result = True
                elif custom_tags and tag_list_contains(custom_tags, query):
                    filter_result = True
                elif use_localised_tags:
                    if merge_english_tags:
                        filter_result = tag_list_contains(','.join(localized_tags), query) or tag_list_contains(emoji['tags'], query)
                    else:
                        filter_result = tag_list_contains(','.join(localized_tags), query)
                elif not use_localised_tags:
                    filter_result = tag_list_contains(emoji['tags'], query)
                else:
                    filter_result = False

                if not filter_result:
                    continue
            else:
                if filter_for_recents:
                    if not is_recent:
                        continue
                elif filter_for_frequent:
                    if not history.get(emoji['hexcode'], {}).get('count'):
                        continue
                elif emoji['group'] != self.selected_category:
                    continue

            emoji_items.append(emoji_item)

        if not query and (filter_for_recents or filter_for_frequent):
            # Recents: newest 30 (history is keyed by base hexcode, tones included)
            # Frequently used: the 30 with the highest use count
            def rank(item: EmojiItem):
                h = history.get(item.emoji['hexcode'], {})
                return h.get('lastUsage', 0) if filter_for_recents else h.get('count', 0)

            emoji_items = sorted(emoji_items, key=rank, reverse=True)[:30]

        self.list_model.splice(
            position=0,
            n_removals=self.list_model.get_n_items(),
            additions=emoji_items
        )

        self.selection_model.unselect_all()


    # Handle events
    def handle_emoji_button_click(self, widget: Gtk.Button):
        widget.get_parent().grab_focus()
        self.insert(widget, invert_close=self.shift_held())

    @staticmethod
    def shift_held() -> bool:
        kbd = Gdk.Display.get_default().get_default_seat().get_keyboard()
        return bool(kbd.get_modifier_state() & Gdk.ModifierType.SHIFT_MASK)

    def insert(self, button: EmojiButton, invert_close: bool = False):
        """Type the emoji into the target app via XTest (never the clipboard)."""
        text = button.get_label()
        if not self.type_text(text, invert_close):
            return
        base = button.base_skintone_widget or button
        base_hexcode = base.emoji_data['hexcode']
        record_usage(base_hexcode)          # one entry per emoji, whatever the tone
        if button.base_skintone_widget is not None:
            self.remember_skintone_choice(button, base_hexcode)

    def type_text(self, text: str, invert_close: bool = False) -> bool:
        """Insert plain text into the target app; returns False (after a notification) on failure."""
        logging.getLogger("smile-panel").debug("insert %r", text)
        try:
            self.overlay_ctl.insert_text(text, self.settings.get_int('key-delay-ms'))
        except input_x11.InjectionError as e:
            notification = Gio.Notification.new(_('Could not insert text'))
            notification.set_body(str(e))
            notification.set_icon(Gio.ThemedIcon.new('dialog-error'))
            self.get_application().send_notification('insert-error', notification)
            return False
        if self.settings.get_boolean('keep-open-after-insert') == invert_close:
            self.default_hiding_action()
        return True

    def on_text_pick(self, text: str, invert_close: bool, history_file: str):
        if self.type_text(text, invert_close):
            record_usage(text, history_file)
            for page in self.pages.values():
                if getattr(page, 'history_file', None) == history_file:
                    page.refresh()

    def on_clipboard_pick(self, text: str, invert_close: bool):
        self.type_text(text, invert_close)   # typed, never written back to the clipboard

    def remember_skintone_choice(self, button: EmojiButton, base_hexcode: str):
        """Remember the tone picked for this emoji and repaint its grid cell."""
        parts = button.hexcode.split('-')
        modifier = parts[1] if len(parts) > 1 else ''
        remember_skintone(base_hexcode, modifier)
        for item in self.emoji_items:
            if item.emoji['hexcode'] == base_hexcode:
                item.skintone = modifier
        for i in range(self.list_model.get_n_items()):
            if self.list_model.get_item(i).emoji['hexcode'] == base_hexcode:
                self.list_model.items_changed(i, 1, 1)
                break

    # Handle every possible keypress here, returns True if the event was handled (prevent default)
    def handle_window_key_press(self, controller: Gtk.EventController, keyval: int, keycode: int, state: Gdk.ModifierType) -> bool:
        if (keyval == Gdk.KEY_Escape):
            self.default_hiding_action()
            return True

        ctrl_key = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift_key = bool(state & Gdk.ModifierType.SHIFT_MASK)
        alt_key = bool(state & Gdk.ModifierType.ALT_MASK)

        is_modifier = ctrl_key or shift_key or alt_key
        keyval_name = Gdk.keyval_name(keyval)
        logging.getLogger('smile-panel').debug('key %r state=%s focus=%r', keyval_name, int(state), self.get_focus())

        focused_widget = self.get_focus()
        focused_button = None
        focused_pick = self.find_pick_widget(focused_widget)

        if isinstance(focused_widget, EmojiButton):
            focused_button = focused_widget

        if alt_key:
            if focused_button and keyval == Gdk.KEY_e:
                self.show_skintone_selector(focused_widget)
                return True

            elif focused_button and keyval == Gdk.KEY_t:
                self.show_custom_tag_entry(focused_widget)
                return True

            elif keyval in [Gdk.KEY_Left, Gdk.KEY_Right]:
                next_sel = None
                if keyval == Gdk.KEY_Left:
                    next_sel = self.selected_category_index - 1 if (self.selected_category_index > 0) else 0
                elif keyval == Gdk.KEY_Right:
                    next_sel_index = (self.categories_count - 1)
                    next_sel = self.selected_category_index + 1 if (self.selected_category_index < (next_sel_index)) else (next_sel_index)

                if next_sel != None:
                    for child in list(self.category_picker_widgets):
                        if child.index == next_sel:
                            self.filter_for_category(child)
                            return True

            return False

        if shift_key:
            if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                if focused_button:
                    self.insert(focused_button, invert_close=True)
                    return True
                if focused_pick:
                    focused_pick.pick(True)
                    return True

        elif ctrl_key:
            if keyval == Gdk.KEY_q:
                self.get_application().activate_action("quit", None)
                return True

            elif keyval == Gdk.KEY_question:
                shortcut_window = ShortcutsWindow()
                shortcut_window.open()

            elif keyval == Gdk.KEY_BackSpace:
                self.search_entry.set_text('')
                self.search_entry.grab_focus()
                return True

        else:
            # handle key combinations without modifiers
            if (not is_modifier) and (keyval == Gdk.KEY_BackSpace):
                self.search_entry.grab_focus()
                return True

            if focused_button:
                # Focus is on an emoji button
                if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                    self.insert(focused_button)
                    return True
                elif (not is_modifier) and (len(keyval_name) == 1) and re.match(r'\S', keyval_name):
                    self.search_entry.insert_text(keyval_name, -1)
                    self.search_entry.set_position(-1)
                    self.search_entry.grab_focus()
                    return True

            elif focused_pick:
                if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                    focused_pick.pick(False)
                    return True
                if (not is_modifier) and (len(keyval_name) == 1) and re.match(r'\S', keyval_name):
                    self.search_entry.insert_text(keyval_name, -1)
                    self.search_entry.set_position(-1)
                    self.search_entry.grab_focus()
                    return True

            elif isinstance(focused_widget, Gtk.Button) and hasattr(focused_widget, 'category'):
                # Focus is on a category button
                # Triggers when we press arrow up on the category picker
                az_re = re.compile(r"[a-z]", re.IGNORECASE)
                if re.match(az_re, keyval_name):
                    self.search_entry.grab_focus()
                else:
                    if (keyval == Gdk.KEY_Up):
                        self.set_active_category(focused_widget.category)
                    return True

        return False

    def handle_skintone_selector_key_press(self, controller: Gtk.EventController, keyval: int, keycode: int, state: Gdk.ModifierType) -> bool:
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            shift_key = bool(state & Gdk.ModifierType.SHIFT_MASK)
            focused_widget: Gtk.FlowBoxChild = self.skintone_selector.get_focus()
            self.skintone_selector.request_close()
            self.insert(focused_widget.get_child(), invert_close=shift_key)
            return True

        return False

    @staticmethod
    def find_pick_widget(widget):
        """Nearest ancestor (or self) that knows how to insert itself: FlowBoxChild / clipboard row."""
        for _ in range(3):
            if widget is None:
                return None
            if hasattr(widget, 'pick'):
                return widget
            widget = widget.get_parent()
        return None

    def handle_search_nav(self, controller, keyval, keycode, state):
        """Down/Up while typing search text jump into the result list instead of moving the caret."""
        focus = self.get_focus()
        if keyval not in (Gdk.KEY_Down, Gdk.KEY_Up) or not focus or not self.search_entry.is_ancestor(focus):
            return False
        if self.stack.get_visible_child_name() == 'emoji':
            self.grid_view.grab_focus()
        else:
            self.pages[self.stack.get_visible_child_name()].focus_first()
        return True

    def handle_search_entry_activate(self, entry: Gtk.Entry):
        # Enter in the search box inserts the first result (Shift+Enter: and inverts keep-open).
        # With no query there is nothing to insert: jump into the list instead.
        if not entry.get_text().strip():
            if self.stack.get_visible_child_name() == 'emoji':
                self.grid_view.grab_focus()
            else:
                self.pages[self.stack.get_visible_child_name()].focus_first()
            return
        name = self.stack.get_visible_child_name()
        if name != 'emoji':
            self.pages[name].pick_first(self.shift_held())
            return
        if self.list_model.get_n_items():
            item: EmojiItem = self.list_model.get_item(0)
            button = EmojiButton()
            button.emoji_data = item.emoji
            button.hexcode = item.emoji['hexcode']
            button.set_label(item.emoji['emoji'].strip())
            self.update_emoji_button_skintone(button, item.skintone)
            self.insert(button, invert_close=self.shift_held())

    def handle_search_entry_keypress(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.default_hiding_action()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and state & Gdk.ModifierType.SHIFT_MASK:
            self.handle_search_entry_activate(self.search_entry)  # GtkText only activates on plain Enter
            return True
        return False

    def default_hiding_action(self):
        self.overlay_ctl.hide()

    def reset_state(self):
        """Runs on every hide (Esc, toggle, outside click, WM unmap)."""
        self.search_entry.set_text('')
        self.set_empty_recent_tip(False)
        if self.selected_category in ('recents', 'frequent'):
            self.refresh_emoji_list()      # freshly used emoji should be at the top next time

    # # # # # #
    def show_skintone_selector(self, focused_widget: EmojiButton):
        if not SkintoneSelector.check_skintone(focused_widget):
            self.overlay.add_toast(
                Adw.Toast(title=_("No skintones available"), timeout=1)
            )
        else:
            self.skintone_selector = SkintoneSelector(
                focused_widget,
                parent=self,
                click_handler=self.handle_emoji_button_click,
                keypress_handler=self.handle_skintone_selector_key_press,
            )

            for widget in self.skintone_selector.flowbox_widgets:
                self.emoji_button_update_css_classes(widget, apply_border_radius=False)

            self.skintone_selector.show()

    def show_custom_tag_entry(self, focused_widget: EmojiButton):
        popup = CustomTagEntry(focused_widget, self)
        popup.show()

    def set_empty_recent_tip(self, enabled: bool):
        self.list_tip_revealer.set_visible(enabled)
        self.list_tip_revealer.set_reveal_child(enabled)

    def set_active_category(self, category: str):
        for b in self.category_picker_widgets:
            if b.category != category:
                b.get_style_context().remove_class('selected')
            else:
                b.get_style_context().add_class('selected')

    def filter_for_category(self, widget: Gtk.Button):
        self.set_active_category(widget.category)
        widget.grab_focus()

        self.selected_category = widget.category
        self.selected_category_index = widget.index

        if widget.category == 'recents':
            empty = not get_history()
        elif widget.category == 'frequent':
            empty = not any(e.get('count') for e in get_history().values())
        else:
            empty = False
        self.set_empty_recent_tip(empty)

        self.refresh_emoji_list()

    @debounce(0.1)
    @idle
    def search_emoji(self, search_entry: Gtk.Entry):
        self.search_entry.grab_focus()
        self.apply_search_filter()

    def apply_search_filter(self):
        """The search box filters whatever tab is visible."""
        name = self.stack.get_visible_child_name()
        if name == 'emoji':
            self.refresh_emoji_list()
        else:
            self.pages[name].set_filter(self.search_entry.get_text().strip())

    def update_emoji_button_skintone(self, emoji_button, modifier_settings):
        if 'skintones' in emoji_button.emoji_data:
            update_data = None

            if len(modifier_settings):
                for tone in emoji_button.emoji_data['skintones']:
                    if f'-{modifier_settings}' in tone['hexcode']:
                        update_data = tone
                        break
            else:
                update_data = emoji_button.emoji_data

            if update_data:
                emoji_button.hexcode = update_data['hexcode']
                emoji_button.set_label(update_data['emoji'])

    def refresh_emoji_items(self):
        self.emoji_items = []
        default = self.settings.get_string('skintone-modifier')
        memory = get_skintone_memory()
        for emoji in emojis.values():
            self.emoji_items.append(EmojiItem(emoji=emoji, skintone=memory.get(emoji['hexcode'], default)))

    def update_emoji_skintones(self, settings: Gio.Settings, key):
        self.refresh_emoji_items()
        self.refresh_emoji_list()

    def update_emoji_size(self, settings: Gio.Settings, key):
        self.refresh_emoji_list()

    def emoji_button_update_css_classes(self, widget: Gtk.Button, apply_border_radius=True):
        emoji_button_css = [self.settings.get_string('emoji-size-class')]

        if apply_border_radius and ('skintones' in widget.emoji_data) and widget.emoji_data['skintones']:
            emoji_button_css.append('emoji-with-skintones')

        widget.set_css_classes(emoji_button_css)

    def on_setup(self, factory, list_item):
        # Called once to create the widget template
        btn = EmojiButton()
        btn.connect('clicked', self.handle_emoji_button_click)
        list_item.set_child(btn)


    def on_bind(self, factory, list_item: Gtk.ListItem):
        # Called each time an item is recycled/shown
        item: EmojiItem = list_item.get_item()

        emoji_data = item.emoji
        emoji_button: EmojiButton = list_item.get_child()
        emoji_button.position = list_item.get_position() + 1
        emoji_button.emoji_data = emoji_data
        emoji_button.hexcode = emoji_data['hexcode']
        emoji_button.set_label(item.emoji['emoji'].strip())
        self.update_emoji_button_skintone(emoji_button, item.skintone)
        self.emoji_button_update_css_classes(emoji_button)
