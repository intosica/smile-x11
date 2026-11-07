"""XGrabKey global hotkey daemon (Super+period, Super+semicolon). Implemented in Phase 4."""
import logging

log = logging.getLogger('smile-panel.hotkey')


class HotkeyDaemon:
    def __init__(self, on_trigger):
        self.on_trigger = on_trigger

    def start(self) -> None:
        log.warning('built-in hotkey listener not implemented yet (Phase 4); '
                    'bind `smile-panel --toggle` in your WM/DE instead')

    def stop(self) -> None:
        pass
