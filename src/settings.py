"""Persistent settings for ReCam, stored in config/default.json."""

import json
import os

DEFAULTS = {
    "camera_facing": "back",        # "back" | "front" | "external"
    "camera_size": "1920x1080",     # "1280x720" | "1920x1080"
    "video_codec": "h265",          # "h264" | "h265"
    "capture_orientation": 0,       # 0 | 90 | 180 | 270
    "turn_screen_off": False,
    "device_path": "/dev/video9",
    "auto_start_stream": True,
    "preview_enabled": True,
}

VALID = {
    "camera_facing": {"back", "front", "external"},
    "camera_size": {"1280x720", "1920x1080"},
    "video_codec": {"h264", "h265"},
    "capture_orientation": {0, 90, 180, 270},
}


def _validate(raw):
    """Clamp unknown values back to defaults so bad edits never crash the GUI."""
    settings = dict(DEFAULTS)
    for key, value in raw.items():
        if key not in settings:
            continue
        allowed = VALID.get(key)
        if allowed is not None and value not in allowed:
            continue
        if not isinstance(value, type(settings[key])):
            continue
        settings[key] = value
    return settings


def load(path):
    if os.path.isfile(path):
        try:
            with open(path, "r") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                return _validate(raw)
        except (json.JSONDecodeError, OSError):
            pass
    # Missing or unreadable: self-heal to defaults.
    settings = dict(DEFAULTS)
    save(settings, path)
    return settings


def save(settings, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)
