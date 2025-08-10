import os
import sqlite3
import string
import random
from flask import Flask, request, jsonify, redirect, g
from flask_cors import CORS
import qrcode
from io import BytesIO
import base64

app = Flask(__name__)
CORS(app)

DATABASE = 'url_shortener.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.execute('''CREATE TABLE IF NOT EXISTS url_mappings
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      short_code TEXT UNIQUE,
                      original_url TEXT)''')
    return db

def generate_short_code():
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(6))

def generate_qr_code(url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

@app.route('/shorten', methods=['POST'])
def shorten_url():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Missing URL parameter"}), 400
    
    original_url = data['url'].strip()
    if not original_url:
        return jsonify({"error": "URL cannot be empty"}), 400
    
    if not original_url.startswith(('http://', 'https://')):
        original_url = 'https://' + original_url
    
    db = get_db()
    cursor = db.cursor()
    
    # Check if URL already exists
    cursor.execute("SELECT short_code FROM url_mappings WHERE original_url=?", (original_url,))
    existing = cursor.fetchone()
    
    if existing:
        short_code = existing[0]
    else:
        while True:
            short_code = generate_short_code()
            cursor.execute("SELECT id FROM url_mappings WHERE short_code=?", (short_code,))
            if not cursor.fetchone():
                break
        
        cursor.execute("INSERT INTO url_mappings (short_code, original_url) VALUES (?, ?)",
                       (short_code, original_url))
        db.commit()
    
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
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT original_url FROM url_mappings WHERE short_code=?", (short_code,))
    result = cursor.fetchone()
    
    if result:
        return redirect(result[0])
    return jsonify({"error": "Short URL not found"}), 404

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
