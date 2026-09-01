<<<<<<< HEAD
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
=======
# app.py
import os
import uuid
import random
import string
from datetime import datetime, timedelta
from flask import Flask, render_template, request, send_file, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import sqlite3

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['DB_NAME'] = 'lekshare.db'

# Allowed file extensions
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp4', 'doc', 'docx'}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def generate_share_code():
    """Generate a unique 6-character share code"""
    while True:
        # Generate a 6-character code with letters and numbers
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Check if code already exists
        conn = sqlite3.connect(app.config['DB_NAME'])
        c = conn.cursor()
        c.execute("SELECT id FROM shares WHERE share_code = ?", (code,))
        existing = c.fetchone()
        conn.close()
        
        if not existing:
            return code

def init_db():
    """Initialize the database"""
    conn = sqlite3.connect(app.config['DB_NAME'])
    c = conn.cursor()
    
    # Check if the old table exists and has data
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shares'")
    table_exists = c.fetchone()
    
    if table_exists:
        # Check if share_code column exists
        c.execute("PRAGMA table_info(shares)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'share_code' not in columns:
            # Create new table with correct schema
            c.execute('''CREATE TABLE shares_new
                         (id TEXT PRIMARY KEY, 
                          share_code TEXT UNIQUE,
                          filename TEXT, 
                          original_name TEXT,
                          file_type TEXT,
                          created_at TIMESTAMP,
                          expires_at TIMESTAMP,
                          view_count INTEGER DEFAULT 0)''')
            
            # Copy existing data to new table
            c.execute("SELECT id, filename, original_name, file_type, created_at, expires_at, view_count FROM shares")
            existing_records = c.fetchall()
            
            for record in existing_records:
                share_code = generate_share_code()
                c.execute("INSERT INTO shares_new (id, share_code, filename, original_name, file_type, created_at, expires_at, view_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                          (record[0], share_code, record[1], record[2], record[3], record[4], record[5], record[6]))
            
            # Drop old table and rename new table
            c.execute("DROP TABLE shares")
            c.execute("ALTER TABLE shares_new RENAME TO shares")
    else:
        # Create new table if it doesn't exist
        c.execute('''CREATE TABLE shares
                     (id TEXT PRIMARY KEY, 
                      share_code TEXT UNIQUE,
                      filename TEXT, 
                      original_name TEXT,
                      file_type TEXT,
                      created_at TIMESTAMP,
                      expires_at TIMESTAMP,
                      view_count INTEGER DEFAULT 0)''')
    
    conn.commit()
    conn.close()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/share', methods=['POST'])
def share():
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('index'))
    
    # Generate unique ID and share code
    share_id = str(uuid.uuid4())[:8]
    share_code = generate_share_code()
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        original_name = filename
        extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        # Save file with unique name
        unique_filename = f"{share_id}.{extension}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        # Determine file type
        if extension in ['txt']:
            file_type = 'text'
        elif extension in ['png', 'jpg', 'jpeg', 'gif']:
            file_type = 'image'
        else:
            file_type = 'file'
        
        # Set expiration (7 days from now)
        created_at = datetime.now()
        expires_at = created_at + timedelta(days=7)
        
        # Save to database
        conn = sqlite3.connect(app.config['DB_NAME'])
        c = conn.cursor()
        c.execute("INSERT INTO shares (id, share_code, filename, original_name, file_type, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (share_id, share_code, unique_filename, original_name, file_type, created_at, expires_at))
        conn.commit()
        conn.close()
        
        share_url = request.host_url + 's/' + share_id
        return render_template('share_success.html', share_url=share_url, share_code=share_code, file_type=file_type)
    
    flash('File type not allowed')
    return redirect(url_for('index'))

@app.route('/s/<share_id>')
def view_share(share_id):
    conn = sqlite3.connect(app.config['DB_NAME'])
    c = conn.cursor()
    c.execute("SELECT * FROM shares WHERE id = ?", (share_id,))
    share = c.fetchone()
    
    if not share:
        return render_template('404.html'), 404
    
    # Update view count
    c.execute("UPDATE shares SET view_count = view_count + 1 WHERE id = ?", (share_id,))
    conn.commit()
    conn.close()
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], share[2])
    
    # Check if file exists
    if not os.path.exists(file_path):
        return render_template('404.html'), 404
    
    # Render based on file type
    if share[4] == 'text':
        with open(file_path, 'r') as f:
            content = f.read()
        return render_template('view_text.html', content=content, filename=share[3])
    elif share[4] == 'image':
        return render_template('view_image.html', filename=share[2], original_name=share[3])
    else:
        return render_template('download_file.html', filename=share[2], original_name=share[3])

