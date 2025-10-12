from flask import Flask, render_template, request, send_file
import requests
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

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return f"⚠️ Failed to fetch the post. Status code: {resp.status_code}", 400

        html = resp.text

        # --- Parse JSON from window.__additionalDataLoaded ---
        json_data = None
        m = re.search(r'window\.__additionalDataLoaded\(".*?",(.*)\);</script>', html)
        if m:
            json_text = m.group(1)
            json_data = json.loads(json_text)

        if not json_data:
            return "⚠️ No video data found. Instagram layout may have changed.", 404

        # Recursive function to find video_url in JSON
        def find_video_url(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ("video_url", "videoUrl"):
                        return v
                    found = find_video_url(v)
                    if found:
                        return found
            elif isinstance(obj, list):
                for item in obj:
                    found = find_video_url(item)
                    if found:
                        return found
            return None

        video_url = find_video_url(json_data)
        if not video_url:
            return "⚠️ No video found. Only public videos are supported.", 404

        # Download video
        video_resp = requests.get(video_url, stream=True)
        video_file = f"{temp_dir}/{shortcode}.mp4"
        with open(video_file, 'wb') as f:
            for chunk in video_resp.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        return send_file(
            video_file,
            as_attachment=True,
            download_name=f"{shortcode}.mp4",
            mimetype="video/mp4"
        )

    except Exception as e:
        return f"❌ Internal Server Error: {e}", 500

    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
