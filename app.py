from flask import Flask, render_template, request, send_file, jsonify
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
import tempfile
import os
from flask_cors import CORS

app = Flask(__name__, template_folder="templates")
CORS(app, resources={r"/*": {"origins": "*"}})

# ===== Netscape format cookies =====
cookies_text = """# Netscape HTTP Cookie File
.youtube.com	TRUE	/	FALSE	0	PREF	hl=en&tz=UTC
.youtube.com	TRUE	/	TRUE	0	SOCS	CAI
.youtube.com	TRUE	/	TRUE	0	YSC	I96mgeAGdTY
.youtube.com	TRUE	/	TRUE	1770316658	__Secure-ROLLOUT_TOKEN	CKrGnKuLz4CJORDfrejyw9-OAxj2xYvhr_6OAw%3D%3D
.youtube.com	TRUE	/	TRUE	1770316659	VISITOR_INFO1_LIVE	36-8gSkAUV0
.youtube.com	TRUE	/	TRUE	1770316659	VISITOR_PRIVACY_METADATA	CgJJThIEGgAgNA%3D%3D
.youtube.com	TRUE	/	TRUE	1817836659	__Secure-YT_TVFAS	t=487140&s=2
.youtube.com	TRUE	/	TRUE	1770316659	DEVICE_INFO	ChxOelV6TWpFd05USTBPRGN5TXpNMU5UWTROdz09EPOq3sQGGNHTncQG
.youtube.com	TRUE	/	TRUE	1754766458	GPS	1
.youtube.com	TRUE	/tv	TRUE	1787596659	__Secure-YT_DERP	CJbI56tB
"""

# Save cookies to a temp file
cookie_file_path = tempfile.NamedTemporaryFile(delete=False, suffix=".txt").name
with open(cookie_file_path, "w", encoding="utf-8") as f:
    f.write(cookies_text)

# Ensure downloads folder exists
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/download")
def download():
    url = request.args.get("url")
    mode = request.args.get("mode", "video").lower()
    quality = request.args.get("quality", "480p")

    if not url:
        return jsonify({"error": "Missing 'url' parameter"}), 400

    # Choose yt-dlp options
    if mode == "audio":
        ydl_opts = {
            "format": "bestaudio/best",
            "cookiefile": cookie_file_path,
            "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
    else:
        ydl_opts = {
            "format": f"bestvideo[height={quality}]+bestaudio/best[height={quality}]",
            "cookiefile": cookie_file_path,
            "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
            "merge_output_format": "mp4",
        }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            # Get the actual final file path from yt-dlp
            if "requested_downloads" in info_dict and info_dict["requested_downloads"]:
                final_path = info_dict["requested_downloads"][0]["filepath"]
            else:
                final_path = ydl.prepare_filename(info_dict)

            if mode == "audio" and not final_path.endswith(".mp3"):
                base, _ = os.path.splitext(final_path)
                final_path = base + ".mp3"

        # Serve the file
        return send_file(final_path, as_attachment=True)

    except DownloadError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
