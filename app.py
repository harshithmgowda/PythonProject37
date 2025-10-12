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

        # Extract JSON data from <script type="application/ld+json"> or embedded JSON
        video_url = None
        json_data_match = re.search(r'window\._sharedData = (.*);</script>', html)
        if json_data_match:
            data = json.loads(json_data_match.group(1))
            try:
                # Traverse JSON to find video URL
                media = data["entry_data"]["PostPage"][0]["graphql"]["shortcode_media"]
                if media.get("is_video"):
                    video_url = media.get("video_url")
            except Exception:
                pass

        if not video_url:
            return "⚠️ No video found. Make sure the post is public and contains a video.", 404

        # Download video
        video_resp = requests.get(video_url, stream=True)
        if video_resp.status_code != 200:
            return f"⚠️ Failed to download video. Status code: {video_resp.status_code}", 500

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
