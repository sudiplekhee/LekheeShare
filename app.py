import os
import random
import sqlite3
import string
import uuid
from datetime import datetime, timedelta

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename


# =========================================================
# Flask Application
# =========================================================

app = Flask(__name__)

app.secret_key = "your-secret-key-here"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.config.update(
    UPLOAD_FOLDER=os.path.join(BASE_DIR, "uploads"),
    DB_NAME=os.path.join(BASE_DIR, "lekshare.db"),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB
)


# =========================================================
# Allowed File Types
# =========================================================

ALLOWED_EXTENSIONS = {
    "txt",
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "mp4",
    "doc",
    "docx",
}

TEXT_EXTENSIONS = {
    "txt",
}

IMAGE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
}


# Create uploads folder if it doesn't exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# =========================================================
# Database
# =========================================================

def get_db_connection():
    """Create and return a SQLite database connection."""
    connection = sqlite3.connect(app.config["DB_NAME"])
    return connection


def init_db():
    """Create the shares table if it doesn't exist."""

    with get_db_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shares (
                id TEXT PRIMARY KEY,
                share_code TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                view_count INTEGER DEFAULT 0
            )
            """
        )

        conn.commit()


# =========================================================
# Share Code
# =========================================================

def generate_share_code():
    """Generate a unique 6-character share code."""

    characters = string.ascii_uppercase + string.digits

    while True:

        code = "".join(
            random.choices(characters, k=6)
        )

        with get_db_connection() as conn:

            existing = conn.execute(
                "SELECT 1 FROM shares WHERE share_code = ?",
                (code,),
            ).fetchone()

        if existing is None:
            return code


# =========================================================
# File Helpers
# =========================================================

def allowed_file(filename):
    """Check whether the uploaded file has an allowed extension."""

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def get_file_type(extension):
    """Determine how the file should be displayed."""

    extension = extension.lower()

    if extension in TEXT_EXTENSIONS:
        return "text"

    if extension in IMAGE_EXTENSIONS:
        return "image"

    return "file"


# =========================================================
# Database Share Functions
# =========================================================

def create_share(
    filename,
    original_name,
    file_type,
):
    """Create a share record and return its ID and share code."""

    share_id = str(uuid.uuid4())[:8]

    share_code = generate_share_code()

    created_at = datetime.now()

    expires_at = created_at + timedelta(days=7)

    with get_db_connection() as conn:

        conn.execute(
            """
            INSERT INTO shares (
                id,
                share_code,
                filename,
                original_name,
                file_type,
                created_at,
                expires_at,
                view_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                share_id,
                share_code,
                filename,
                original_name,
                file_type,
                created_at,
                expires_at,
            ),
        )

        conn.commit()

    return share_id, share_code


def get_share_by_id(share_id):
    """Find a share using its ID."""

    with get_db_connection() as conn:

        return conn.execute(
            "SELECT * FROM shares WHERE id = ?",
            (share_id,),
        ).fetchone()


def get_share_by_code(share_code):
    """Find a share using its share code."""

    with get_db_connection() as conn:

        return conn.execute(
            "SELECT * FROM shares WHERE share_code = ?",
            (share_code,),
        ).fetchone()


def increment_view_count(
    share_id=None,
    share_code=None,
):
    """Increase the view count of a shared file."""

    with get_db_connection() as conn:

        if share_id:

            conn.execute(
                """
                UPDATE shares
                SET view_count = view_count + 1
                WHERE id = ?
                """,
                (share_id,),
            )

        elif share_code:

            conn.execute(
                """
                UPDATE shares
                SET view_count = view_count + 1
                WHERE share_code = ?
                """,
                (share_code,),
            )

        conn.commit()


# =========================================================
# Render Shared File
# =========================================================

def render_share(share):
    """Display a shared file according to its type."""

    filename = share[2]
    original_name = share[3]
    file_type = share[4]

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename,
    )

    # Check if file exists
    if not os.path.exists(file_path):
        return render_template("404.html"), 404

    # Text file
    if file_type == "text":

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8",
            ) as file:

                content = file.read()

        except UnicodeDecodeError:

            return render_template("404.html"), 404

        return render_template(
            "view_text.html",
            content=content,
            filename=original_name,
        )

    # Image file
    if file_type == "image":

        return render_template(
            "view_image.html",
            filename=filename,
            original_name=original_name,
        )

    # Other files
    return render_template(
        "download_file.html",
        filename=filename,
        original_name=original_name,
    )


# =========================================================
# Home Page
# =========================================================

