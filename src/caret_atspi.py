"""Optional caret lookup through AT-SPI. Returns None (-> pointer positioning) when pyatspi or the
accessibility bus is missing, nothing is focused, or the search exceeds BUDGET seconds."""
import time

BUDGET = 0.15


def caret_rect():
    try:
        import pyatspi
    except ImportError:
        return None
    deadline = time.monotonic() + BUDGET

    def find(node, depth=0):
        if time.monotonic() > deadline or depth > 12:
            return None
        try:
            st = node.getState()
            if st.contains(pyatspi.STATE_FOCUSED) and node.queryText() is not None:
                return node
            for child in node:
                hit = find(child, depth + 1)
                if hit is not None:
                    return hit
        except Exception:  # noqa  (dead accessibles, missing interfaces)
            pass
        return None

    try:
        acc = find(pyatspi.Registry.getDesktop(0))
        if acc is None:
            return None
        t = acc.queryText()
        x, y, w, h = t.getCharacterExtents(t.caretOffset, pyatspi.DESKTOP_COORDS)
        return (x, y, w, h) if (w or h) and (x or y) else None
    except Exception:  # noqa
        return None
