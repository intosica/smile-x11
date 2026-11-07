#!/usr/bin/python3
"""Phase 2 acceptance: type the four emoji sequences into GTK4/GTK3/Qt5/xterm/alacritty/Firefox on a
private Xvfb and verify (a) the text arrived and (b) CLIPBOARD+PRIMARY are byte-identical.

    python3 tests/test_inject_targets.py [target ...]     # default: all
"""
import http.server
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'src'))

DISPLAY = ':79'
SAMPLES = ['😄', '👍🏽', '🏳️‍🌈', '👨‍👩‍👧']
EXPECT = ''.join(SAMPLES)
PY = '/usr/bin/python3'
procs = []


def sh(*a, **k):
    return subprocess.run(a, capture_output=True, text=True, **k).stdout


def xclip_get(sel):
    r = subprocess.run(['xclip', '-o', '-selection', sel], capture_output=True)
    return r.stdout


def wait_window(name, timeout=15):
    t = time.time()
    while time.time() - t < timeout:
        ids = sh('xdotool', 'search', '--name', name).split()
        if ids:
            return ids[-1]
        time.sleep(0.2)
    raise RuntimeError(f'window {name!r} never appeared')


def focus(wid):
    sh('xdotool', 'windowfocus', '--sync', wid)
    time.sleep(0.3)


def run_file_target(tmp, name, cmd, env=None):
    out = os.path.join(tmp, name + '.txt')
    p = subprocess.Popen(cmd(out), env={**os.environ, **(env or {})}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    procs.append(p)
    return out, p


def read(path):
    try:
        return open(path, encoding='utf-8').read()
    except FileNotFoundError:
        return ''


def target_gtk(kind):
    def go(tmp):
        out, p = run_file_target(tmp, kind, lambda o: [PY, os.path.join(HERE, 'targets.py'), kind, o])
        wid = wait_window('target-' + kind)
        time.sleep(0.7)
        return out, wid, p, None
    return go


def target_xterm(tmp):
    out = os.path.join(tmp, 'xterm.txt')
    p = subprocess.Popen(['xterm', '-u8', '-T', 'target-xterm', '-e', 'sh', '-c', f'stty raw -echo; exec cat > {out}'],
                         env={**os.environ, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}, stderr=subprocess.DEVNULL)
    procs.append(p)
    wid = wait_window('target-xterm')
    time.sleep(0.7)
    return out, wid, p, None


def target_alacritty(tmp):
    out = os.path.join(tmp, 'alacritty.txt')
    p = subprocess.Popen(['alacritty', '-T', 'target-alacritty', '-e', 'sh', '-c', f'stty raw -echo; exec cat > {out}'],
                         env={**os.environ, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'WINIT_UNIX_BACKEND': 'x11',
                              'LIBGL_ALWAYS_SOFTWARE': '1'}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    procs.append(p)
    wid = wait_window('target-alacritty')
    time.sleep(1.0)
    return out, wid, p, None


PAGE = b"""<title>target-web</title><textarea id=t autofocus rows=8 cols=40
oninput="fetch('/log?v='+encodeURIComponent(this.value))"></textarea>"""


def target_firefox(tmp):
    out = os.path.join(tmp, 'firefox.txt')

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith('/log?v='):
                open(out, 'w', encoding='utf-8').write(urllib.parse.unquote(self.path[7:]))
                self.send_response(204); self.end_headers()
            else:
                self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers()
                self.wfile.write(PAGE)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    prof = os.path.join(tmp, 'ffprofile')
    os.makedirs(prof)
    open(os.path.join(prof, 'user.js'), 'w').write(
        'user_pref("browser.shell.checkDefaultBrowser", false);\nuser_pref("datareporting.policy.dataSubmissionEnabled", false);\n'
        'user_pref("browser.startup.homepage_override.mstone", "ignore");\nuser_pref("startup.homepage_welcome_url", "");\n'
        'user_pref("browser.aboutwelcome.enabled", false);\nuser_pref("browser.preonboarding.enabled", false);\n'
        'user_pref("termsofuse.bypassNotification", true);\nuser_pref("termsofuse.acceptedVersion", 999);\nuser_pref("trailhead.firstrun.didSeeAboutWelcome", true);\n'
        'user_pref("browser.startup.firstrunSkipsHomepage", true);\nuser_pref("toolkit.telemetry.reportingpolicy.firstRun", false);\n')
    p = subprocess.Popen(['firefox', '--no-remote', '--profile', prof, f'http://127.0.0.1:{srv.server_port}/'],
                         env={**os.environ, 'MOZ_ENABLE_WAYLAND': '0', 'GDK_BACKEND': 'x11'},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    procs.append(p)
    wid = wait_window('target-web', 60)
    time.sleep(3)
    # focus the textarea: Firefox honours autofocus, but click inside the page to be sure
    geo = sh('xdotool', 'getwindowgeometry', '--shell', wid)
    g = dict(l.split('=') for l in geo.split() if '=' in l)
    sh('xdotool', 'mousemove', '--window', wid, '100', '200', 'click', '1')
    time.sleep(0.5)
    return out, wid, p, srv


TARGETS = {'gtk4': target_gtk('gtk4'), 'gtk3': target_gtk('gtk3'), 'qt5': target_gtk('qt5'),
           'xterm': target_xterm, 'alacritty': target_alacritty, 'firefox': target_firefox}


def main():
    import input_x11
    names = sys.argv[1:] or list(TARGETS)
    xvfb = subprocess.Popen(['Xvfb', DISPLAY, '-screen', '0', '1280x800x24'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    os.environ['DISPLAY'] = DISPLAY
    os.environ['GDK_BACKEND'] = 'x11'
    os.environ['QT_QPA_PLATFORM'] = 'xcb'
    tmp = tempfile.mkdtemp(prefix='injtest')
    # sentinel selections: owned by background xclip processes
    for sel, val in (('clipboard', 'SENTINEL-CLIPBOARD'), ('primary', 'SENTINEL-PRIMARY')):
        subprocess.run(['xclip', '-i', '-selection', sel], input=val.encode(), check=True)
    clip0, prim0 = xclip_get('clipboard'), xclip_get('primary')
    assert clip0 == b'SENTINEL-CLIPBOARD' and prim0 == b'SENTINEL-PRIMARY', (clip0, prim0)
    results = {}
    try:
        for name in names:
            try:
                out, wid, p, srv = TARGETS[name](tmp)
            except Exception as e:  # noqa
                results[name] = f'SKIP ({e})'
                continue
            focus(wid)
            t0 = time.perf_counter()
            for s in SAMPLES:
                input_x11.type_text(s + ('\n' if name in () else ''))
            dt = (time.perf_counter() - t0) * 1000
            time.sleep(1.0)
            got = read(out)
            ok = got == EXPECT
            results[name] = f"{'PASS' if ok else 'FAIL'} ({dt:.0f} ms for 4 sequences)" + ('' if ok else f' got={got!r}')
            p.terminate()
            if srv:
                srv.shutdown()
            time.sleep(0.5)
    finally:
        clip1, prim1 = xclip_get('clipboard'), xclip_get('primary')
        for p in procs:
            if p.poll() is None:
                p.kill()
        xvfb.kill()
        shutil.rmtree(tmp, ignore_errors=True)
    for k, v in results.items():
        print(f'{k:10s} {v}')
    same = (clip1 == clip0 and prim1 == prim0)
    print('clipboard/primary byte-identical:', same, clip1, prim1)
    sys.exit(0 if same and all(v.startswith('PASS') for v in results.values() if not v.startswith('SKIP')) else 1)


if __name__ == '__main__':
    main()
