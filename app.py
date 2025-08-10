import os
import sqlite3
import string
import random
from flask import Flask, request, jsonify, redirect, g
from flask_cors import CORS
import qrcode
from io import BytesIO
import base64
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

DATABASE = 'url_shortener.db'

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS url_mappings
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      short_code TEXT UNIQUE,
                      original_url TEXT)''')
        db.commit()

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
    return g.db

def generate_short_code():
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=6))

def generate_qr_code(url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=6,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

@app.route('/shorten', methods=['POST'])
def shorten_url():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Missing URL parameter"}), 400
    
    original_url = data['url'].strip()
    if not original_url:
        return jsonify({"error": "URL cannot be empty"}), 400
    
    # Add https:// if missing scheme
    if not original_url.startswith(('http://', 'https://')):
        original_url = 'https://' + original_url
    
    # Validate URL format
    if not is_valid_url(original_url):
        return jsonify({"error": "Invalid URL format"}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Check if URL already exists
    cursor.execute("SELECT short_code FROM url_mappings WHERE original_url=?", (original_url,))
    existing = cursor.fetchone()
    
    if existing:
        short_code = existing[0]
    else:
        # Generate unique short code
        for _ in range(10):  # Try up to 10 times to generate unique code
            short_code = generate_short_code()
            cursor.execute("SELECT id FROM url_mappings WHERE short_code=?", (short_code,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO url_mappings (short_code, original_url) VALUES (?, ?)",
                            (short_code, original_url))
                db.commit()
                break
        else:
            return jsonify({"error": "Failed to generate unique short code"}), 500
    
    base_url = request.url_root.rstrip('/')
    short_url = f"{base_url}/{short_code}"
    qr_base64 = generate_qr_code(short_url)
    
    return jsonify({
        "original_url": original_url,
        "short_url": short_url,
        "qr_code": qr_base64
    })

@app.route('/<short_code>')
def redirect_to_original(short_code):
    if len(short_code) != 6 or not all(c in (string.ascii_letters + string.digits) for c in short_code):
        return jsonify({"error": "Invalid short URL format"}), 400
        
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT original_url FROM url_mappings WHERE short_code=?", (short_code,))
    result = cursor.fetchone()
    
    if result:
        return redirect(result[0])
    return jsonify({"error": "Short URL not found"}), 404

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
