import json
import os
import threading
import time

from . import config


queue_lock = threading.Lock()
state = {
    "queue": [],
    "paused": False,
    "running": False,
    "stats": {"downloaded": 0, "failed": 0, "total_added": 0}
}

stop_event = threading.Event()
pause_event = threading.Event()
pause_event.set()

speed_lock = threading.Lock()
speed_data = {
    "history": [],
    "current_start": None,
    "current_track": "",
    "current_bytes": 0,
    "current_total": 0,
    "bytes_per_sec_avg": 0,
}

active_workers = {"count": 0}
workers_lock = threading.Lock()
worker_threads = []
num_workers = [config.MAX_WORKERS]


def update_item(item_id, **kwargs):
    with queue_lock:
        for q in state["queue"]:
            if q["id"] == item_id:
                q.update(kwargs)
                break


def load_state():
    if os.path.exists(config.STATE_FILE):
        try:
            with open(config.STATE_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                state["queue"] = saved.get("queue", [])
                state["stats"] = saved.get("stats", state["stats"])
        except (json.JSONDecodeError, OSError):
            pass


def save_state():
    with open(config.STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            "queue": state["queue"],
            "stats": state["stats"]
        }, f, ensure_ascii=False, indent=2)
