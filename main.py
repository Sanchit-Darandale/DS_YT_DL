from flask import Flask, request, Response, send_file
from yt_dlp import YoutubeDL
import tempfile
import os
import time
import uuid
import shutil
import traceback

app = Flask(__name__)

cookies_file = './cookies.txt'
# Temporary download directory
download_root = tempfile.mkdtemp()
print(f"Temporary download folder: {download_root}")

def cleanup_old_files(root_dir, max_age=3600):
    now = time.time()
    for folder in os.listdir(root_dir):
        path = os.path.join(root_dir, folder)
        if os.path.isdir(path):
            if now - os.path.getmtime(path) > max_age:
                shutil.rmtree(path, ignore_errors=True)

@app.route("/proxy")
def proxy():
    cleanup_old_files(download_root)
    url = request.args.get("url")
    ext = request.args.get("ext", "mp3")
    filename = request.args.get("filename", str(uuid.uuid4()))

    if not url:
        return Response("Missing URL", status=400)

    is_audio = ext == "mp3"
    outdir = os.path.join(download_root, filename)
    os.makedirs(outdir, exist_ok=True)

    output_path = os.path.join(outdir, f"{filename}.%(ext)s")
    format_string = (
        "bestaudio[ext=m4a]/bestaudio"
        if is_audio
        else f"bestvideo[height<={ext}]+bestaudio/best"
    )

    ydl_opts = {
        'format': format_string,
        'outtmpl': output_path,
        'cookiefile': cookies_file,  # your attached cookie file
        'merge_output_format': 'mp4' if not is_audio else None,
        'noplaylist': False,  # enable playlist/channel support
        'quiet': True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Handle playlists
            if 'entries' in info:
                filepaths = []
                for entry in info['entries']:
                    path = ydl.prepare_filename(entry)
                    filepaths.append(path)

                # If many files, zip them
                zip_path = os.path.join(outdir, f"{filename}.zip")
                shutil.make_archive(zip_path.replace('.zip',''), 'zip', outdir)
                return send_file(zip_path, as_attachment=True)

            # Handle single video/audio
            final_file = ydl.prepare_filename(info)
            return send_file(final_file, as_attachment=True)
    except Exception as e:
        return Response(f"Error: {str(e)}\n\n{traceback.format_exc()}", status=500)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
