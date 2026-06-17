import concurrent.futures
import json
import logging
import os
import re
import subprocess
import threading
import time

from . import config, state, soulseek

logger = logging.getLogger(__name__)


def _clean_query(artist, title):
    q = f"{artist} - {title}"
    q = re.sub(r'\(.*?\)', '', q).strip()
    q = re.sub(r'\[.*?\]', '', q).strip()
    q = re.sub(r'\b(feat\.?|ft\.?)\b', '', q, flags=re.IGNORECASE).strip()
    q = re.sub(r'\s+', ' ', q)
    return q


def _safe_filename(query):
    return re.sub(r'[<>:"/\\|?*]', '_', query)[:200]


def _file_already_exists(query):
    safe = _safe_filename(query)
    for ext in ['mp3', 'opus', 'm4a', 'ogg', 'flac', 'wav', 'ape', 'aac']:
        if os.path.exists(os.path.join(config.DOWNLOAD_DIR, f"{safe}.{ext}")):
            return True
    q_lower = query.lower()
    try:
        for root, dirs, files in os.walk(config.DOWNLOAD_DIR):
            if '.incomplete' in root:
                continue
            for f in files:
                if q_lower.replace(' - ', ' ') in f.lower().replace(' - ', ' '):
                    return True
    except OSError:
        pass
    return False


def _find_file_size(query):
    safe = _safe_filename(query)
    for ext in ['flac', 'mp3', 'opus', 'm4a', 'ogg', 'wav', 'ape', 'aac']:
        fp = os.path.join(config.DOWNLOAD_DIR, f"{safe}.{ext}")
        if os.path.exists(fp):
            return os.path.getsize(fp)
    return 0