@app.route("/")
def index():
    """Display the home page."""

    return render_template("index.html")


# =========================================================
# Upload File
# =========================================================

@app.route("/share", methods=["POST"])
def share():
    """Upload a file and create a share."""

    if "file" not in request.files:

        flash("No file selected")

        return redirect(url_for("index"))

    file = request.files["file"]

    if not file.filename:

        flash("No file selected")

        return redirect(url_for("index"))

    if not allowed_file(file.filename):

        flash("File type not allowed")

        return redirect(url_for("index"))

    # Clean original filename
    original_name = secure_filename(file.filename)

    if not original_name:

        flash("Invalid filename")

        return redirect(url_for("index"))

    # Get extension
    extension = original_name.rsplit(
        ".",
        1,
    )[1].lower()

    # Generate temporary unique filename
    unique_id = str(uuid.uuid4())[:8]

    unique_filename = (
        f"{unique_id}.{extension}"
    )

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        unique_filename,
    )

    # Save uploaded file
    file.save(file_path)

    # Determine file type
    file_type = get_file_type(extension)

    # Create database share
    share_id, share_code = create_share(
        filename=unique_filename,
        original_name=original_name,
        file_type=file_type,
    )

    # Create share URL
    share_url = (
        request.host_url
        + f"s/{share_id}"
    )

    return render_template(
        "share_success.html",
        share_url=share_url,
        share_code=share_code,
        file_type=file_type,
    )


# =========================================================
# View Share Using ID
# =========================================================

@app.route("/s/<share_id>")
def view_share(share_id):
    """Open a shared file using its share ID."""

    share = get_share_by_id(share_id)

    if not share:

        return render_template(
            "404.html"
        ), 404

    # Increase view count
    increment_view_count(
        share_id=share_id
    )

    return render_share(share)


# =========================================================
# View Share Using Code
# =========================================================

@app.route("/code/<share_code>")
def view_by_code(share_code):
    """Open a shared file using its share code."""

    share_code = (
        share_code
        .strip()
        .upper()
    )

    share = get_share_by_code(
        share_code
    )

    if not share:

        return render_template(
            "404.html"
        ), 404

    # Increase view count
    increment_view_count(
        share_code=share_code
    )

    return render_share(share)


# =========================================================
# Download File
# =========================================================

@app.route("/download/<filename>")
def download_file(filename):
    """Download a shared file."""

    with get_db_connection() as conn:

        share = conn.execute(
            """
            SELECT original_name
            FROM shares
            WHERE filename = ?
            """,
            (filename,),
        ).fetchone()

    if not share:

        return render_template(
            "404.html"
        ), 404

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename,
    )

    if not os.path.exists(file_path):

        return render_template(
            "404.html"
        ), 404

    return send_file(
        file_path,
        as_attachment=True,
        download_name=share[0],
    )


# =========================================================
# Share Text
# =========================================================

@app.route("/text", methods=["GET", "POST"])
def share_text():
    """Create and share a text file."""

    # Show text sharing page
    if request.method == "GET":

        return render_template(
            "share_text.html"
        )

    # Get text
    text_content = request.form.get(
        "text_content",
        "",
    ).strip()

    if not text_content:

        flash("Please enter some text")

        return redirect(
            url_for("share_text")
        )

    # Generate unique filename
    unique_id = str(
        uuid.uuid4()
    )[:8]

    filename = f"{unique_id}.txt"

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename,
    )

    # Save text
    with open(
        file_path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(text_content)

    # Create share
    share_id, share_code = create_share(
        filename=filename,
        original_name="text_share.txt",
        file_type="text",
    )

    # Create URL
    share_url = (
        request.host_url
        + f"s/{share_id}"
    )

    return render_template(
        "share_success.html",
        share_url=share_url,
        share_code=share_code,
        file_type="text",
    )


# =========================================================
# Access File Using Share Code
# =========================================================

@app.route("/access", methods=["GET", "POST"])
def access_file():
    """Find a shared file using its share code."""

    if request.method == "GET":

        return render_template(
            "access_file.html"
        )

    share_code = request.form.get(
        "share_code",
        "",
    ).strip().upper()

    if not share_code:

        flash("Please enter a share code")

        return redirect(
            url_for("access_file")
        )

    share = get_share_by_code(
        share_code
    )

    if not share:

        flash("Invalid share code")

        return redirect(
            url_for("access_file")
        )

    return redirect(
        url_for(
            "view_by_code",
            share_code=share_code,
        )
    )


# =========================================================
# Initialize Database
# =========================================================

init_db()


# =========================================================
# Run Application Locally
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
    )