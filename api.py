from flask import Flask, request, send_file, jsonify
from yt_dlp import YoutubeDL
import os, uuid

app = Flask(__name__)
COOKIES = "cookies.txt"
DOWNLOADS = "downloads"

if not os.path.exists(DOWNLOADS):
    os.makedirs(DOWNLOADS)

@app.route("/api/download", methods=["POST"])
def download_video():
    data = request.get_json()
    url = data.get("url")
    fmt = data.get("format", "audio")
    res = data.get("resolution", "720")

    if not url:
        return jsonify({"error": "URL is required"}), 400

    file_id = str(uuid.uuid4())
    output_path = os.path.join(DOWNLOADS, f"{file_id}.%(ext)s")

    ydl_opts = {
        "cookiefile": COOKIES,
        "format": "bestaudio[ext=m4a]/bestaudio" if fmt == "audio" else f"bestvideo[height<={res}]+bestaudio/best",
        "merge_output_format": "mp4" if fmt == "video" else None,
        "outtmpl": output_path,
        "quiet": True,
        "noplaylist": True,
        "geo_bypass": True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
