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

@app.route("/")
def home():
    return render_template("index.html")
    
@app.route('/download', methods=['GET'])
def download():
    url = request.args.get('url')
    mode = request.args.get('mode', 'video').lower()
    quality = request.args.get('quality', '720')

    if not url:
        return jsonify({"error": "Missing 'url' parameter"}), 400

    # Avoid ffmpeg requirement: request a single muxed MP4 or M4A file
    if mode == 'video':
        video_format = f"best[height<={quality}][ext=mp4]"
        merge_format = None
    elif mode == 'audio':
        video_format = "bestaudio[ext=m4a]"
        merge_format = None
    else:
        return jsonify({"error": "Invalid mode. Use 'audio' or 'video'"}), 400

    # Temp output dir
    output_dir = tempfile.mkdtemp()
    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")

    ydl_opts = {
        'cookiefile': cookie_file_path,
        'format': video_format,
        'merge_output_format': merge_format,
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
    except DownloadError as e:
        return jsonify({"error": str(e)}), 500

    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    # Render will use PORT env var
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
