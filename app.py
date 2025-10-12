from flask import Flask, render_template, request, send_file
import requests
import os
import tempfile
import shutil
import re
import json

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_video():
    url = request.form.get('url')
    if not url:
        return "❌ No URL provided", 400

    temp_dir = None
    try:
        # Extract shortcode
        match = re.search(r"/(p|reel)/([^/?#&]+)", url)
        if not match:
            return "⚠️ Invalid Instagram URL", 400
        shortcode = match.group(2)

        # Create temp folder
        temp_dir = tempfile.mkdtemp()

        # Fetch post HTML
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return "⚠️ Failed to fetch the Instagram post. Make sure it's public.", 400

        html = resp.text

        # Extract video URL from JSON in the page
        video_url = None
        m = re.search(r'"video_url":"([^"]+)"', html)
        if m:
            video_url = m.group(1).replace("\\u0026", "&")  # unescape &

        if not video_url:
            return "⚠️ No video found. Only public videos are supported.", 404

        # Download video to temp file
        video_resp = requests.get(video_url, stream=True)
        video_file = os.path.join(temp_dir, f"{shortcode}.mp4")
        with open(video_file, 'wb') as f:
            for chunk in video_resp.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        # Send file to browser (Chrome download bar)
        return send_file(
            video_file,
            as_attachment=True,
            download_name=f"{shortcode}.mp4",
            mimetype="video/mp4"
        )

    except Exception as e:
        return f"⚠️ An unexpected error occurred: {e}", 500
    finally:
        # Clean up temp folder after request
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
