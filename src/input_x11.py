"""Clipboard-free text injection through XTest. Implemented in Phase 2."""


class InjectionError(Exception):
    """Raised when text could not be typed; the clipboard is never used as a fallback."""


def type_text(text: str, display=None) -> None:
    raise InjectionError('XTest injection is not implemented yet (Phase 2)')
