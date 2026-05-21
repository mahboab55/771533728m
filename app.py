import os
import random
import string
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from hijridate import Gregorian, Hijri
from xhtml2pdf import pisa
import io
import qrcode

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sick_leave.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='user') # 'admin' or 'user'

class SickLeave(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(20), unique=True)
    patient_name = db.Column(db.String(100))
    id_number = db.Column(db.String(20))
    patient_phone = db.Column(db.String(20))
    medical_entity = db.Column(db.String(100))
    doctor_name = db.Column(db.String(100))
    specialty = db.Column(db.String(100))
    start_date_g = db.Column(db.String(20))
    start_date_h = db.Column(db.String(20))
    duration = db.Column(db.Integer)
    status = db.Column(db.String(20), default='active') # 'active' or 'cancelled'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    logo_path = db.Column(db.String(200), default='uploads/default_logo.png')
    sms_status = db.Column(db.String(100))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helpers
def generate_report_id():
    return 'PSL' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def convert_h_to_g(h_date_str):
    try:
        y, m, d = map(int, h_date_str.split('-'))
        g = Hijri(y, m, d).to_gregorian()
        return f"{g.year}-{g.month:02d}-{g.day:02d}"
    except:
        return None

def convert_g_to_h(g_date_str):
    try:
        y, m, d = map(int, g_date_str.split('-'))
        h = Gregorian(y, m, d).to_hijri()
        return f"{h.year}-{h.month:02d}-{h.day:02d}"
    except:
        return None

# Routes
@app.route('/')
def public_index():
    return render_template('verify.html')

@app.route('/dashboard')
@login_required
def index():
    if current_user.role == 'admin':
        leaves = SickLeave.query.all()
        stats = {
            'total': SickLeave.query.count(),
            'active': SickLeave.query.filter_by(status='active').count(),
            'cancelled': SickLeave.query.filter_by(status='cancelled').count(),
            'users': User.query.count()
        }
        return render_template('admin_dashboard.html', leaves=leaves, stats=stats)
    else:
        leaves = SickLeave.query.filter_by(user_id=current_user.id).all()
        return render_template('user_dashboard.html', leaves=leaves)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('index'))
        flash('خطأ في اسم المستخدم أو كلمة المرور')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin/add_user', methods=['POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'غير مصرح'})
    
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role', 'user')
    
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'المستخدم موجود مسبقاً'})
    
    new_user = User(username=username, password=generate_password_hash(password), role=role)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/convert-date', methods=['POST'])
def api_convert_date():
    data = request.json
    date_str = data.get('date')
    direction = data.get('direction')
    
    if direction == 'hijri_to_gregorian':
        res = convert_h_to_g(date_str)
    else:
        res = convert_g_to_h(date_str)
        
    return jsonify({'success': True, 'result': res})

@app.route('/form', methods=['GET', 'POST'])
@login_required
def form():
    edit_id = request.args.get('edit')
    leave = None
    if edit_id:
        leave = SickLeave.query.filter_by(report_id=edit_id).first()
        if not leave or (current_user.role != 'admin' and leave.user_id != current_user.id):
            return redirect(url_for('index'))

    if request.method == 'POST':
        data = request.form
        p_phone = data.get('patient_phone')
        
        if edit_id:
            leave.patient_name = data.get('patient_name')
            leave.id_number = data.get('id_number')
            leave.patient_phone = p_phone
            leave.medical_entity = data.get('medical_entity')
            leave.doctor_name = data.get('doctor_name')
            leave.specialty = data.get('specialty')
            leave.start_date_g = data.get('start_date_g')
            leave.start_date_h = data.get('start_date_h')
            leave.duration = data.get('duration')
            target_leave = leave
        else:
            target_leave = SickLeave(
                report_id=generate_report_id(),
                patient_name=data.get('patient_name'),
                id_number=data.get('id_number'),
                patient_phone=p_phone,
                medical_entity=data.get('medical_entity'),
                doctor_name=data.get('doctor_name'),
                specialty=data.get('specialty'),
                start_date_g=data.get('start_date_g'),
                start_date_h=data.get('start_date_h'),
                duration=data.get('duration'),
                user_id=current_user.id
            )
            db.session.add(target_leave)
        
        db.session.commit()

        # توليد الباركود
        qr_dir = os.path.join(app.static_folder, 'qrcodes')
        os.makedirs(qr_dir, exist_ok=True)
        qr_path = os.path.join(qr_dir, f"{target_leave.report_id}.png")
        verify_url = request.host_url.rstrip('/') + url_for('public_index') + f"?report_id={target_leave.report_id}&id_number={target_leave.id_number}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(verify_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_path)

        # إرسال SMS
        if p_phone:
            try:
                from utils.sms_sender import send_sms
                msg = f"خطاك السوء {target_leave.patient_name} تم إصدار إجازة مرضية ليوم {target_leave.duration} برقم {target_leave.report_id} ويمكنك الاطلاع عليها عبر تطبيق صحتي دمتم بصحة."
                res = send_sms(p_phone, msg)
                target_leave.sms_status = "تم الإرسال" if res['success'] else f"فشل: {res.get('error')}"
                db.session.commit()
            except Exception as e:
                print(f"SMS Error: {e}")

        return redirect(url_for('view_result', report_id=target_leave.report_id))

    return render_template('form.html', leave=leave)

@app.route('/view/<report_id>')
@login_required
def view_result(report_id):
    leave = SickLeave.query.filter_by(report_id=report_id).first()
    if not leave:
        return redirect(url_for('index'))
    return render_template('result.html', leave=leave)

@app.route('/download_pdf/<report_id>')
@login_required
def download_pdf(report_id):
    leave = SickLeave.query.filter_by(report_id=report_id).first()
    if not leave:
        return redirect(url_for('index'))
    
    html = render_template('result.html', leave=leave, is_pdf=True)
    result = io.BytesIO()
    pisa.CreatePDF(io.BytesIO(html.encode("UTF-8")), dest=result, encoding='UTF-8')
    result.seek(0)
    
    return send_from_directory(directory=app.config['UPLOAD_FOLDER'], path='default_logo.png', as_attachment=True) # Placeholder for actual PDF delivery logic if needed, but we'll use window.print() as primary.

@app.route('/delete/<report_id>')
@login_required
def delete_leave(report_id):
    leave = SickLeave.query.filter_by(report_id=report_id).first()
    if leave and (current_user.role == 'admin' or leave.user_id == current_user.id):
        db.session.delete(leave)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/cancel/<report_id>')
@login_required
def cancel_leave(report_id):
    leave = SickLeave.query.filter_by(report_id=report_id).first()
    if leave and (current_user.role == 'admin' or leave.user_id == current_user.id):
        leave.status = 'cancelled'
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/api/verify', methods=['POST'])
def api_verify():
    report_id = request.json.get('report_id')
    id_number = request.json.get('id_number')
    leave = SickLeave.query.filter_by(report_id=report_id, id_number=id_number).first()
    if leave:
        return jsonify({
            'success': True,
            'data': {
                'patient_name': leave.patient_name,
                'medical_entity': leave.medical_entity,
                'doctor_name': leave.doctor_name,
                'start_date_h': leave.start_date_h,
                'duration': leave.duration,
                'status': leave.status
            }
        })
    return jsonify({'success': False, 'message': 'لم يتم العثور على الإجازة أو البيانات غير متطابقة'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create default admin if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password=generate_password_hash('admin123'), role='admin')
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True, host='0.0.0.0', port=5000)
