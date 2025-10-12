from flask import Flask, render_template, request, send_file
import instaloader
import tempfile
import os
import re
import shutil

# --- Load Instagram credentials from environment variables ---
USERNAME = os.environ.get("IG_USERNAME")
PASSWORD = os.environ.get("IG_PASSWORD")
SESSION_FILE = "instaloader.session"

# Initialize Flask
app = Flask(__name__)

# --- Initialize Instaloader globally ---
def initialize_instaloader():
    L = instaloader.Instaloader(
        dirname_pattern=tempfile.gettempdir(),  # Temp folder
        filename_pattern="{shortcode}",
        download_video_thumbnails=False,
        download_comments=False,
        save_metadata=False,
        sleep=True  # Avoid rate-limits
    )

    if USERNAME and PASSWORD:
        try:
            # Load session if exists
            if os.path.exists(SESSION_FILE):
                L.load_session_from_file(USERNAME, SESSION_FILE)
            else:
                L.login(USERNAME, PASSWORD)
                L.save_session_to_file(SESSION_FILE)
            print(f"✅ Logged in as {USERNAME}")
        except Exception as e:
            print(f"❌ Instagram login failed: {e}")

    return L

try:
    INSTALOADER_SESSION = initialize_instaloader()
except Exception as e:
    print(f"❌ Failed to initialize Instaloader: {e}")
    INSTALOADER_SESSION = None

# -------------------------------------------------------------------

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/download', methods=['POST'])
def download_video():
    if INSTALOADER_SESSION is None:
        return "❌ Server Error: Instagram not initialized. Check logs.", 500

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

        # Temp folder
        temp_dir = tempfile.mkdtemp()
        L = INSTALOADER_SESSION

        # Temporarily override dirname_pattern
        original_dir = L.dirname_pattern
        L.dirname_pattern = temp_dir

        # Download post (requires authentication)
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target='')

        L.dirname_pattern = original_dir  # Restore

        # Find the video file
        video_file = None
        for file in os.listdir(temp_dir):
            if file.endswith(".mp4"):
                video_file = os.path.join(temp_dir, file)
                break

        if not video_file:
            return "⚠️ No video found. It may be a photo or private post.", 404

        # Stream to browser (Chrome download)
        return send_file(
            video_file,
            as_attachment=True,
            download_name=f"{shortcode}.mp4",
            mimetype="video/mp4"
        )

    except instaloader.exceptions.PostNotExistsException:
        return "⚠️ Post not found or URL incorrect.", 404
    except instaloader.exceptions.QueryReturnedBadRequestException as e:
        return f"❌ Download failed: Instagram rejected the query. Error: {e}", 500
    except Exception as e:
        return f"⚠️ Unexpected error: {e}", 500
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
