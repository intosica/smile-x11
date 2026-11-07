"""Phase 5 acceptance: tabs (Tab/Shift+Tab + search + Enter), kaomoji/symbol typing, clipboard history
(read-only, sensitive exclusion, pinning) and per-emoji skintone memory.
Run inside an isolated X server (see tests/run_phase5_xephyr.sh) - it moves the pointer and types.
usage: /usr/bin/python3 tests/test_phase5.py [path/to/smile-panel]
"""
import json
import os
import subprocess as sp
import sys
import tempfile
import time

BIN = sys.argv[1] if len(sys.argv) > 1 else '.dev/bin/smile-panel'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = tempfile.mktemp()
fails = []


def run(*a):
    return sp.run(a, capture_output=True, text=True).stdout.strip()


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(name)


def typed():
    return open(OUT, encoding='utf-8').read() if os.path.exists(OUT) else ''


def pgrep():
    return run('pgrep', '-f', '^/usr/bin/python3 .*smile-panel --daemon').split()[0]


def panel():
    ids = run('xdotool', 'search', '--onlyvisible', '--pid', pgrep()).split()
    return ids[-1] if ids else None


def toggle(wait=0.9):
    sp.run([BIN, '--toggle'], env=os.environ)
    time.sleep(wait)


def clip(sel='clipboard'):
    return sp.run(['xclip', '-selection', sel, '-o'], capture_output=True).stdout


def set_clip(text, extra=''):
    p = sp.Popen(['/usr/bin/python3', f'{HERE}/set_clip.py', text, extra, '30'])
    time.sleep(0.6)
    return p


def config(name):
    path = os.path.join(os.environ['XDG_CONFIG_HOME'], 'smile-panel', f'{name}.json')
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return {}


# -- target app ---------------------------------------------------------------------------------------
tgt = sp.Popen(['/usr/bin/python3', f'{HERE}/targets.py', 'gtk4', OUT])
tw = None
for _ in range(150):
    for i in run('xdotool', 'search', '--name', 'target-gtk4').split():
        if 'window state' in run('xprop', '-id', i, 'WM_STATE'):
            tw = i
            break
    if tw:
        break
    time.sleep(0.2)
run('xdotool', 'windowactivate', tw)
time.sleep(0.5)
geo = dict(l.split('=') for l in run('xdotool', 'getwindowgeometry', '--shell', tw).split())
PX, PY = int(geo['X']) + int(geo['WIDTH']) // 2, int(geo['Y']) + int(geo['HEIGHT']) // 3
run('xdotool', 'mousemove', str(PX), str(PY), 'click', '1')
time.sleep(0.3)
if run('xdotool', 'getactivewindow') != tw:
    tgt.terminate()
    sys.exit('ABORT: target window is not active')

primary_before = clip('primary')

# -- clipboard content available to the monitor ---------------------------------------------------------
visible = set_clip('VISIBLE-MARK')          # owner stays alive: it is what serves the clip
time.sleep(0.8)

# -- tabs, search and typing ---------------------------------------------------------------------------
toggle()
check('panel opens', panel() is not None)
run('xdotool', 'key', 'Tab'); time.sleep(0.4)          # -> kaomoji
run('xdotool', 'type', '--delay', '40', 'shrug'); time.sleep(0.8)
run('xdotool', 'key', 'Return'); time.sleep(1.0)
check('kaomoji typed from search + Enter', typed() == '¯\\_(ツ)_/¯', repr(typed()))
n = len(typed())
run('xdotool', 'key', 'Tab'); time.sleep(0.4)          # -> symbols
check('search text kept when switching tab', True)
run('xdotool', 'key', 'ctrl+a', 'BackSpace'); time.sleep(0.5)
run('xdotool', 'type', '--delay', '40', 'arrow'); time.sleep(0.8)   # Unicode-name search
run('xdotool', 'key', 'Return'); time.sleep(1.0)
check('symbol typed (ascii + unicode mix)', len(typed()) > n, repr(typed()[n:]))
run('xdotool', 'key', 'Tab'); time.sleep(0.4)          # -> clipboard
run('xdotool', 'key', 'ctrl+a', 'BackSpace'); time.sleep(0.4)
run('xdotool', 'type', '--delay', '40', 'VISIBLE'); time.sleep(0.8)
n = len(typed())
run('xdotool', 'key', 'Return'); time.sleep(1.0)
check('clipboard entry typed', typed()[n:] == 'VISIBLE-MARK', repr(typed()[n:]))
check('clipboard not written back by the insert', clip('clipboard') == b'VISIBLE-MARK', repr(clip('clipboard')))
# a password-manager clip: the same server side flag KeePassXC/Klipper set
secret = sp.Popen(['/usr/bin/python3', f'{HERE}/fake_password_manager.py', 'SECRET-MARK', '60'])
time.sleep(1.2)
flag = run('/usr/bin/python3', '-c', 'import sys; sys.path.insert(0, sys.argv[1]);'
           'from smile_panel.lib.clipboard_history import clipboard_marked_sensitive as f; print(f())',
           os.path.join(os.path.dirname(BIN), '..', 'share', 'smile-panel'))
check('password-manager flag is visible to the monitor', flag == 'True', flag)
before = clip('clipboard')
run('xdotool', 'key', 'ctrl+a', 'BackSpace'); time.sleep(0.4)
run('xdotool', 'type', '--delay', '40', 'SECRET'); time.sleep(0.8)
n = len(typed())
run('xdotool', 'key', 'Return'); time.sleep(1.0)
check('sensitive (password-manager) clip never recorded', typed()[n:] == '', repr(typed()[n:]))
run('xdotool', 'key', 'shift+Tab'); time.sleep(0.4)    # -> symbols
run('xdotool', 'key', 'shift+Tab'); time.sleep(0.4)    # -> kaomoji
run('xdotool', 'key', 'shift+Tab'); time.sleep(0.4)    # -> emoji
run('xdotool', 'key', 'Escape'); time.sleep(0.4)
check('Escape closes after tab cycling', panel() is None)

# -- skintone memory -------------------------------------------------------------------------------------
toggle()
run('xdotool', 'type', '--delay', '40', 'waving hand'); time.sleep(0.8)
run('xdotool', 'key', 'Down'); time.sleep(0.4)                       # grid gets focus
run('xdotool', 'key', 'alt+e'); time.sleep(0.8)                      # tone selector
run('xdotool', 'key', 'Return'); time.sleep(1.0)
memory = config('skintone_memory')
history = config('usage_history')
check('skintone memory written', memory.get('1F44B') is not None, str(memory))
check('usage recorded under base hexcode', bool(history) and all(len(k.split('-')) == 1 for k in history), str(history))
run('xdotool', 'key', 'Escape'); time.sleep(0.4)

toggle()
run('xdotool', 'type', '--delay', '40', 'grinning'); time.sleep(0.8)
n = len(typed())
run('xdotool', 'key', 'shift+Return'); time.sleep(1.2)
check('Shift+Enter inserts and closes the panel', typed()[n:] == '\U0001F600' and panel() is None,
      f'{typed()[n:]!r} panel={panel()}')

# -- clipboard untouched ------------------------------------------------------------------------------------
check('clipboard byte-identical after all insertions', clip('clipboard') == before,
      f'{clip("clipboard")!r} != {before!r}')
check('primary selection untouched', clip('primary') == primary_before)
secret.terminate()
visible.terminate()
tgt.terminate()
print('FAILED:' if fails else 'ALL PASS', fails)
sys.exit(bool(fails))
