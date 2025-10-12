from flask import Flask, render_template, request, send_file
import instaloader
import tempfile
import os
import re
import shutil

# --- ADDED: Load Credentials from Environment Variables ---
USERNAME = os.environ.get("IG_USERNAME")
PASSWORD = os.environ.get("IG_PASSWORD")
SESSION_FILE = "instaloader.session"  # Name for the session file

# Initialize Flask app
app = Flask(__name__)


# --- ADDED: Global Instaloader Initialization and Login Function ---
def initialize_instaloader():
    L = instaloader.Instaloader(
        dirname_pattern=tempfile.gettempdir(),  # Use system temp directory for Instaloader files
        filename_pattern="{shortcode}",
        download_video_thumbnails=False,
        download_comments=False,
        save_metadata=False,
        # Set a sleep time to appear less like a bot (optional but recommended)
        sleep=True
    )

    if USERNAME and PASSWORD:
        try:
            # 1. Try to load saved session (won't work on first run/new container)
            # You might need persistent storage (S3/Render Disk) for this to fully work
            if os.path.exists(SESSION_FILE):
                L.load_session_from_file(USERNAME, SESSION_FILE)
            else:
                # 2. Log in and save session if no session file exists
                L.login(USERNAME, PASSWORD)
                L.save_session_to_file(SESSION_FILE)
            print(f"Instaloader session initialized for {USERNAME}")
        except Exception as e:
            # IMPORTANT: If login fails, you MUST report it and halt the function.
            print(f"Instaloader Login Failed: {e}")
            # The 401 Unauthorized error usually occurs here if login fails.

    return L


# Initialize Instaloader globally when the app starts
try:
    INSTALOADER_SESSION = initialize_instaloader()
except Exception as e:
    # Handle critical error if initialization fails
    print(f"CRITICAL ERROR initializing Instaloader: {e}")
    INSTALOADER_SESSION = None


# -------------------------------------------------------------------

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/download', methods=['POST'])
def download_video():
    # --- ADDED: Check if Instaloader initialized successfully ---
    if INSTALOADER_SESSION is None:
        return "❌ Server Error: Instagram initialization failed. Check logs.", 500

    url = request.form.get('url')
    if not url:
        return "❌ No URL provided", 400

    temp_dir = None
    try:
        # Extract shortcode (works for /p/.../ or /reel/.../)
        match = re.search(r"/(p|reel)/([^/?#&]+)", url)
        if not match:
            return "⚠️ Invalid Instagram URL", 400
        shortcode = match.group(2)

        # Create a temporary folder to store the file
        temp_dir = tempfile.mkdtemp()

        # --- MODIFIED: Use the global, initialized Instaloader instance ---
        L = INSTALOADER_SESSION

        # NOTE: We temporarily change the dirname_pattern to the specific temp_dir for this request
        original_dirname_pattern = L.dirname_pattern
        L.dirname_pattern = temp_dir

        # Download the post. This requires authentication.
        # This is the line that previously failed with 401 Unauthorized.
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target='')

        # Restore the original dirname_pattern
        L.dirname_pattern = original_dirname_pattern

        # Find the downloaded .mp4 file
        video_file = None
        for file in os.listdir(temp_dir):
            if file.endswith(".mp4"):
                video_file = os.path.join(temp_dir, file)
                break

        if not video_file:
            # If no file is found, it's likely a photo or the post is private
            return "⚠️ No video file found. Maybe it's a photo or private post.", 404

        # Send video to browser as attachment
        # NOTE: We return the response *before* deleting the temp_dir to allow Flask to read the file.
        response = send_file(
            video_file,
            as_attachment=True,
            download_name=f"{shortcode}.mp4",
            mimetype="video/mp4"
        )
        return response

    except instaloader.exceptions.PostNotExistsException:
        return "⚠️ Post not found or URL is incorrect.", 404
    except instaloader.exceptions.QueryReturnedBadRequestException as e:
        # This exception often contains the original 401 unauthorized message
        return f"❌ Download Failed: Query rejected by Instagram (check authentication/rate limits). Error: {e}", 500
    except Exception as e:
        return f"⚠️ An unexpected error occurred: {e}", 500
    finally:
        # --- ADDED: Clean up the temp directory after the download/error ---
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


if __name__ == '__main__':
    # Use 0.0.0.0 and PORT env var for Render deployment
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)