import json
import logging
import os
import time
import urllib.parse
import urllib.request

from . import config, state

logger = logging.getLogger(__name__)


def slskd_api(endpoint, method="GET", data=None):
    url = f"{config.SLSKD_URL}/{endpoint}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        body = resp.read().decode()
        return json.loads(body) if body.strip() else {}
    except Exception as e:
        logger.debug("slskd_api %s failed: %s", endpoint, e)
        return None


def slsk_connected():
    s = slskd_api("server")
    return s and s.get("isLoggedIn", False)


def score_file(file_info, user_info):
    filename = file_info.get("filename", "").lower()
    ext = os.path.splitext(filename)[1]
    if ext not in config.AUDIO_EXTENSIONS:
        return -1
    bitrate = file_info.get("bitRate", 0) or 0
    speed = user_info.get("uploadSpeed", 0) or 0
    free = user_info.get("hasFreeUploadSlot", False)
    size = file_info.get("size", 0) or 0

    score = 0
    if ext == '.flac':
        score += 1000
    elif ext == '.wav':
        score += 900
    elif ext == '.ape':
        score += 850
    elif ext == '.mp3':
        score += 400 + min(bitrate, 320)
    elif ext in ('.ogg', '.opus'):
        score += 350 + min(bitrate, 320)
    elif ext == '.m4a':
        score += 350 + min(bitrate, 320)
    elif ext == '.aac':
        score += 300 + min(bitrate, 320)
    else:
        score += 200
    if free:
        score += 200
    if speed > 0:
        score += min(int(speed / 1024 / 10), 100)
    if size > 0:
        mb = size / 1024 / 1024
        if 2 < mb < 100:
            score += min(int(mb * 3), 80)
    return score


def probe_soulseek(artist, title, item_id, clean_query_fn):
    query = clean_query_fn(artist, title)
    result = slskd_api("searches", method="POST", data={"searchText": query})
    if not result:
        return []
    search_id = result.get("id")
    if not search_id:
        return []

    try:
        for _ in range(config.SEARCH_TIMEOUT):
            if state.stop_event.is_set():
                return []
            time.sleep(1)

        results = slskd_api(f"searches/{search_id}?includeResponses=true")
        if not results:
            return []

        candidates = []
        for resp in results.get("responses", []):
            ui = {
                "uploadSpeed": resp.get("uploadSpeed", 0),
                "hasFreeUploadSlot": resp.get("hasFreeUploadSlot", False)
            }
            for f in resp.get("files", []):
                s = score_file(f, ui)
                if s > 0:
                    ext = os.path.splitext(f.get("filename", ""))[1].lower()
                    bitrate = f.get("bitRate", 0) or 0
                    size_mb = round((f.get("size", 0) or 0) / 1024 / 1024, 1)
                    candidates.append({
                        "score": s,
                        "source": "soulseek",
                        "label": f"Soulseek ({ext} {bitrate}kbps {size_mb}MB)",
                        "username": resp.get("username", ""),
                        "file_info": f,
                    })
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:5]
    finally:
        slskd_api(f"searches/{search_id}", method="DELETE")


def download_soulseek(candidate, query, item_id, safe_filename_fn, download_dir):
    username = candidate["username"]
    file_info = candidate["file_info"]
    filename = file_info.get("filename", "")
    eu = urllib.parse.quote(username, safe='')

    existing_files = set()
    for root, dirs, files in os.walk(download_dir):
        if '.incomplete' in root:
            continue
        for f in files:
            existing_files.add(os.path.join(root, f))

    state.update_item(item_id, progress=f"⬇ Soulseek: качаю от {username}...")
    dl = slskd_api(f"transfers/downloads/{eu}", method="POST", data=[file_info])
    if dl is None:
        return False

    start = time.time()
    last_bytes = 0
    stall = 0
    while time.time() - start < config.DOWNLOAD_TIMEOUT:
        if state.stop_event.is_set():
            return False
        transfers = slskd_api(f"transfers/downloads/{eu}")
        if transfers:
            if isinstance(transfers, dict):
                transfers = [transfers]
            for ub in transfers:
                for di in ub.get("directories", []):
                    for tf in di.get("files", []):
                        if tf.get("filename") == filename:
                            st = tf.get("state", "")
                            bt = tf.get("bytesTransferred", 0)
                            sz = tf.get("size", 1) or 1
                            pct = int(bt / sz * 100)
                            state.update_item(item_id, progress=f"⬇ Soulseek: {pct}% от {username}")
                            with state.speed_lock:
                                state.speed_data["current_bytes"] = bt
                                state.speed_data["current_total"] = sz
                            if "Succeeded" in st:
                                time.sleep(1)
                                _move_new_soulseek_file(existing_files, query, safe_filename_fn, download_dir)
                                return True
                            if any(x in st for x in ("Errored", "Rejected", "Cancelled", "TimedOut")):
                                return False
                            if bt > last_bytes:
                                last_bytes = bt
                                stall = 0
                            else:
                                stall += 1
                            if stall > 10:
                                return False
        time.sleep(config.DOWNLOAD_CHECK_INTERVAL)
    return False


def _move_new_soulseek_file(existing_files, query, safe_filename_fn, download_dir):
    import shutil
    safe = safe_filename_fn(query)
    for root, dirs, files in os.walk(download_dir):
        if root == download_dir or '.incomplete' in root:
            continue
        for f in files:
            fp = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            if ext in config.AUDIO_EXTENSIONS and fp not in existing_files:
                dst = os.path.join(download_dir, f"{safe}{ext}")
                if not os.path.exists(dst):
                    try:
                        shutil.move(fp, dst)
                    except OSError as e:
                        logger.warning("Failed to move %s: %s", fp, e)
    for d in os.listdir(download_dir):
        dp = os.path.join(download_dir, d)
        if os.path.isdir(dp) and d != '.incomplete':
            try:
                if not os.listdir(dp):
                    os.rmdir(dp)
            except OSError:
                pass
