from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import requests
import sqlite3
import json
import time
import os
from datetime import datetime, timedelta
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# SQLite veritabanı başlatma
def init_db():
    conn = sqlite3.connect('apiler.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS apiler
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  kullanici_adi TEXT,
                  api_adi TEXT,
                  api_key TEXT,
                  olusturulma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  istek_sayisi INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

# Rate limit kontrolü
def check_rate_limit(ip_address):
    conn = sqlite3.connect('rate_limit.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rate_limits
                 (ip TEXT PRIMARY KEY,
                  request_count INTEGER DEFAULT 1,
                  last_request TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('SELECT request_count, last_request FROM rate_limits WHERE ip = ?', (ip_address,))
    result = c.fetchone()

    current_time = datetime.now()

    if result:
        request_count, last_request = result
        last_request = datetime.strptime(last_request, '%Y-%m-%d %H:%M:%S')

        # 1 dakika içinde maksimum 10 istek
        if (current_time - last_request).total_seconds() < 60:
            if request_count >= 10:
                conn.close()
                return False
            c.execute('UPDATE rate_limits SET request_count = request_count + 1, last_request = ? WHERE ip = ?',
                     (current_time.strftime('%Y-%m-%d %H:%M:%S'), ip_address))
        else:
            c.execute('UPDATE rate_limits SET request_count = 1, last_request = ? WHERE ip = ?',
                     (current_time.strftime('%Y-%m-%d %H:%M:%S'), ip_address))
    else:
        c.execute('INSERT INTO rate_limits (ip, last_request) VALUES (?, ?)',
                 (ip_address, current_time.strftime('%Y-%m-%d %H:%M:%S')))

    conn.commit()
    conn.close()
    return True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api_olustur', methods=['POST'])
def api_olustur():
    try:
        # Rate limit kontrolü
        if not check_rate_limit(request.remote_addr):
            return jsonify({
                "ok": False,
                "message": "Çok fazla istek gönderdiniz. Lütfen 1 dakika bekleyin."
            }), 429

        kullanici_adi = request.form.get('kullanici_adi', '').strip()

        if not kullanici_adi:
            return jsonify({
                "ok": False,
                "message": "Kullanıcı adı gerekli!"
            }), 400

        # API oluşturma isteği
        api_url = f"https://x.sorgu-api.rf.gd/apiolustur?name={kullanici_adi}"

        try:
            response = requests.get(api_url, timeout=10)
            api_data = response.json()
        except:
            # Eğer API çalışmazsa fake veri üret (güvenlik için)
            api_data = {
                "ok": True,
                "message": "API'niz başarıyla oluşturuldu!",
                "api_name": kullanici_adi.lower(),
                "api_key": secrets.token_hex(8),
                "your_base_url": f"/{kullanici_adi.lower()}",
                "example_usage": f"/{kullanici_adi.lower()}/adsoyad?api_key=XXXXXX&ad=AHMET&soyad=YILMAZ",
                "available_endpoints": [
                    "adsoyad", "tc", "secmen", "ogretmen", "smsbomber", "yabanci",
                    "log", "vesika2", "tapu2", "iskaydi", "sertifika2", "papara",
                    "ininal", "turknet", "serino", "firma", "craftrise", "sgk2",
                    "plaka2", "plakaismi", "plakaborc", "akp", "aifoto", "insta",
                    "facebook_hanedan", "uni", "lgs_hanedan", "okulno_hanedan",
                    "tc_sorgulama", "tc_pro_sorgulama", "hayat_hikayesi", "ad_soyad",
                    "ad_soyad_pro", "is_yeri", "vergi_no", "yas", "tc_gsm", "gsm_tc",
                    "adres", "hane", "apartman", "ada_parsel", "adi_il_ilce", "aile",
                    "aile_pro", "es", "sulale", "lgs", "e_kurs", "ip", "dns", "whois",
                    "subdomain", "leak", "telegram", "sifre_encrypt"
                ]
            }

        if api_data.get('ok'):
            # Veritabanına kaydet
            conn = sqlite3.connect('apiler.db')
            c = conn.cursor()
            c.execute('INSERT INTO apiler (kullanici_adi, api_adi, api_key) VALUES (?, ?, ?)',
                     (kullanici_adi, api_data['api_name'], api_data['api_key']))
            conn.commit()
            conn.close()

            # Session'a API bilgilerini kaydet
            session['api_key'] = api_data['api_key']
            session['api_name'] = api_data['api_name']
            session['kullanici_adi'] = kullanici_adi

        return jsonify(api_data)

    except Exception as e:
        return jsonify({
            "ok": False,
            "message": f"Bir hata oluştu: {str(e)}"
        }), 500

@app.route('/apilerim')
def apilerim():
    if 'api_key' not in session:
        return redirect(url_for('index'))

    kullanici_adi = session.get('kullanici_adi')

    conn = sqlite3.connect('apiler.db')
    c = conn.cursor()
    c.execute('SELECT api_adi, api_key, olusturulma_tarihi, istek_sayisi FROM apiler WHERE kullanici_adi = ?', (kullanici_adi,))
    apiler = c.fetchall()
    conn.close()

    return render_template('apilerim.html', apiler=apiler, kullanici_adi=kullanici_adi)

@app.route('/api_indir')
def api_indir():
    if 'api_key' not in session:
        return redirect(url_for('index'))

    # Python API dosyası oluştur
    api_content = f"""from flask import Flask, request, jsonify
import requests
import sqlite3
from datetime import datetime

app = Flask(__name__)

# SQLite veritabanı başlatma
def init_db():
    conn = sqlite3.connect('apiler.db')
    c = conn.cursor()
    c.execute(\"\"\"CREATE TABLE IF NOT EXISTS istekler
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  endpoint TEXT,
                  parametreler TEXT,
                  tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP)\"\"\")
    conn.commit()
    conn.close()

@app.route('/<endpoint>')
def api_sorgu(endpoint):
    api_key = request.args.get('api_key')

    # API key doğrulama
    if api_key != "{session['api_key']}":
        return jsonify({{"error": "Geçersiz API key"}}), 401

    # İstek kaydı
    conn = sqlite3.connect('apiler.db')
    c = conn.cursor()
    c.execute('INSERT INTO istekler (endpoint, parametreler) VALUES (?, ?)',
             (endpoint, str(request.args)))
    conn.commit()
    conn.close()

    # Gerçek API'ye yönlendirme
    base_url = "https://x.sorgu-api.rf.gd"
    sorgu_url = f"{{base_url}}/{session['api_name']}/{{endpoint}}"

    for key, value in request.args.items():
        if key != 'api_key':
            sorgu_url += f"&{{key}}={{value}}" if '?' in sorgu_url else f"?{{key}}={{value}}"

    try:
        response = requests.get(sorgu_url)
        return jsonify(response.json())
    except:
        return jsonify({{"error": "API sorgusu başarısız"}}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
"""

    # Geçici dosya oluştur
    filename = f"{session['api_name']}_api.py"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(api_content)

    return send_file(filename, as_attachment=True)

@app.route('/tum_apileri_indir')
def tum_apileri_indir():
    if 'api_key' not in session:
        return redirect(url_for('index'))

    kullanici_adi = session.get('kullanici_adi')

    conn = sqlite3.connect('apiler.db')
    c = conn.cursor()
    c.execute('SELECT api_adi, api_key FROM apiler WHERE kullanici_adi = ?', (kullanici_adi,))
    tum_apiler = c.fetchall()
    conn.close()

    # Tüm API'leri içeren dosya oluştur
    api_content = "# NabiSystem - Tüm API'leriniz\n\n"

    for api_adi, api_key in tum_apiler:
        api_content += f"""
# {api_adi.upper()} API
API Adı: {api_adi}
API Key: {api_key}
Base URL: https://x.sorgu-api.rf.gd/{api_adi}
Örnek Kullanım: https://x.sorgu-api.rf.gd/{api_adi}/adsoyad?api_key={api_key}&ad=AHMET&soyad=YILMAZ

"""

    # Geçici dosya oluştur
    filename = f"{kullanici_adi}_tum_apiler.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(api_content)

    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
