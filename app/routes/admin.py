"""
MediCore HMS — Admin Routes
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models.user import User, Role, HospitalSetting, AuditLog
from app.models.patient import Patient
from app.models.doctor import Doctor, Department, DoctorSchedule
from app.models.appointment import Appointment
from app.models.clinical import Ward, Bed, Invoice, Notification
from app.services.auth_service import create_user, log_action, generate_password
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin():
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    return render_template('admin/dashboard.html')

@admin_bp.route('/api/stats')
@admin_required
def api_stats():
    today = datetime.utcnow().date()
    occupied = Bed.query.filter_by(status='occupied').count()
    available = Bed.query.filter_by(status='available').count()
    total_beds = Bed.query.filter_by(is_active=True).count()
    revenue = db.session.query(
        db.func.coalesce(db.func.sum(Invoice.total_amount), 0)
    ).filter(
        db.func.date(Invoice.created_at) == today,
        Invoice.status == 'paid'
    ).scalar() or 0
    appt_today = Appointment.query.filter(
        db.func.date(Appointment.appointment_date) == today).count()
    patients_today = Appointment.query.filter(
        db.func.date(Appointment.appointment_date) == today,
        Appointment.status.in_(['completed','in_progress','checked_in'])
    ).count()
    return jsonify({'success': True, 'stats': {
        'patients_today':     patients_today,
        'total_patients':     Patient.query.filter_by(is_active=True).count(),
        'active_doctors':     Doctor.query.filter_by(is_available=True).count(),
        'total_doctors':      Doctor.query.count(),
        'beds_occupied':      occupied,
        'beds_available':     available,
        'beds_total':         total_beds,
        'appointments_today': appt_today,
        'revenue_today':      float(revenue),
        'total_users':        User.query.filter_by(is_active=True).count(),
    }})

@admin_bp.route('/api/charts/appointments')
@admin_required
def chart_appointments():
    labels, counts = [], []
    for i in range(6, -1, -1):
        d = datetime.utcnow().date() - timedelta(days=i)
        c = Appointment.query.filter(
            db.func.date(Appointment.appointment_date) == d).count()
        labels.append(d.strftime('%a'))
        counts.append(c)
    return jsonify({'success': True, 'labels': labels, 'data': counts})

@admin_bp.route('/api/charts/departments')
@admin_required
def chart_departments():
    results = db.session.query(
        Department.name, db.func.count(Appointment.id)
    ).outerjoin(Appointment, Appointment.department_id == Department.id
    ).filter(Department.is_active == True
    ).group_by(Department.id).limit(8).all()
    return jsonify({'success': True,
                    'labels': [r[0] for r in results],
                    'data':   [r[1] for r in results]})

@admin_bp.route('/api/notifications')
@admin_required
def api_notifications():
    notifs = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).order_by(Notification.created_at.desc()).limit(15).all()
    return jsonify({'success': True,
                    'notifications': [n.to_dict() for n in notifs],
                    'unread_count': len(notifs)})

@admin_bp.route('/api/notifications/mark-read', methods=['POST'])
@admin_required
def mark_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update(
        {'is_read': True, 'read_at': datetime.utcnow()})
    db.session.commit()
    return jsonify({'success': True})

@admin_bp.route('/api/users')
@admin_required
def api_users():
    role_filter = request.args.get('role', '')
    search      = request.args.get('search', '')
    page        = int(request.args.get('page', 1))
    per_page    = 20
    q = User.query.join(Role)
    if role_filter:
        q = q.filter(Role.name == role_filter)
    if search:
        q = q.filter(db.or_(
            User.first_name.ilike(f'%{search}%'),
            User.last_name.ilike(f'%{search}%'),
            User.email.ilike(f'%{search}%'),
            User.username.ilike(f'%{search}%'),
        ))
    total = q.count()
    users = q.order_by(User.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()
    return jsonify({'success': True, 'users': [u.to_dict() for u in users],
                    'total': total, 'page': page,
                    'pages': (total + per_page - 1) // per_page})

@admin_bp.route('/api/users/create', methods=['POST'])
@admin_required
def api_create_user():
    data = request.get_json() or {}
    for field in ['first_name', 'last_name', 'email', 'phone', 'role']:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'{field} is required'}), 400
    try:
        user, plain_pwd = create_user(
            first_name = data['first_name'].strip(),
            last_name  = data['last_name'].strip(),
            email      = data['email'].strip().lower(),
            phone      = data['phone'].strip(),
            role_name  = data['role'],
            gender     = data.get('gender'),
            created_by = current_user.id,
        )
        if data['role'] == 'doctor':
            dept_id = data.get('department_id')
            doc = Doctor(
                user_id          = user.id,
                department_id    = int(dept_id) if dept_id else None,
                specialization   = data.get('specialization', ''),
                qualification    = data.get('qualification', ''),
                experience_years = int(data.get('experience_years', 0)),
                registration_no  = data.get('registration_no', ''),
                consultation_fee = float(data.get('consultation_fee', 0)),
                employee_id      = f'EMP{user.id:04d}',
            )
            db.session.add(doc)
            db.session.commit()
        db.session.add(Notification(
            user_id=user.id, title='Welcome to MediCore HMS',
            message=f'Your account: Username={user.username}, Password={plain_pwd}',
            notif_type='info', module='auth'))
        db.session.commit()
        return jsonify({'success': True,
                        'message': f'User {user.username} created!',
                        'credentials': {'username': user.username, 'password': plain_pwd}})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/api/users/<int:uid>/toggle', methods=['POST'])
@admin_required
def toggle_user(uid):
    user = User.query.get_or_404(uid)
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot deactivate yourself'}), 400
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': user.is_active})

@admin_bp.route('/api/users/<int:uid>/reset-password', methods=['POST'])
@admin_required
def reset_pwd(uid):
    user    = User.query.get_or_404(uid)
    new_pwd = generate_password()
    user.set_password(new_pwd)
    db.session.commit()
    return jsonify({'success': True, 'new_password': new_pwd})

@admin_bp.route('/api/doctors')
@admin_required
def api_doctors():
    search = request.args.get('search', '')
    dept   = request.args.get('department_id', '')
    q = Doctor.query.join(User)
    if search:
        q = q.filter(db.or_(User.first_name.ilike(f'%{search}%'),
                             User.last_name.ilike(f'%{search}%')))
    if dept:
        q = q.filter(Doctor.department_id == int(dept))
    return jsonify({'success': True, 'doctors': [d.to_dict() for d in q.all()]})

@admin_bp.route('/api/doctors/<int:did>/schedule', methods=['GET','POST'])
@admin_required
def doctor_schedule(did):
    Doctor.query.get_or_404(did)
    if request.method == 'GET':
        ss = DoctorSchedule.query.filter_by(doctor_id=did, is_active=True).all()
        return jsonify({'success': True, 'schedules': [{
            'id': s.id, 'day_of_week': s.day_of_week,
            'start_time': s.start_time.strftime('%H:%M'),
            'end_time':   s.end_time.strftime('%H:%M'),
            'slot_duration': s.slot_duration, 'max_patients': s.max_patients,
        } for s in ss]})
    data = request.get_json() or {}
    DoctorSchedule.query.filter_by(doctor_id=did).delete()
    from datetime import time as dtime
    for s in data.get('schedules', []):
        st = dtime(*map(int, s['start_time'].split(':')))
        et = dtime(*map(int, s['end_time'].split(':')))
        db.session.add(DoctorSchedule(
            doctor_id=did, day_of_week=s['day_of_week'],
            start_time=st, end_time=et,
            slot_duration=s.get('slot_duration', 15),
            max_patients=s.get('max_patients', 20),
        ))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Schedule saved!'})

@admin_bp.route('/api/departments')
@admin_required
def api_departments():
    depts = Department.query.filter_by(is_active=True).all()
    return jsonify({'success': True,
                    'departments': [{'id': d.id, 'name': d.name, 'floor': d.floor} for d in depts]})

@admin_bp.route('/api/settings', methods=['GET','POST'])
@admin_required
def api_settings():
    if request.method == 'GET':
        return jsonify({'success': True, 'settings': {
            s.setting_key: s.setting_value
            for s in HospitalSetting.query.all()}})
    for k, v in (request.get_json() or {}).items():
        HospitalSetting.set_value(k, v, updated_by=current_user.id)
    log_action(user_id=current_user.id, action='UPDATE_SETTINGS', module='admin',
               description='Settings updated')
    return jsonify({'success': True, 'message': 'Settings saved!'})

@admin_bp.route('/api/audit-logs')
@admin_required
def api_audit():
    page = int(request.args.get('page', 1))
    per_page = 50
    q = AuditLog.query.order_by(AuditLog.created_at.desc())
    total = q.count()
    logs  = q.offset((page-1)*per_page).limit(per_page).all()
    return jsonify({'success': True, 'total': total, 'logs': [{
        'id': l.id, 'action': l.action, 'module': l.module or '',
        'description': l.description or '', 'ip_address': l.ip_address or '',
        'user': User.query.get(l.user_id).full_name if l.user_id else 'System',
        'created_at': l.created_at.strftime('%d %b %Y %H:%M'),
    } for l in logs]})

@admin_bp.route('/api/roles')
@admin_required
def api_roles():
    roles = Role.query.all()
    return jsonify({'success': True,
                    'roles': [{'id': r.id, 'name': r.name} for r in roles]})
