from flask import Flask, request, jsonify, redirect
import string, random
import qrcode
import io
import base64

app = Flask(__name__)

url_db = {}  # short_code: original_url mapping

def generate_short_code(length=6):
    chars = string.ascii_letters + string.digits
    while True:
        code = ''.join(random.choices(chars, k=length))
        if code not in url_db:
            return code

@app.route('/shorten', methods=['POST'])
def shorten_url():
    data = request.json
    original_url = data.get('url')
    if not original_url:
        return jsonify({'error': 'No URL provided'}), 400
    
    # generate short code
    code = generate_short_code()
    url_db[code] = original_url

    short_url = request.host_url + code

    # generate QR code
    img = qrcode.make(short_url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return jsonify({
        'short_url': short_url,
        'qr_code': f"data:image/png;base64,{qr_b64}"
    })

@app.route('/<code>')
def redirect_to_original(code):
    original_url = url_db.get(code)
    if original_url:
        return redirect(original_url)
    else:
        return jsonify({'error': 'Invalid short URL'}), 404

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
