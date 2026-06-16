import logging
import os
import time
from datetime import datetime

from flask import Blueprint, jsonify, request, send_from_directory

from . import config, state
from .downloader import ensure_worker, _clean_query, _safe_filename

logger = logging.getLogger(__name__)

api = Blueprint('api', __name__)


@api.route('/')
def index():
    return send_from_directory('static', 'index.html')


@api.route('/speedtest')
def speedtest_page():
    return send_from_directory('static', 'speedtest.html')


@api.route('/api/speedtest')
def api_speedtest():
    with state.speed_lock:
        history = list(state.speed_data["history"])
        avg_speed = state.speed_data["bytes_per_sec_avg"]
        cur_start = state.speed_data["current_start"]
        cur_track = state.speed_data["current_track"]
        cur_bytes = state.speed_data["current_bytes"]
        cur_total = state.speed_data["current_total"]

    with state.queue_lock:
        pending = sum(1 for q in state.state["queue"] if q["status"] == "pending")
        downloading = sum(1 for q in state.state["queue"] if q["status"] == "downloading")
        done = sum(1 for q in state.state["queue"] if q["status"] == "done")
        failed = sum(1 for q in state.state["queue"] if q["status"] == "failed")

    sizes = [h["size_bytes"] for h in history if h["size_bytes"] > 0]
    avg_file_size = sum(sizes) / len(sizes) if sizes else 15 * 1024 * 1024

    durations = [h["duration_sec"] for h in history if h["duration_sec"] > 0]
    avg_track_time = sum(durations) / len(durations) if durations else 30

    remaining = pending + downloading
    eta_seconds = remaining * avg_track_time if avg_track_time > 0 else 0

    last5 = [h for h in history[-5:] if h["duration_sec"] > 0 and h["size_bytes"] > 0]
    if last5:
        cur_speed = sum(h["size_bytes"] for h in last5) / sum(h["duration_sec"] for h in last5)
    else:
        cur_speed = 0

    instant_speed = 0
    if cur_start and cur_bytes > 0:
        elapsed = time.time() - cur_start
        if elapsed > 0:
            instant_speed = cur_bytes / elapsed

    file_count = 0
    total_size = 0
    try:
        for root, dirs, files in os.walk(config.DOWNLOAD_DIR):
            if '.incomplete' in root:
                continue
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in config.AUDIO_EXTENSIONS:
                    file_count += 1
                    total_size += os.path.getsize(os.path.join(root, f))
    except OSError:
        pass

    recent = history[-30:]

    return jsonify({
        "running": state.state["running"],
        "paused": state.state["paused"],
        "queue": {
            "pending": pending,
            "downloading": downloading,
            "done": done,
            "failed": failed,
            "total": len(state.state["queue"]),
        },
        "speed": {
            "current_bps": round(cur_speed),
            "instant_bps": round(instant_speed),
            "avg_bps": round(avg_speed),
            "current_mbps": round(cur_speed / 1024 / 1024, 2),
            "avg_mbps": round(avg_speed / 1024 / 1024, 2),
        },
        "timing": {
            "avg_track_sec": round(avg_track_time, 1),
            "avg_file_mb": round(avg_file_size / 1024 / 1024, 1),
            "eta_seconds": round(eta_seconds),
            "remaining_tracks": remaining,
        },
        "disk": {
            "files": file_count,
            "size_mb": round(total_size / 1024 / 1024, 1),
            "size_gb": round(total_size / 1024 / 1024 / 1024, 2),
        },
        "current": {
            "track": cur_track,
            "bytes": cur_bytes,
            "total": cur_total,
            "start": cur_start,
        },
        "recent": [{
            "track": h["track"][:40],
            "size_mb": round(h["size_bytes"] / 1024 / 1024, 1),
            "duration": h["duration_sec"],
            "source": h["source"],
            "speed_mbps": round(h["size_bytes"] / h["duration_sec"] / 1024 / 1024, 2) if h["duration_sec"] > 0 else 0,
        } for h in recent],
    })


@api.route('/api/status')
def api_status():
    with state.queue_lock:
        pending = sum(1 for q in state.state["queue"] if q["status"] == "pending")
        downloading = sum(1 for q in state.state["queue"] if q["status"] == "downloading")
        done = sum(1 for q in state.state["queue"] if q["status"] == "done")
        failed = sum(1 for q in state.state["queue"] if q["status"] == "failed")

    file_count = 0
    total_size = 0
    try:
        for root, dirs, files in os.walk(config.DOWNLOAD_DIR):
            if '.incomplete' in root:
                continue
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in config.AUDIO_EXTENSIONS:
                    file_count += 1
                    total_size += os.path.getsize(os.path.join(root, f))
    except OSError:
        pass

    from .soulseek import slsk_connected

    return jsonify({
        "running": state.state["running"],
        "paused": state.state["paused"],
        "slsk_connected": slsk_connected(),
        "sources": ["Soulseek (FLAC)", "YouTube Music", "SoundCloud", "YouTube"],
        "workers": state.active_workers["count"],
        "max_workers": config.MAX_WORKERS,
        "adaptive_workers": state.num_workers[0],
        "queue_pending": pending,
        "queue_downloading": downloading,
        "queue_done": done,
        "queue_failed": failed,
        "queue_total": len(state.state["queue"]),
        "files_on_disk": file_count,
        "disk_size_mb": round(total_size / 1024 / 1024, 1),
        "stats": state.state["stats"]
    })