@app.route('/code/<share_code>')
def view_by_code(share_code):
    conn = sqlite3.connect(app.config['DB_NAME'])
    c = conn.cursor()
    c.execute("SELECT * FROM shares WHERE share_code = ?", (share_code,))
    share = c.fetchone()
    
    if not share:
        return render_template('404.html'), 404
    
    # Update view count
    c.execute("UPDATE shares SET view_count = view_count + 1 WHERE share_code = ?", (share_code,))
    conn.commit()
    conn.close()
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], share[2])
    
    # Check if file exists
    if not os.path.exists(file_path):
        return render_template('404.html'), 404
    
    # Render based on file type
    if share[4] == 'text':
        with open(file_path, 'r') as f:
            content = f.read()
        return render_template('view_text.html', content=content, filename=share[3])
    elif share[4] == 'image':
        return render_template('view_image.html', filename=share[2], original_name=share[3])
    else:
        return render_template('download_file.html', filename=share[2], original_name=share[3])

@app.route('/download/<filename>')
def download_file(filename):
    conn = sqlite3.connect(app.config['DB_NAME'])
    c = conn.cursor()
    c.execute("SELECT original_name FROM shares WHERE filename = ?", (filename,))
    share = c.fetchone()
    conn.close()
    
    if not share:
        return render_template('404.html'), 404
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(file_path, as_attachment=True, download_name=share[0])

@app.route('/text', methods=['GET', 'POST'])
def share_text():
    if request.method == 'POST':
        text_content = request.form.get('text_content')
        if not text_content:
            flash('Please enter some text')
            return redirect(url_for('share_text'))
        
        # Generate unique ID and share code
        share_id = str(uuid.uuid4())[:8]
        share_code = generate_share_code()
        filename = f"{share_id}.txt"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save text to file
        with open(filepath, 'w') as f:
            f.write(text_content)
        
        # Set expiration (7 days from now)
        created_at = datetime.now()
        expires_at = created_at + timedelta(days=7)
        
        # Save to database
        conn = sqlite3.connect(app.config['DB_NAME'])
        c = conn.cursor()
        c.execute("INSERT INTO shares (id, share_code, filename, original_name, file_type, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (share_id, share_code, filename, 'text_share.txt', 'text', created_at, expires_at))
        conn.commit()
        conn.close()
        
        share_url = request.host_url + 's/' + share_id
        return render_template('share_success.html', share_url=share_url, share_code=share_code, file_type='text')
    
    return render_template('share_text.html')

@app.route('/access', methods=['GET', 'POST'])
def access_file():
    if request.method == 'POST':
        share_code = request.form.get('share_code', '').strip().upper()
        if not share_code:
            flash('Please enter a share code')
            return redirect(url_for('access_file'))
        
        # Check if share code exists
        conn = sqlite3.connect(app.config['DB_NAME'])
        c = conn.cursor()
        c.execute("SELECT * FROM shares WHERE share_code = ?", (share_code,))
        share = c.fetchone()
        conn.close()
        
        if not share:
            flash('Invalid share code')
            return redirect(url_for('access_file'))
        
        # Redirect to the file
        return redirect(url_for('view_by_code', share_code=share_code))
    
    return render_template('access_file.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
>>>>>>> b7ba4ffd24021a83426d5741a4a7b62c0fa41bf6
