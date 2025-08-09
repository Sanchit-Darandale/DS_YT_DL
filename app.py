# app.py
import os
import time
import uuid
import json
import shutil
import tempfile
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, Response
from flask_cors import CORS
import yt_dlp

app = Flask(__name__, template_folder="templates")
CORS(app, resources={r"/*": {"origins": "*"}}) 
downloads = {}
DOWNLOAD_TTL_SECONDS = 60 * 15  # keep finished files for 15 minutes

def cleanup_download(download_id):
    info = downloads.get(download_id)
    if not info:
        return
    temp_dir = info.get("temp_dir")
    try:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass
    downloads.pop(download_id, None)


def cleaner_loop():
    """Background cleaner thread to remove stale downloads."""
    while True:
        now = datetime.utcnow()
        to_delete = []
        for did, info in list(downloads.items()):
            created = info.get("created_at")
            if not created:
                continue
            age = (now - created).total_seconds()
            # delete if older than TTL or if status == served and older than 60s
            if age > DOWNLOAD_TTL_SECONDS or (info.get("status") == "served" and age > 60):
                to_delete.append(did)
        for did in to_delete:
            cleanup_download(did)
        time.sleep(30)

cleaner_thread = threading.Thread(target=cleaner_loop, daemon=True)
cleaner_thread.start()


def make_progress_hook(download_id):
    def hook(d):
        info = downloads.get(download_id)
        if not info:
            return
        status = d.get("status")
        if status == "downloading":
            # prefer _percent_str if present
            pct = d.get("_percent_str")
            if pct:
                try:
                    pct_val = float(pct.strip().replace("%", ""))
                except Exception:
                    pct_val = None
            else:
                # fallback calculation
                try:
                    dl = d.get("downloaded_bytes") or d.get("downloaded_bytes", 0)
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or None
                    if total:
                        pct_val = (dl / total) * 100.0 if total > 0 else 0.0
                    else:
                        pct_val = None
                except Exception:
                    pct_val = None

            info["status"] = "downloading"
            if pct_val is not None:
                info["percent"] = round(pct_val, 2)
            info["eta"] = d.get("_eta_str") or d.get("eta")
            info["speed"] = d.get("_speed_str") or d.get("speed")
        elif status == "finished":
            # When finished, yt-dlp provides "filename" in d
            info["status"] = "finished"
            # filename may be in d or we can scan temp_dir
            filename = d.get("filename")
            if filename and os.path.exists(filename):
                info["filepath"] = filename
            else:
                # fallback: find the largest media file in temp_dir
                temp_dir = info.get("temp_dir")
                if temp_dir and os.path.exists(temp_dir):
                    candidates = []
                    for root, _, files in os.walk(temp_dir):
                        for f in files:
                            if f.lower().endswith((".mp4", ".m4a", ".webm", ".mkv", ".mp3")):
                                candidates.append(os.path.join(root, f))
                    if candidates:
                        # pick largest
                        candidates.sort(key=lambda p: os.path.getsize(p), reverse=True)
                        info["filepath"] = candidates[0]
            info["percent"] = 100.0
    return hook


