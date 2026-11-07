"""Phase 3 acceptance on a live X11 session with a running `smile-panel --daemon` (moves the real pointer!).
usage: /usr/bin/python3 tests/test_overlay_session.py [path/to/smile-panel]
"""
import os, subprocess as sp, sys, tempfile, time

BIN = sys.argv[1] if len(sys.argv) > 1 else '.dev/bin/smile-panel'
HERE = os.path.dirname(os.path.abspath(__file__))
out = tempfile.mktemp()
fails = []


def run(*a, **k):
    return sp.run(a, capture_output=True, text=True, **k).stdout.strip()


def check(name, cond):
    print(('PASS ' if cond else 'FAIL ') + name)
    if not cond:
        fails.append(name)


def clip(sel):
    return sp.run(['xclip', '-selection', sel, '-o'], capture_output=True).stdout


def panel_win():
    ids = run('xdotool', 'search', '--onlyvisible', '--pid', pgrep()).split()
    return ids[-1] if ids else None


def pgrep():
    return run('pgrep', '-f', '^/usr/bin/python3 .*smile-panel --daemon').split()[0]


def geom(w):
    g = dict(l.split('=') for l in run('xdotool', 'getwindowgeometry', '--shell', w).split())
    return int(g['X']), int(g['Y']), int(g['WIDTH']), int(g['HEIGHT'])


def toggle():
    sp.run([BIN, '--toggle'], env=os.environ)
    time.sleep(0.5)


def read():
    return open(out, encoding='utf-8').read() if os.path.exists(out) else ''


sp.run('printf SENT-CLIP | xclip -selection clipboard; printf SENT-PRIM | xclip -selection primary', shell=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
before = (clip('clipboard'), clip('primary'))
tgt = sp.Popen(['/usr/bin/python3', f'{HERE}/targets.py', 'gtk4', out])
tw = None
for _ in range(150):
    ids = run('xdotool', 'search', '--name', 'target-gtk4').split()
    ids = [i for i in ids if 'window state' in run('xprop', '-id', i, 'WM_STATE')]   # skip GTK's hidden leader windows
    if ids:
        tw = ids[0]
        break
    time.sleep(0.2)
time.sleep(0.5)
run('xdotool', 'windowmove', tw, '300', '200')
run('xdotool', 'windowactivate', tw)
time.sleep(0.5)
tx, ty, twid, thei = geom(tw)
PX, PY = tx + twid // 2, ty + thei // 3          # a point inside the target, above where the panel will open
run('xdotool', 'mousemove', str(PX), str(PY), 'click', '1')
time.sleep(0.3)
if run('xdotool', 'getactivewindow') != tw:
    tgt.terminate()
    sys.exit('ABORT: target window is not active; refusing to click/type into other apps')

toggle()
pw = panel_win()
check('panel appears', pw is not None)
x, y, w, h = geom(pw)
print('panel geometry', x, y, w, h)
check('panel size ~360x480', (w, h) == (360, 480))
# three emoji clicks on the grid (rows below the top bar)
run('xdotool', 'type', '--delay', '40', 'smile'); time.sleep(0.8)
for dx, dy in ((44, 60), (112, 60), (180, 100)):
    run('xdotool', 'mousemove', str(x + dx), str(y + dy), 'click', '1')
    time.sleep(0.6)
typed = read()
print('typed:', repr(typed))
check('3 emoji typed, panel still visible', len(typed) >= 3 and panel_win() is not None)
run('xdotool', 'mousemove', str(x + 200), str(y + 380), 'click', '1')   # empty grid area (whitespace)
time.sleep(0.3)
check('inside click keeps panel', panel_win() is not None)
run('xdotool', 'mousemove', str(PX), str(PY), 'click', '1')
time.sleep(0.4)
check('outside click (other app) closes', panel_win() is None)
toggle()
check('toggle shows', panel_win() is not None)
run('xdotool', 'key', 'Escape'); time.sleep(0.3)
check('Escape closes', panel_win() is None)
toggle(); toggle()
check('toggle hides', panel_win() is None)
toggle()
n = len(read())
run('xdotool', 'type', '--delay', '30', 'grin'); time.sleep(0.4)
run('xdotool', 'key', 'shift+Return'); time.sleep(0.6)
check('Shift+Enter inserts', len(read()) > n)
check('Shift+Enter closes', panel_win() is None)
after = (clip('clipboard'), clip('primary'))
check('clipboard/primary untouched', before == after)
tgt.terminate()
print('FAILED:' if fails else 'ALL PASS', fails)
sys.exit(bool(fails))
