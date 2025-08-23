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