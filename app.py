import os
import tempfile
import json
from flask import Flask, render_template, request, jsonify, send_file, Response
import yt_dlp
import ffmpeg

app = Flask(__name__)

# Progress storage
progress_data = {}

def progress_hook(d):
    if d['status'] == 'downloading':
        progress_data[d['filename']] = {
            'downloaded': d.get('_percent_str', '0.0%').strip(),
            'speed': d.get('_speed_str', 'N/A').strip(),
            'eta': d.get('_eta_str', 'N/A').strip()
        }

@app.route("/")
def home():
    return render_template("index.html")

@app.route('/download', methods=['POST'])
def download_video():
    url = request.json.get('url')

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    temp_dir = tempfile.mkdtemp()
    output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'outtmpl': output_template,
        'progress_hooks': [progress_hook],
        'cookies': 'cookies.txt',  # Your cookies file
        'ffmpeg_location': '/usr/bin/ffmpeg',  # Render's ffmpeg path
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp4"

        return send_file(filename, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        # Cleanup temp files
        try:
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)
        except:
            pass

@app.route('/progress', methods=['GET'])
def get_progress():
    # Return latest progress info
    return jsonify(progress_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
