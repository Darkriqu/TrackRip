import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, ".config.json")
SLSKD_URL = os.environ.get("SLSKD_URL", "http://localhost:5030/api/v0")

AUDIO_EXTENSIONS = {'.flac', '.mp3', '.ogg', '.opus', '.m4a', '.aac', '.wav', '.wma', '.ape', '.webm'}
SEARCH_TIMEOUT = 8
DOWNLOAD_TIMEOUT = 90
DOWNLOAD_CHECK_INTERVAL = 2
MIN_WORKERS = 2
MAX_WORKERS = 10


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


_cfg = load_config()
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", _cfg.get("download_dir", os.path.expanduser("~/Downloads/Music")))
STATE_FILE = os.path.join(DOWNLOAD_DIR, ".panel_state.json")

HAS_FFMPEG = None


def detect_ffmpeg():
    global HAS_FFMPEG
    import shutil
    HAS_FFMPEG = shutil.which("ffmpeg") is not None
    if not HAS_FFMPEG:
        local_ffmpeg = os.path.join(BASE_DIR, "ffmpeg")
        if os.path.isdir(local_ffmpeg):
            os.environ["PATH"] = local_ffmpeg + os.pathsep + os.environ.get("PATH", "")
            HAS_FFMPEG = shutil.which("ffmpeg") is not None
    return HAS_FFMPEG


YTDLP_SOURCES = [
    ("ytmusic",    "YouTube Music",  "ytsearch1:{q} official audio"),
    ("soundcloud", "SoundCloud",     "scsearch1:{q}"),
    ("youtube",    "YouTube",        "ytsearch1:{q}"),
]
