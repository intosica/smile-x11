import json
import os

from gi.repository import GLib

# JSON files in ~/.config/smile-panel/ (created on first write)


def _config_path(filename: str) -> str:
    config_dir = os.path.join(GLib.get_user_config_dir(), 'smile-panel')
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, f'{filename}.json')


def save_json_config(content: dict or list, filename: str):
    """Saves in a configuration file"""
    with open(_config_path(filename), 'w+') as f:
        f.write(json.dumps(content))


def read_json_config(filename: str) -> dict or list or False:
    """Reads from a configuration file"""
    current_conf_raw = False

    try:
        current_conf_raw = GLib.file_get_contents(_config_path(filename))
    except GLib.Error as e:
        if e.code != GLib.FileError.NOENT:
            return False

    current_conf_json = current_conf_raw.contents.decode() if current_conf_raw else '{}'

    try:
        current_conf = json.loads(current_conf_json)
    except Exception:
        print('Config file is not readable')
        return False

    return current_conf
