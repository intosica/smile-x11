"""Hold an XGrabKey on Super+period for N seconds (simulates a conflicting WM/IBus grab)."""
import sys, time
from Xlib import X, XK, display
d = display.Display(); r = d.screen().root
r.grab_key(d.keysym_to_keycode(XK.string_to_keysym('period')), X.Mod4Mask, False, X.GrabModeAsync, X.GrabModeAsync)
d.sync()
print('holding', flush=True)
time.sleep(float(sys.argv[1]) if len(sys.argv) > 1 else 60)