@api.route('/api/queue')
def api_queue():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    filter_status = request.args.get('status', '')

    with state.queue_lock:
        items = state.state["queue"]
        if filter_status:
            items = [q for q in items if q["status"] == filter_status]
        total = len(items)
        start = (page - 1) * per_page
        items = items[start:start + per_page]

    return jsonify({
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page
    })


def _add_tracks_impl(lines):
    added = 0
    with state.queue_lock:
        existing = {q["query"] for q in state.state["queue"]}
        for line in lines:
            line = line.strip()
            if not line or ' - ' not in line:
                continue
            if line in existing:
                continue
            parts = line.split(' - ', 1)
            if len(parts) != 2:
                continue
            item = {
                "id": f"t{int(time.time()*1000)}-{added}",
                "artist": parts[0].strip(),
                "title": parts[1].strip(),
                "query": line,
                "status": "pending",
                "method": "",
                "progress": "",
                "error": "",
                "added_at": datetime.now().isoformat()
            }
            state.state["queue"].append(item)
            existing.add(line)
            state.state["stats"]["total_added"] += 1
            added += 1
    state.save_state()
    ensure_worker()
    return jsonify({"added": added, "total": len(state.state["queue"])})


@api.route('/api/add', methods=['POST'])
def api_add():
    data = request.json
    tracks = data.get('tracks', [])
    if isinstance(tracks, str):
        tracks = [tracks]
    return _add_tracks_impl(tracks)


@api.route('/api/add-file', methods=['POST'])
def api_add_file():
    text = request.data.decode('utf-8')
    lines = [l.strip() for l in text.strip().split('\n') if l.strip() and ' - ' in l.strip()]
    return _add_tracks_impl(lines)


@api.route('/api/start', methods=['POST'])
def api_start():
    state.stop_event.clear()
    state.pause_event.set()
    state.state["paused"] = False
    ensure_worker()
    return jsonify({"ok": True, "running": True})


@api.route('/api/pause', methods=['POST'])
def api_pause():
    state.pause_event.clear()
    state.state["paused"] = True
    return jsonify({"ok": True, "paused": True})


@api.route('/api/resume', methods=['POST'])
def api_resume():
    state.pause_event.set()
    state.state["paused"] = False
    ensure_worker()
    return jsonify({"ok": True, "paused": False})


@api.route('/api/stop', methods=['POST'])
def api_stop():
    state.stop_event.set()
    state.pause_event.set()
    state.state["paused"] = False
    return jsonify({"ok": True, "running": False})


@api.route('/api/retry-failed', methods=['POST'])
def api_retry_failed():
    count = 0
    with state.queue_lock:
        for q in state.state["queue"]:
            if q["status"] == "failed":
                q["status"] = "pending"
                q["progress"] = ""
                q["error"] = ""
                q["method"] = ""
                count += 1
    state.save_state()
    ensure_worker()
    return jsonify({"retried": count})


@api.route('/api/clear-done', methods=['POST'])
def api_clear_done():
    with state.queue_lock:
        state.state["queue"] = [q for q in state.state["queue"] if q["status"] != "done"]
    state.save_state()
    return jsonify({"ok": True})


@api.route('/api/remove/<item_id>', methods=['DELETE'])
def api_remove(item_id):
    with state.queue_lock:
        state.state["queue"] = [q for q in state.state["queue"] if q["id"] != item_id]
    state.save_state()
    return jsonify({"ok": True})


@api.route('/api/clear-all', methods=['POST'])
def api_clear_all():
    state.stop_event.set()
    state.pause_event.set()
    state.state["paused"] = False
    state.state["running"] = False
    with state.queue_lock:
        count = len(state.state["queue"])
        state.state["queue"] = []
    state.save_state()
    return jsonify({"ok": True, "removed": count})


@api.route('/api/workers', methods=['GET'])
def api_get_workers():
    return jsonify({"workers": state.num_workers[0], "min": config.MIN_WORKERS, "max": config.MAX_WORKERS})


@api.route('/api/workers', methods=['POST'])
def api_set_workers():
    data = request.json
    n = data.get("count", state.num_workers[0])
    state.num_workers[0] = max(config.MIN_WORKERS, min(config.MAX_WORKERS, int(n)))
    return jsonify({"workers": state.num_workers[0]})


@api.route('/api/download-dir', methods=['GET'])
def api_get_download_dir():
    return jsonify({"path": config.DOWNLOAD_DIR})


@api.route('/api/download-dir', methods=['POST'])
def api_set_download_dir():
    data = request.json
    new_path = data.get("path", "").strip()
    if not new_path:
        return jsonify({"error": "Пустой путь"}), 400
    new_path = os.path.expanduser(new_path)
    os.makedirs(new_path, exist_ok=True)
    config.DOWNLOAD_DIR = new_path
    config.STATE_FILE = os.path.join(config.DOWNLOAD_DIR, ".panel_state.json")
    cfg = config.load_config()
    cfg["download_dir"] = config.DOWNLOAD_DIR
    config.save_config(cfg)
    state.load_state()
    return jsonify({"path": config.DOWNLOAD_DIR})


@api.route('/api/import-playlist', methods=['POST'])
def api_import_playlist():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    songs_file = os.path.join(base_dir, "Песни.txt")
    if not os.path.exists(songs_file):
        songs_file = os.path.expanduser("~/Desktop/Песни.txt")
    if not os.path.exists(songs_file):
        return jsonify({"error": "Файл Песни.txt не найден (ни в папке проекта, ни на рабочем столе)"}), 404

    with open(songs_file, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip() and ' - ' in l.strip()]

    return _add_tracks_impl(lines)