def probe_ytdlp(search_q, source_id, search_template, item_id):
    search_url = search_template.format(q=search_q)
    cmd = [
        "yt-dlp", "--dump-json", "--no-download", "--no-playlist",
        "--no-warnings", "--socket-timeout", "15",
        search_url
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        info = json.loads(proc.stdout.strip().split('\n')[0])

        best_abr = 0
        best_acodec = "unknown"
        for fmt in info.get("formats", []):
            abr = fmt.get("abr") or fmt.get("tbr") or 0
            if fmt.get("acodec", "none") != "none" and abr > best_abr:
                best_abr = abr
                best_acodec = fmt.get("acodec", "unknown")

        if best_abr == 0:
            best_abr = info.get("abr") or info.get("tbr") or 128
            best_acodec = info.get("acodec") or "unknown"

        score = 0
        if best_acodec in ("opus", "vorbis"):
            score = 350 + min(int(best_abr), 320)
        elif best_acodec in ("mp4a", "aac", "mp4a.40.2"):
            score = 340 + min(int(best_abr), 320)
        elif best_acodec in ("mp3",):
            score = 330 + min(int(best_abr), 320)
        else:
            score = 300 + min(int(best_abr), 256)

        return {
            "score": score,
            "source": source_id,
            "label": f"{source_id} ({best_acodec} ~{int(best_abr)}kbps)",
            "url": info.get("webpage_url") or info.get("url") or search_url,
            "title": info.get("title", ""),
            "abr": best_abr,
            "acodec": best_acodec,
        }
    except Exception as e:
        logger.debug("probe_ytdlp failed for %s: %s", source_id, e)
        return None


def _probe_sources(sources, query, item_id):
    probe_cmd = [
        "yt-dlp", "--dump-json", "--no-download", "--no-playlist",
        "--no-warnings", "--socket-timeout", "10"
    ]
    results = []
    for label, search_url in sources:
        if state.stop_event.is_set():
            break
        try:
            cmd = probe_cmd + [search_url]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if proc.returncode == 0 and proc.stdout.strip():
                info = json.loads(proc.stdout.strip().split('\n')[0])
                webpage_url = info.get("webpage_url") or info.get("url") or search_url
                title = info.get("title", "")
                logger.info("probe OK for %s: %s [%s]", label, title[:60], webpage_url[:80])
                results.append((label, webpage_url, info))
            else:
                stderr_snip = (proc.stderr or "").strip()[:100]
                logger.warning("probe FAIL for %s: rc=%s stderr=%s", label, proc.returncode, stderr_snip)
        except subprocess.TimeoutExpired:
            logger.warning("probe TIMEOUT for %s", label)
        except Exception as e:
            logger.warning("probe ERROR for %s: %s", label, e)
    return results


def download_ytdlp_direct(search_url, label, query, item_id):
    safe_name = _safe_filename(query)
    output = os.path.join(config.DOWNLOAD_DIR, f"{safe_name}.%(ext)s")

    state.update_item(item_id, progress=f"⬇ {label}: ищу и скачиваю...")

    cmd = [
        "yt-dlp", "--no-playlist",
        "--format", "bestaudio[ext=m4a]/bestaudio/best",
        "--add-metadata",
        "--output", output,
        "--socket-timeout", "15", "--retries", "2",
        "--no-warnings", "--newline",
        search_url
    ]
    if config.HAS_FFMPEG:
        cmd.insert(-1, "--concurrent-fragments")
        cmd.insert(-1, "8")
        cmd.insert(-1, "--embed-thumbnail")

    dl_real_start = None
    last_error = ""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        while True:
            if state.stop_event.is_set():
                proc.kill()
                return False, 0
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            line_stripped = line.strip()
            if 'ERROR' in line_stripped:
                last_error = line_stripped[:120]
                logger.warning("yt-dlp error [%s] for %s: %s", label, query, last_error)
            if '[download]' in line and '%' in line:
                if dl_real_start is None:
                    dl_real_start = time.time()
                match = re.search(r'(\d+\.?\d*)%', line)
                if match:
                    state.update_item(item_id, progress=f"⬇ {label}: {match.group(1)}%")
                size_match = re.search(r'of\s+~?(\d+\.?\d*)(MiB|KiB|GiB)', line)
                if size_match:
                    sz_val = float(size_match.group(1))
                    unit = size_match.group(2)
                    mult = {"KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}.get(unit, 1024**2)
                    total_b = int(sz_val * mult)
                    pct_val = float(match.group(1)) if match else 0
                    cur_b = int(total_b * pct_val / 100)
                    with state.speed_lock:
                        state.speed_data["current_bytes"] = cur_b
                        state.speed_data["current_total"] = total_b
        dl_duration = time.time() - dl_real_start if dl_real_start else 0
        if proc.returncode != 0:
            logger.warning("yt-dlp download failed [%s] for %s: rc=%s err=%s", label, query, proc.returncode, last_error)
            state.update_item(item_id, progress=f"❌ {label}: {last_error or 'ошибка загрузки'}")
        return proc.returncode == 0, dl_duration
    except Exception as e:
        logger.error("yt-dlp exception [%s] for %s: %s", label, query, e)
        state.update_item(item_id, progress=f"❌ {label}: {str(e)[:80]}")
        return False, 0


def _recalc_avg_speed():
    recent = [h for h in state.speed_data["history"] if h["duration_sec"] > 0 and h["size_bytes"] > 0]
    if not recent:
        state.speed_data["bytes_per_sec_avg"] = 0
        return
    recent = recent[-20:]
    total_bytes = sum(h["size_bytes"] for h in recent)
    total_sec = sum(h["duration_sec"] for h in recent)
    state.speed_data["bytes_per_sec_avg"] = total_bytes / total_sec if total_sec > 0 else 0


def _adapt_workers():
    with state.speed_lock:
        avg_speed = state.speed_data["bytes_per_sec_avg"]
    if avg_speed <= 0:
        return
    current_workers = state.active_workers.get("count", state.num_workers[0])
    if current_workers <= 0:
        return
    speed_per_worker = avg_speed / max(current_workers, 1)
    total_mbps = avg_speed * 8 / 1_000_000
    if total_mbps < 10 and state.num_workers[0] > config.MIN_WORKERS:
        state.num_workers[0] = max(config.MIN_WORKERS, state.num_workers[0] - 1)
    elif speed_per_worker > 500 * 1024 and state.num_workers[0] < config.MAX_WORKERS:
        state.num_workers[0] = min(config.MAX_WORKERS, state.num_workers[0] + 1)


def _track_download_stats(query, dl_duration, source):
    dl_size = _find_file_size(query)
    with state.speed_lock:
        state.speed_data["history"].append({
            "ts": time.time(),
            "size_bytes": dl_size,
            "duration_sec": round(dl_duration, 2),
            "source": source,
            "track": query
        })
        if len(state.speed_data["history"]) > 200:
            state.speed_data["history"] = state.speed_data["history"][-200:]
        _recalc_avg_speed()
        _adapt_workers()
        state.speed_data["current_start"] = None
        state.speed_data["current_track"] = ""


def _process_item(item):
    item_id = item["id"]
    artist = item["artist"]
    title = item["title"]
    query = item["query"]

    try:
        if _file_already_exists(query):
            state.update_item(item_id, status="done", method="уже есть", progress="✅ Файл уже скачан")
            with state.queue_lock:
                state.state["stats"]["downloaded"] += 1
            state.save_state()
            return

        dl_start_time = time.time()
        with state.speed_lock:
            state.speed_data["current_start"] = dl_start_time
            state.speed_data["current_track"] = query
            state.speed_data["current_bytes"] = 0
            state.speed_data["current_total"] = 0

        search_q = _clean_query(artist, title)
        downloaded = False

        slsk_result = []
        slsk_future = None
        if soulseek.slsk_connected():
            slsk_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            slsk_future = slsk_pool.submit(soulseek.probe_soulseek, artist, title, item_id, _clean_query)

        fast_sources = [
            ("YouTube Music", f"ytsearch1:{search_q} official audio"),
            ("YouTube",       f"ytsearch1:{search_q}"),
            ("SoundCloud",    f"scsearch1:{search_q}"),
        ]

        logger.info("Processing: %s (search: %s)", query, search_q)

        state.update_item(item_id, progress=f"🔍 Проверяю источники...")
        probed = _probe_sources(fast_sources, search_q, item_id)
        logger.info("Probed %d sources for: %s", len(probed), query)

        if probed:
            for label, webpage_url, info in probed:
                if state.stop_event.is_set():
                    state.update_item(item_id, status="pending", progress="")
                    return
                ok, dl_duration = download_ytdlp_direct(webpage_url, label, query, item_id)
                if ok:
                    _track_download_stats(query, dl_duration, label)
                    state.update_item(item_id, status="done", method=label, progress=f"✅ {label}")
                    with state.queue_lock:
                        state.state["stats"]["downloaded"] += 1
                    downloaded = True
                    break

        if not downloaded:
            for label, search_url in fast_sources:
                if state.stop_event.is_set():
                    state.update_item(item_id, status="pending", progress="")
                    return
                if any(p[0] == label for p in probed):
                    continue
                logger.info("Trying direct download from %s for: %s", label, query)
                ok, dl_duration = download_ytdlp_direct(search_url, label, query, item_id)
                if ok:
                    _track_download_stats(query, dl_duration, label)
                    state.update_item(item_id, status="done", method=label, progress=f"✅ {label}")
                    with state.queue_lock:
                        state.state["stats"]["downloaded"] += 1
                    downloaded = True
                    break

        if not downloaded and slsk_future:
            state.update_item(item_id, progress="🔍 Soulseek: ищу...")
            try:
                slsk_result = slsk_future.result(timeout=20)
            except Exception:
                slsk_result = []

            if slsk_result:
                for cand in slsk_result:
                    if state.stop_event.is_set():
                        state.update_item(item_id, status="pending", progress="")
                        return
                    slsk_dl_start = time.time()
                    ok = soulseek.download_soulseek(cand, query, item_id, _safe_filename, config.DOWNLOAD_DIR)
                    if ok:
                        dl_duration = time.time() - slsk_dl_start
                        _track_download_stats(query, dl_duration, "soulseek")
                        state.update_item(item_id, status="done", method=cand.get("label", "Soulseek"),
                                    progress=f"✅ Soulseek")
                        with state.queue_lock:
                            state.state["stats"]["downloaded"] += 1
                        downloaded = True
                        break

        if state.stop_event.is_set():
            state.update_item(item_id, status="pending", progress="")
            return

        if not downloaded:
            state.update_item(item_id, status="failed", progress="❌ Все источники исчерпаны")
            logger.warning("All sources exhausted for: %s", query)
            with state.queue_lock:
                state.state["stats"]["failed"] += 1

        state.save_state()

    except Exception as e:
        state.update_item(item_id, status="failed", progress=f"❌ Ошибка: {str(e)[:50]}")
        with state.queue_lock:
            state.state["stats"]["failed"] += 1
        state.save_state()


def _get_next_item():
    with state.queue_lock:
        for q in state.state["queue"]:
            if q["status"] == "pending":
                q["status"] = "downloading"
                return q.copy()
    return None


def download_worker(worker_id=0):
    with state.workers_lock:
        state.active_workers["count"] += 1
    state.state["running"] = True

    try:
        while not state.stop_event.is_set():
            state.pause_event.wait()
            if state.stop_event.is_set():
                break

            item = _get_next_item()
            if not item:
                time.sleep(0.5)
                with state.queue_lock:
                    has_pending = any(q["status"] == "pending" for q in state.state["queue"])
                if not has_pending:
                    time.sleep(1)
                    with state.queue_lock:
                        has_pending = any(q["status"] == "pending" for q in state.state["queue"])
                    if not has_pending:
                        break
                continue

            _process_item(item)
            time.sleep(0.3)
    finally:
        with state.workers_lock:
            state.active_workers["count"] -= 1
            if state.active_workers["count"] <= 0:
                state.active_workers["count"] = 0
                state.state["running"] = False


def ensure_worker():
    state.stop_event.clear()
    state.pause_event.set()
    state.state["paused"] = False

    state.worker_threads = [t for t in state.worker_threads if t.is_alive()]

    while len(state.worker_threads) < state.num_workers[0]:
        wid = len(state.worker_threads)
        t = threading.Thread(target=download_worker, args=(wid,), daemon=True)
        t.start()
        state.worker_threads.append(t)
