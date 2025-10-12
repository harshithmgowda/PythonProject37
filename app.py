from flask import Flask, render_template, request, send_file
import instaloader
import tempfile
import os
import re
import shutil

app = Flask(__name__)

# Load Instagram credentials
USERNAME = os.environ.get("IG_USERNAME")
PASSWORD = os.environ.get("IG_PASSWORD")
SESSION_FILE = "instaloader.session"


# Initialize Instaloader
def initialize_instaloader():
    if not USERNAME or not PASSWORD:
        raise Exception("❌ IG_USERNAME or IG_PASSWORD environment variable not set.")

    L = instaloader.Instaloader(
        dirname_pattern=tempfile.gettempdir(),
        filename_pattern="{shortcode}",
        download_video_thumbnails=False,
        download_comments=False,
        save_metadata=False,
        sleep=True
    )
    try:
        if os.path.exists(SESSION_FILE):
            L.load_session_from_file(USERNAME, SESSION_FILE)
        else:
            L.login(USERNAME, PASSWORD)
            L.save_session_to_file(SESSION_FILE)
    except Exception as e:
        raise Exception(f"❌ Instagram login failed: {e}")
    return L


try:
    L = initialize_instaloader()
except Exception as e:
    print(e)
    L = None


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/download', methods=['POST'])
def download_video():
    if L is None:
        return "❌ Instagram session not initialized. Check server logs.", 500

    url = request.form.get('url')
    if not url:
        return "❌ No URL provided", 400

    temp_dir = tempfile.mkdtemp()
    try:
        # Extract shortcode
        match = re.search(r"/(p|reel)/([^/?#&]+)", url)
        if not match:
            return "⚠️ Invalid Instagram URL", 400
        shortcode = match.group(2)

        # Temporarily change dirname_pattern to temp_dir
        original_dir = L.dirname_pattern
        L.dirname_pattern = temp_dir

        # Download the post
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target='')

        # Restore original directory
        L.dirname_pattern = original_dir

        # Find the video file
        video_file = None
        for f in os.listdir(temp_dir):
            if f.endswith(".mp4"):
                video_file = os.path.join(temp_dir, f)
                break

        if not video_file:
            return "⚠️ No video found. It may be a photo or private post.", 404

        return send_file(
            video_file,
            as_attachment=True,
            download_name=f"{shortcode}.mp4",
            mimetype="video/mp4"
        )

    except Exception as e:
        return f"❌ Error occurred: {e}", 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
