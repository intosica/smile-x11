from time import time
from .user_config import read_json_config, save_json_config

MAX_HISTORY = 200  # Recents shows the newest 30, Frequently used the 30 most used


def record_usage(key: str, filename: str = 'usage_history'):
    """Count one use of ``key`` (emoji hexcode, kaomoji or symbol text) in config/<filename>.json."""
    history = read_json_config(filename) or {}
    entry = history.setdefault(key, {'count': 0})
    entry['count'] += 1
    entry['lastUsage'] = time()

    if len(history) > MAX_HISTORY:
        del history[min(history, key=lambda k: history[k]['lastUsage'])]

    save_json_config(history, filename)


def get_history(filename: str = 'usage_history') -> dict:
    return read_json_config(filename) or {}


def get_skintone_memory() -> dict:
    """base emoji hexcode -> skintone modifier ('' = no tone) chosen last time for that emoji."""
    return read_json_config('skintone_memory') or {}


def remember_skintone(base_hexcode: str, modifier: str):
    memory = get_skintone_memory()
    memory[base_hexcode] = modifier
    save_json_config(memory, 'skintone_memory')
