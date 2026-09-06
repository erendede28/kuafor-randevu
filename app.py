import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'kuafor_gizli_anahtar_123'

# Fotoğraf Yükleme Klasör Ayarı
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db():
    conn = sqlite3.connect('kuafor.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    # Randevular tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            service TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            status TEXT DEFAULT 'Beklemede',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Galeri tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gallery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            image_path TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


init_db()

SERVICES = [
    {"id": 1, "name": "Saç Kesim & Şekillendirme", "price": "450 ₺", "duration": "45 dk"},
    {"id": 2, "name": "Ombre / Sombre / Renklendirme", "price": "2.800 ₺", "duration": "180 dk"},
    {"id": 3, "name": "Keratin & Botoks Bakımı", "price": "1.200 ₺", "duration": "90 dk"},
    {"id": 4, "name": "Gelin Saçı & Profesyonel Makyaj", "price": "6.000 ₺", "duration": "240 dk"}
]


@app.route('/')
def home():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM gallery ORDER BY id DESC')
    photos = cursor.fetchall()
    conn.close()
    return render_template('index.html', services=SERVICES, photos=photos)


@app.route('/randevu-al', methods=['POST'])
def create_appointment():
    name = request.form.get('name')
    phone = request.form.get('phone')
    service = request.form.get('service')
    date_time = request.form.get('date_time')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM appointments 
        WHERE appointment_date = ? AND status != 'İptal'
    ''', (date_time,))
    existing_appointment = cursor.fetchone()

    if existing_appointment:
        conn.close()
        flash('Seçtiğiniz tarih ve saatte başka bir randevu bulunmaktadır.', 'danger')
        return redirect(url_for('home'))

    cursor.execute('''
        INSERT INTO appointments (customer_name, phone, service, appointment_date, status)
        VALUES (?, ?, ?, ?, 'Beklemede')
    ''', (name, phone, service, date_time))

    conn.commit()
    appointment_id = cursor.lastrowid
    conn.close()

    return redirect(url_for('success', appointment_id=appointment_id))


@app.route('/randevu-basarili/<int:appointment_id>')
def success(appointment_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM appointments WHERE id = ?', (appointment_id,))
    appointment = cursor.fetchone()
    conn.close()

    if not appointment:
        return redirect(url_for('home'))

    return render_template('basarili.html', appointment=appointment)


# --- YÖNETİCİ VE GİRİŞ ROTALARI ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == 'admin' and password == '123456':
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            flash('Hatalı kullanıcı adı veya şifre!', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('login'))


@app.route('/admin')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM appointments ORDER BY appointment_date DESC')
    appointments = cursor.fetchall()

    cursor.execute('SELECT * FROM gallery ORDER BY id DESC')
    photos = cursor.fetchall()
    conn.close()

    return render_template('admin.html', appointments=appointments, photos=photos)


# Fotoğraf Yükleme Rotası
@app.route('/admin/foto-ekle', methods=['POST'])
def add_photo():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    title = request.form.get('title')
    file = request.files.get('file')

    if file and file.filename != '':
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO gallery (title, image_path) VALUES (?, ?)', (title, f'uploads/{filename}'))
        conn.commit()
        conn.close()
        flash('Fotoğraf başarıyla yüklendi.', 'success')

    return redirect(url_for('admin_panel'))


# Fotoğraf Silme Rotası
@app.route('/admin/foto-sil/<int:photo_id>')
def delete_photo(photo_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT image_path FROM gallery WHERE id = ?', (photo_id,))
    photo = cursor.fetchone()

    if photo:
        full_path = os.path.join('static', photo['image_path'])
        if os.path.exists(full_path):
            os.remove(full_path)

        cursor.execute('DELETE FROM gallery WHERE id = ?', (photo_id,))
        conn.commit()
        flash('Fotoğraf silindi.', 'info')

    conn.close()
    return redirect(url_for('admin_panel'))


@app.route('/admin/durum-guncelle/<int:appointment_id>/<string:new_status>')
def update_status(appointment_id, new_status):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE appointments SET status = ? WHERE id = ?', (new_status, appointment_id))
    conn.commit()
    conn.close()
    flash(f'Randevu durumu "{new_status}" olarak güncellendi.', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/sil/<int:appointment_id>')
def delete_appointment(appointment_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM appointments WHERE id = ?', (appointment_id,))
    conn.commit()
    conn.close()
    flash('Randevu kaydı silindi.', 'info')
    return redirect(url_for('admin_panel'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)