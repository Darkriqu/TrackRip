#!/usr/bin/env python3
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("trackrip")

from flask import Flask

from tracker import config, state
from tracker.api import api
from tracker.downloader import ensure_worker

config.detect_ffmpeg()
os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
state.load_state()

app = Flask(__name__, static_folder='static', static_url_path='')
app.register_blueprint(api)

if __name__ == '__main__':
    logger.info("TrackRip starting on http://localhost:8844")
    logger.info("Download dir: %s", config.DOWNLOAD_DIR)
    logger.info("FFmpeg: %s", "found" if config.HAS_FFMPEG else "not found")
    app.run(host='0.0.0.0', port=8844, debug=False)
