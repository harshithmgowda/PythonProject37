from flask import Flask, render_template, request, send_file
import instaloader
import tempfile
import os
import re
import shutil

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_video():
    url = request.form.get('url')
    if not url:
        return "❌ No URL provided", 400

    try:
        # Extract shortcode (works for /p/.../ or /reel/.../)
        match = re.search(r"/(p|reel)/([^/?#&]+)", url)
        if not match:
            return "⚠️ Invalid Instagram URL", 400
        shortcode = match.group(2)

        # Create a temporary folder to store the file
        temp_dir = tempfile.mkdtemp()
        L = instaloader.Instaloader(
            dirname_pattern=temp_dir,
            filename_pattern=shortcode,
            download_video_thumbnails=False,
            download_comments=False,
            save_metadata=False
        )

        # Download the post into temp folder
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target='')

        # Find the downloaded .mp4 file
        video_file = None
        for file in os.listdir(temp_dir):
            if file.endswith(".mp4"):
                video_file = os.path.join(temp_dir, file)
                break

        if not video_file:
            shutil.rmtree(temp_dir)
            return "⚠️ No video file found. Maybe it's a photo or private reel.", 404

        # Send video to browser as attachment
        return send_file(
            video_file,
            as_attachment=True,
            download_name=f"{shortcode}.mp4",
            mimetype="video/mp4"
        )

    except Exception as e:
        return f"⚠️ Error: {e}", 500

if __name__ == '__main__':
    app.run(debug=True)