def download_worker(download_id, url, mode, quality):
    downloads[download_id]["status"] = "queued"
    temp_dir = downloads[download_id]["temp_dir"]
    outtmpl = os.path.join(temp_dir, "%(title)s.%(ext)s")

    # Choose format to avoid the need for ffmpeg merging on server
    if mode == "video":
        # prefer mp4 muxed streams; fallback to best
        try:
            q_int = int(quality)
        except Exception:
            q_int = 720
        fmt = f"best[height<={q_int}][ext=mp4]/best"
    else:
        # audio: prefer m4a (widely supported)
        fmt = "bestaudio[ext=m4a]/bestaudio"

    ydl_opts = {
        "format": fmt,
        "outtmpl": outtmpl,
        "noplaylist": True,
        "geo_bypass": True,
        "progress_hooks": [make_progress_hook(download_id)],
        "quiet": True,
        # add cookiefile if present in project root
    }

    # add cookiefile if exists
    if os.path.exists("cookies.txt"):
        ydl_opts["cookiefile"] = "cookies.txt"

    try:
        downloads[download_id]["status"] = "downloading"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # download (blocks inside thread)
            info = ydl.extract_info(url, download=True)
            # prepare_filename gives the expected file path
            try:
                path = ydl.prepare_filename(info)
            except Exception:
                path = None
        # locate final file (prefer 'path' if exists)
        final_path = None
        if path and os.path.exists(path):
            final_path = path
        else:
            # scan temp_dir for typical media files
            candidates = []
            for root, _, files in os.walk(temp_dir):
                for f in files:
                    if f.lower().endswith((".mp4", ".m4a", ".webm", ".mkv", ".mp3")):
                        candidates.append(os.path.join(root, f))
            if candidates:
                candidates.sort(key=lambda p: os.path.getsize(p) if os.path.exists(p) else 0, reverse=True)
                final_path = candidates[0]
        if final_path:
            downloads[download_id]["filepath"] = final_path
            downloads[download_id]["status"] = "finished"
            downloads[download_id]["percent"] = 100.0
        else:
            downloads[download_id]["status"] = "error"
            downloads[download_id]["error"] = "Download finished but file not found."
    except Exception as e:
        downloads[download_id]["status"] = "error"
        downloads[download_id]["error"] = str(e)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/download", methods=["POST"])
def start_download():
    data = request.get_json(force=True, silent=True) or {}
    url = data.get("url")
    mode = (data.get("mode") or "video").lower()
    quality = data.get("quality") or "720"

    if not url:
        return jsonify({"error": "No URL provided"}), 400
    if mode not in ("video", "audio"):
        return jsonify({"error": "Invalid mode, use 'video' or 'audio'"}), 400

    download_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp(prefix=f"dl_{download_id}_")
    downloads[download_id] = {
        "status": "queued",
        "temp_dir": temp_dir,
        "filepath": None,
        "percent": 0.0,
        "eta": None,
        "speed": None,
        "error": None,
        "created_at": datetime.utcnow(),
    }

    # spawn background thread to perform download
    t = threading.Thread(target=download_worker, args=(download_id, url, mode, quality), daemon=True)
    t.start()

    return jsonify({"download_id": download_id})


@app.route("/progress/<download_id>")
def progress_sse(download_id):
    def event_stream():
        # SSE: send current state every 1s until finished/error
        while True:
            info = downloads.get(download_id)
            if not info:
                # send a small keepalive and exit
                yield f"data: {json.dumps({'status':'error','error':'download_id not found'})}\n\n"
                break

            state = {
                "status": info.get("status"),
                "percent": info.get("percent"),
                "eta": info.get("eta"),
                "speed": info.get("speed"),
            }

            # send as JSON string
            yield f"data: {json.dumps(state)}\n\n"

            if info.get("status") in ("finished", "error"):
                # final message: if finished include file field
                if info.get("status") == "finished" and info.get("filepath"):
                    yield f"data: {json.dumps({'file': True})}\n\n"
                break
            time.sleep(1)

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"  # disable buffering on some proxies
    }
    return Response(event_stream(), headers=headers)

@app.route("/file/<download_id>")
def get_file(download_id):
    info = downloads.get(download_id)
    if not info:
        return jsonify({"error": "download_id not found"}), 404
    if info.get("status") != "finished" or not info.get("filepath"):
        return jsonify({"error": "file not ready"}), 404

    path = info["filepath"]
    if not os.path.exists(path):
        return jsonify({"error": "file missing on server"}), 404

    # schedule cleanup after send (daemon thread)
    def delayed_cleanup(did, delay=30):
        time.sleep(delay)
        downloads.get(did) and cleanup_download(did)

    threading.Thread(target=delayed_cleanup, args=(download_id,), daemon=True).start()

    # mark served
    info["status"] = "served"
    return send_file(path, as_attachment=True)

# healthcheck
@app.route("/healthz")
def health():
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
