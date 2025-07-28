from flask import Flask, request, render_template, send_file, redirect, url_for, flash
import os
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
import uuid

app = Flask(__name__)
app.secret_key = "replace_with_a_secure_random_key"

DOWNLOAD_DIR = "downloads"
COOKIES_FILE = "cookies.txt"  # Make sure this file is generated from a browser

if not os.path.isdir(DOWNLOAD_DIR):
    if os.path.exists(DOWNLOAD_DIR):
        os.remove(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_yt_options(url, fmt, res, outfile):
    if fmt == "audio":
        video_format = "bestaudio[ext=m4a]/bestaudio"
        merge = None
    else:
        video_format = f"bestvideo[height<={res}]+bestaudio/best" if res else "bestvideo+bestaudio/best"
        merge = "mp4"

    return {
        "cookiefile": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        "format": video_format,
        "merge_output_format": merge,
        "outtmpl": outfile,
        "noplaylist": False,
        "quiet": True,
    }

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form["url"].strip()
        fmt = request.form["type"]
        res = request.form.get("resolution", "1080").strip() if fmt == "video" else None
        filename = f"{uuid.uuid4()}.%(ext)s"
        filepath = os.path.join(DOWNLOAD_DIR, filename)

        if not os.path.exists(COOKIES_FILE):
            flash("❌ Error: cookies.txt file not found. Please upload or generate it.", "danger")
            return redirect(url_for("index"))

        ydl_opts = get_yt_options(url, fmt, res, filepath)

        try:
            with YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=True)
                real_file = ydl.prepare_filename(result)
        except DownloadError as e:
            flash(f"❌ Download failed: {str(e)}", "danger")
            return redirect(url_for('index'))

        basename = os.path.basename(real_file)
        return redirect(url_for('download_file', filename=basename))

    return render_template("index.html")

@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(file_path):
        flash("File not found.", "danger")
        return redirect(url_for('index'))
    return send_file(file_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
