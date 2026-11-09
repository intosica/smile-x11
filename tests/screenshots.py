#!/usr/bin/env python3
"""Reproducible screenshots of the panel (see docs/SCREENSHOTS.md).

    tests/screenshots.py [--font FILE.ttf] [--out DIR] [--prefix DIR] [scenario ...]

Runs the panel from a dev install (default prefix: .dev) in an isolated Xephyr + openbox +
private D-Bus session with a throw-away XDG_* tree, so the user's session, settings and clipboard
are never touched. Prints one `name path` line per PNG written. Exit code 1 if any scenario failed.
Needs: Xephyr openbox xdotool dbus-run-session python3-pil (system python).
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ':81'
APP = 'local.winpanel.Smile'
NEW = 'fingerprint orca trombone harp leafless root vegetable landslide distorted bags'.split()

# name -> list of steps: ('type', text) ('key', 'Tab ...') ('pref',) ('scroll', clicks)
SCENARIOS = {
    'emoji': [],
    'search': [('type', 'heart')],
    'kaomoji': [('key', 'Tab')],
    'symbols': [('key', 'Tab Tab')],
    'clipboard': [('key', 'Tab Tab Tab')],
    'preferences': [('pref',)],
    'preferences-font': [('pref',), ('scroll', '8')],
    **{f'new-{w}': [('type', w)] for w in NEW},
}


def sh(*cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def grab(path):
    from PIL import ImageGrab
    img = ImageGrab.grab(xdisplay=D).convert('RGB')
    img.crop(img.getbbox()).save(path)       # crop the black Xephyr background


def run_scenarios(args, env):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bin_ = Path(args.prefix) / 'bin' / 'smile-panel'
    if args.font:
        sh('gsettings', 'set', APP, 'emoji-font-file', str(Path(args.font).resolve()), env=env)
    subprocess.Popen(['openbox'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    log = open(tempfile.gettempdir() + '/screenshots-panel.log', 'w')
    daemon = subprocess.Popen([bin_, '--daemon'], env=env, stdout=log, stderr=subprocess.STDOUT)
    time.sleep(2)
    failed = 0
    names = args.scenario or list(SCENARIOS)
    for name in names:
        try:
            steps = SCENARIOS[name]
            sh('xdotool', 'mousemove', '300', '200', env=env)
            sh(bin_, '--toggle', env=env)          # prefs window is transient for the panel: must be visible
            time.sleep(1.2)
            for step, *a in steps:
                if step == 'type':
                    sh('xdotool', 'type', '--delay', '60', a[0], env=env)
                elif step == 'key':
                    for k in a[0].split():
                        sh('xdotool', 'key', k, env=env)
                        time.sleep(0.3)
                elif step == 'scroll':
                    sh('xdotool', 'mousemove', '450', '500', 'click', '--repeat', a[0], '--delay', '80', '5', env=env)
                elif step == 'pref':
                    sh('gdbus', 'call', '--session', '--dest', APP, '--object-path', '/local/winpanel/Smile',
                       '--method', 'org.freedesktop.Application.ActivateAction', 'preferences', '[]', '{}',
                       env=env, stdout=subprocess.DEVNULL)
                time.sleep(1)
            path = out / f'{name}.png'
            grab(path)
            print(name, path, flush=True)
            sh('xdotool', 'key', 'Escape', env=env)           # closes the panel or the prefs window
            time.sleep(0.5)
        except Exception as e:  # keep going: report all broken scenarios in one run
            failed += 1
            print(f'FAILED {name}: {e}', file=sys.stderr)
    daemon.terminate()
    return failed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('scenario', nargs='*', help='default: all of ' + ' '.join(SCENARIOS))
    ap.add_argument('--font', help='emoji font file to set in the panel (e.g. the iOS NotoColorEmoji.ttf)')
    ap.add_argument('--out', default=str(ROOT / 'docs/screenshots'))
    ap.add_argument('--prefix', default=str(ROOT / '.dev'), help='dev install prefix (meson setup --prefix)')
    ap.add_argument('--inner', action='store_true', help=argparse.SUPPRESS)
    args = ap.parse_args()
    unknown = set(args.scenario) - set(SCENARIOS)
    if unknown:
        ap.error(f'unknown scenario(s): {", ".join(sorted(unknown))}')

    if not args.inner:                                           # re-exec inside a private session bus
        cmd = ['dbus-run-session', '--config-file', str(ROOT / 'tests/session.conf'), '--',
               sys.executable, __file__, '--inner', *sys.argv[1:]]
        subprocess.run(['pkill', '-f', f'Xephyr {D}'])
        xephyr = subprocess.Popen(['Xephyr', D, '-screen', '900x1000', '-ac'],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
        tmp = tempfile.mkdtemp()
        env = {**os.environ, 'DISPLAY': D, 'XDG_DATA_HOME': tmp + '/data', 'XDG_CONFIG_HOME': tmp + '/config',
               'XDG_CACHE_HOME': tmp + '/cache', 'GSETTINGS_BACKEND': 'keyfile',
               'GSETTINGS_SCHEMA_DIR': f'{args.prefix}/share/glib-2.0/schemas',
               'XDG_DATA_DIRS': f'{args.prefix}/share:/usr/share', 'GTK_USE_PORTAL': '0',
               'NO_AT_BRIDGE': '1', 'GTK_A11Y': 'none'}
        try:
            return subprocess.run(cmd, env=env).returncode
        finally:
            xephyr.terminate()
            shutil.rmtree(tmp, ignore_errors=True)
    return 1 if run_scenarios(args, os.environ) else 0


if __name__ == '__main__':
    sys.exit(main())
