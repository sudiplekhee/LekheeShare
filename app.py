import os
import random
import sqlite3
import string
import uuid
from datetime import datetime, timedelta

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename


app = Flask(__name__)

app.secret_key = "your-secret-key-here"  # Change this in production.
app.config.update(
    UPLOAD_FOLDER="uploads",
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB
    DB_NAME="lekshare.db",
)

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

TEXT_EXTENSIONS = {"txt"}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def get_db_connection():
    """Create and return a SQLite database connection."""
    return sqlite3.connect(app.config["DB_NAME"])


def generate_share_code():
    """Generate a unique 6-character share code."""
    characters = string.ascii_uppercase + string.digits

    while True:
        code = "".join(random.choices(characters, k=6))

        with get_db_connection() as conn:
            exists = conn.execute(
                "SELECT 1 FROM shares WHERE share_code = ?",
                (code,),
            ).fetchone()

        if not exists:
            return code


def init_db():
    """Create the shares table if it does not already exist."""
    with get_db_connection() as conn:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name = 'shares'"
        ).fetchone()

        if not table_exists:
            conn.execute(
                """
                CREATE TABLE shares (
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


def allowed_file(filename):
    """Return True when the filename has an allowed extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def get_file_type(extension):
    """Return the application file type used by the templates."""
    extension = extension.lower()

    if extension in TEXT_EXTENSIONS:
        return "text"

    if extension in IMAGE_EXTENSIONS:
        return "image"

    return "file"


def create_share(filename, original_name, file_type):
    """Store share information and return its ID and share code."""
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
                expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
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

    return share_id, share_code


def get_share_by_id(share_id):
    """Get a share record by its ID."""
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT * FROM shares WHERE id = ?",
            (share_id,),
        ).fetchone()


def get_share_by_code(share_code):
    """Get a share record by its share code."""
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT * FROM shares WHERE share_code = ?",
            (share_code,),
        ).fetchone()


def render_share(share):
    """Render a share according to its stored file type."""
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], share[2])

    if not os.path.exists(file_path):
        return render_template("404.html"), 404

    if share[4] == "text":
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        return render_template(
            "view_text.html",
            content=content,
            filename=share[3],
        )

    if share[4] == "image":
        return render_template(
            "view_image.html",
            filename=share[2],
            original_name=share[3],
        )

    return render_template(
        "download_file.html",
        filename=share[2],
        original_name=share[3],
    )


def increment_view_count(share_id=None, share_code=None):
    """Increment the view count for a share."""
    if share_id is not None:
        query = "UPDATE shares SET view_count = view_count + 1 WHERE id = ?"
        value = share_id
    else:
        query = (
            "UPDATE shares SET view_count = view_count + 1 "
            "WHERE share_code = ?"
        )
        value = share_code

    with get_db_connection() as conn:
        conn.execute(query, (value,))


@app.route("/")
def index():
    """Display the home page."""
    return render_template("index.html")


@app.route("/share", methods=["POST"])
def share():
    """Upload a file and create a share link."""
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

    original_name = secure_filename(file.filename)
    extension = original_name.rsplit(".", 1)[1].lower()
    share_id = str(uuid.uuid4())[:8]
    unique_filename = f"{share_id}.{extension}"

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        unique_filename,
    )
    file.save(file_path)

    file_type = get_file_type(extension)
    share_id, share_code = create_share(
        unique_filename,
        original_name,
        file_type,
    )

    share_url = request.host_url + f"s/{share_id}"

    return render_template(
        "share_success.html",
        share_url=share_url,
        share_code=share_code,
        file_type=file_type,
    )


@app.route("/s/<share_id>")
def view_share(share_id):
    """Open a shared file using its share ID."""
    share = get_share_by_id(share_id)

    if not share:
        return render_template("404.html"), 404

    increment_view_count(share_id=share_id)
    return render_share(share)


@app.route("/code/<share_code>")
def view_by_code(share_code):
    """Open a shared file using its share code."""
    share_code = share_code.strip().upper()
    share = get_share_by_code(share_code)

    if not share:
        return render_template("404.html"), 404

    increment_view_count(share_code=share_code)
    return render_share(share)


@app.route("/download/<filename>")
def download_file(filename):
    """Download a shared file."""
    with get_db_connection() as conn:
        share = conn.execute(
            "SELECT original_name FROM shares WHERE filename = ?",
            (filename,),
        ).fetchone()

    if not share:
        return render_template("404.html"), 404

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    if not os.path.exists(file_path):
        return render_template("404.html"), 404

    return send_file(
        file_path,
        as_attachment=True,
        download_name=share[0],
    )


@app.route("/text", methods=["GET", "POST"])
def share_text():
    """Create and share a text file."""
    if request.method == "GET":
        return render_template("share_text.html")

    text_content = request.form.get("text_content", "").strip()

    if not text_content:
        flash("Please enter some text")
        return redirect(url_for("share_text"))

    share_id = str(uuid.uuid4())[:8]
    filename = f"{share_id}.txt"
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(text_content)

    share_id, share_code = create_share(
        filename=filename,
        original_name="text_share.txt",
        file_type="text",
    )

    share_url = request.host_url + f"s/{share_id}"

    return render_template(
        "share_success.html",
        share_url=share_url,
        share_code=share_code,
        file_type="text",
    )


@app.route("/access", methods=["GET", "POST"])
def access_file():
    """Find a shared file using its share code."""
    if request.method == "GET":
        return render_template("access_file.html")

    share_code = request.form.get("share_code", "").strip().upper()

    if not share_code:
        flash("Please enter a share code")
        return redirect(url_for("access_file"))

    share = get_share_by_code(share_code)

    if not share:
        flash("Invalid share code")
        return redirect(url_for("access_file"))

    return redirect(url_for("view_by_code", share_code=share_code))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
