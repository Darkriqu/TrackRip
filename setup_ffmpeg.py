#!/usr/bin/env python3
"""Download ffmpeg for Windows if not present."""
import glob
import os
import shutil
import sys
import urllib.request
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG_DIR = os.path.join(BASE_DIR, "ffmpeg")


def main():
    if shutil.which("ffmpeg"):
        print("[OK] ffmpeg found in PATH")
        return 0

    if os.path.isfile(os.path.join(FFMPEG_DIR, "ffmpeg.exe")):
        print("[OK] ffmpeg found in ./ffmpeg/")
        return 0

    print("[*] Downloading ffmpeg...")
    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    zip_path = os.path.join(BASE_DIR, "ffmpeg.zip")
    tmp_dir = os.path.join(BASE_DIR, "ffmpeg_tmp")

    try:
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if 'bin/ffmpeg.exe' in name or 'bin/ffprobe.exe' in name:
                    zf.extract(name, tmp_dir)

        os.makedirs(FFMPEG_DIR, exist_ok=True)
        for exe in glob.glob(os.path.join(tmp_dir, "*", "bin", "*.exe")):
            dst = os.path.join(FFMPEG_DIR, os.path.basename(exe))
            os.rename(exe, dst)
            print(f"  -> {dst}")

        shutil.rmtree(tmp_dir, ignore_errors=True)
        os.remove(zip_path)
        print("[OK] ffmpeg downloaded to ./ffmpeg/")
        return 0
    except Exception as e:
        print(f"[ERROR] Failed to download ffmpeg: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
