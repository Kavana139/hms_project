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
            message=f'Your account has been created. Username: {user.username}',
            notif_type='info', module='auth'))
        db.session.commit()

        # Send welcome email with credentials
        try:
            from app.services.notification_service import send_email
            role_label = data['role'].replace('_', ' ').title()
            email_body = (
                f"Dear {user.full_name},\n\n"
                f"Welcome to MediCore HMS! Your {role_label} account has been created.\n\n"
                f"Login Details:\n"
                f"  URL:      http://localhost:5000/auth/login\n"
                f"  Username: {user.username}\n"
                f"  Password: {plain_pwd}\n\n"
                f"Please log in and change your password immediately.\n\n"
                f"Regards,\nMediCore HMS Administration"
            )
            send_email(
                to      = user.email,
                subject = f'Welcome to MediCore HMS — Your {role_label} Account',
                body    = email_body,
            )
        except Exception as mail_err:
            import logging
            logging.getLogger(__name__).warning(f'Welcome email failed: {mail_err}')

        return jsonify({'success': True,
                        'message': f'User {user.username} created! Credentials emailed to {user.email}.',
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


# ── Bed & Ward Management ─────────────────────────────────────

@admin_bp.route('/api/wards')
@admin_required
def api_wards():
    wards = Ward.query.filter_by(is_active=True).all()
    result = []
    for w in wards:
        total     = Bed.query.filter_by(ward_id=w.id, is_active=True).count()
        available = Bed.query.filter_by(ward_id=w.id, status='available', is_active=True).count()
        occupied  = Bed.query.filter_by(ward_id=w.id, status='occupied').count()
        cleaning  = Bed.query.filter_by(ward_id=w.id, status='cleaning').count()
        reserved  = Bed.query.filter_by(ward_id=w.id, status='reserved').count()
        maintenance = Bed.query.filter_by(ward_id=w.id, status='maintenance').count()
        result.append({
            'id': w.id, 'name': w.name, 'ward_type': w.ward_type,
            'floor': w.floor or '', 'charge_per_day': float(w.charge_per_day or 0),
            'description': w.description or '',
            'total': total, 'available': available, 'occupied': occupied,
            'cleaning': cleaning, 'reserved': reserved, 'maintenance': maintenance,
        })
    return jsonify({'success': True, 'wards': result})


@admin_bp.route('/api/wards/create', methods=['POST'])
@admin_required
def api_create_ward():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'success': False, 'message': 'Ward name is required'}), 400
    ward = Ward(
        name           = data['name'].strip(),
        ward_type      = data.get('ward_type', 'general'),
        floor          = data.get('floor', ''),
        charge_per_day = float(data.get('charge_per_day', 0)),
        description    = data.get('description', ''),
        is_active      = True,
    )
    db.session.add(ward)
    db.session.commit()
    log_action(user_id=current_user.id, action='CREATE_WARD', module='admin',
               description=f'Ward created: {ward.name}')
    return jsonify({'success': True, 'message': f'Ward "{ward.name}" created!',
                    'ward_id': ward.id})


@admin_bp.route('/api/wards/<int:wid>', methods=['PUT'])
@admin_required
def api_update_ward(wid):
    ward = Ward.query.get_or_404(wid)
    data = request.get_json() or {}
    if data.get('name'):        ward.name           = data['name'].strip()
    if data.get('ward_type'):   ward.ward_type       = data['ward_type']
    if data.get('floor') is not None: ward.floor     = data['floor']
    if data.get('charge_per_day') is not None:
        ward.charge_per_day = float(data['charge_per_day'])
    if data.get('description') is not None: ward.description = data['description']
    db.session.commit()
    log_action(user_id=current_user.id, action='UPDATE_WARD', module='admin',
               description=f'Ward updated: {ward.name}')
    return jsonify({'success': True, 'message': 'Ward updated!'})


@admin_bp.route('/api/wards/<int:wid>/deactivate', methods=['POST'])
@admin_required
def api_deactivate_ward(wid):
    ward = Ward.query.get_or_404(wid)
    occupied = Bed.query.filter_by(ward_id=wid, status='occupied').count()
    if occupied:
        return jsonify({'success': False,
                        'message': f'Cannot deactivate: {occupied} bed(s) still occupied'}), 409
    ward.is_active = False
    db.session.commit()
    return jsonify({'success': True, 'message': f'Ward "{ward.name}" deactivated'})


@admin_bp.route('/api/beds')
@admin_required
def api_beds():
    ward_id = request.args.get('ward_id')
    status  = request.args.get('status')
    q = Bed.query.join(Ward).filter(Bed.is_active == True)
    if ward_id:
        q = q.filter(Bed.ward_id == int(ward_id))
    if status:
        q = q.filter(Bed.status == status)
    beds = q.order_by(Ward.name, Bed.bed_number).all()
    return jsonify({'success': True, 'beds': [{
        'id': b.id, 'bed_number': b.bed_number,
        'ward_id': b.ward_id, 'ward_name': b.ward.name if b.ward else '',
        'ward_type': b.ward.ward_type if b.ward else '',
        'bed_type': b.bed_type, 'status': b.status,
        'features': b.features or '',
    } for b in beds]})


@admin_bp.route('/api/beds/create', methods=['POST'])
@admin_required
def api_create_bed():
    data = request.get_json() or {}
    if not data.get('ward_id') or not data.get('bed_number'):
        return jsonify({'success': False, 'message': 'ward_id and bed_number are required'}), 400
    ward = Ward.query.get_or_404(int(data['ward_id']))
    # Check duplicate bed number in same ward
    existing = Bed.query.filter_by(ward_id=ward.id,
                                   bed_number=data['bed_number'].strip()).first()
    if existing:
        return jsonify({'success': False,
                        'message': f'Bed {data["bed_number"]} already exists in {ward.name}'}), 409
    bed = Bed(
        bed_number = data['bed_number'].strip(),
        ward_id    = ward.id,
        bed_type   = data.get('bed_type', 'standard'),
        status     = 'available',
        features   = data.get('features', ''),
        is_active  = True,
    )
    db.session.add(bed)
    db.session.commit()
    log_action(user_id=current_user.id, action='CREATE_BED', module='admin',
               description=f'Bed {bed.bed_number} added to {ward.name}')
    return jsonify({'success': True,
                    'message': f'Bed {bed.bed_number} added to {ward.name}!',
                    'bed_id': bed.id})


@admin_bp.route('/api/beds/bulk-create', methods=['POST'])
@admin_required
def api_bulk_create_beds():
    data     = request.get_json() or {}
    ward_id  = data.get('ward_id')
    prefix   = data.get('prefix', 'B')
    start    = int(data.get('start', 1))
    count    = min(int(data.get('count', 1)), 50)  # max 50 at once
    bed_type = data.get('bed_type', 'standard')
    if not ward_id:
        return jsonify({'success': False, 'message': 'ward_id required'}), 400
    ward    = Ward.query.get_or_404(int(ward_id))
    created = 0
    skipped = 0
    for i in range(start, start + count):
        num = f'{prefix}{i:02d}'
        if Bed.query.filter_by(ward_id=ward.id, bed_number=num).first():
            skipped += 1
            continue
        db.session.add(Bed(bed_number=num, ward_id=ward.id,
                           bed_type=bed_type, status='available', is_active=True))
        created += 1
    db.session.commit()
    log_action(user_id=current_user.id, action='BULK_CREATE_BEDS', module='admin',
               description=f'{created} beds created in {ward.name}')
    msg = f'{created} beds created in {ward.name}'
    if skipped:
        msg += f' ({skipped} skipped — already exist)'
    return jsonify({'success': True, 'message': msg, 'created': created})


@admin_bp.route('/api/beds/<int:bid>/status', methods=['POST'])
@admin_required
def api_update_bed_status(bid):
    bed    = Bed.query.get_or_404(bid)
    data   = request.get_json() or {}
    status = data.get('status')
    allowed = ['available', 'occupied', 'cleaning', 'maintenance', 'reserved']
    if status not in allowed:
        return jsonify({'success': False, 'message': f'Status must be one of: {allowed}'}), 400
    if bed.status == 'occupied' and status != 'occupied':
        # Check if patient is still admitted
        from app.models.clinical import Admission
        active = Admission.query.filter_by(bed_id=bid, status='admitted').first()
        if active:
            return jsonify({'success': False,
                            'message': 'Bed has an active admission. Discharge patient first.'}), 409
    old_status = bed.status
    bed.status = status
    db.session.commit()
    # Broadcast via Socket.IO
    try:
        from app import socketio
        from app.sockets.bed_status import broadcast_bed_update
        broadcast_bed_update(socketio, bid, status)
    except Exception:
        pass
    log_action(user_id=current_user.id, action='UPDATE_BED_STATUS', module='admin',
               description=f'Bed {bed.bed_number} status: {old_status} → {status}')
    return jsonify({'success': True, 'message': f'Bed {bed.bed_number} set to {status}'})


@admin_bp.route('/api/beds/<int:bid>', methods=['PUT'])
@admin_required
def api_update_bed(bid):
    bed  = Bed.query.get_or_404(bid)
    data = request.get_json() or {}
    if data.get('bed_type'):   bed.bed_type = data['bed_type']
    if data.get('features') is not None: bed.features = data['features']
    if data.get('bed_number'): bed.bed_number = data['bed_number'].strip()
    db.session.commit()
    return jsonify({'success': True, 'message': 'Bed updated!'})


@admin_bp.route('/api/beds/<int:bid>/deactivate', methods=['POST'])
@admin_required
def api_deactivate_bed(bid):
    bed = Bed.query.get_or_404(bid)
    if bed.status == 'occupied':
        return jsonify({'success': False, 'message': 'Cannot deactivate occupied bed'}), 409
    bed.is_active = False
    db.session.commit()
    return jsonify({'success': True, 'message': f'Bed {bed.bed_number} deactivated'})


@admin_bp.route('/api/admissions')
@admin_required
def api_admissions():
    from app.models.clinical import Admission
    status = request.args.get('status', 'admitted')
    admissions = Admission.query.filter_by(status=status)        .order_by(Admission.admission_date.desc()).limit(100).all()
    result = []
    for a in admissions:
        result.append({
            'id': a.id,
            'admission_no': a.admission_no,
            'patient': a.patient.full_name if a.patient else '',
            'uhid': a.patient.uhid if a.patient else '',
            'doctor': a.doctor.user.full_name if a.doctor and a.doctor.user else '',
            'ward': a.ward.name if a.ward else '',
            'bed': a.bed.bed_number if a.bed else '',
            'admission_date': a.admission_date.strftime('%d %b %Y %H:%M'),
            'reason': a.admission_reason or '',
            'status': a.status,
        })
    return jsonify({'success': True, 'admissions': result})


@admin_bp.route('/api/bed-stats')
@admin_required
def api_bed_stats():
    stats = {
        'total':       Bed.query.filter_by(is_active=True).count(),
        'available':   Bed.query.filter_by(status='available', is_active=True).count(),
        'occupied':    Bed.query.filter_by(status='occupied').count(),
        'cleaning':    Bed.query.filter_by(status='cleaning').count(),
        'maintenance': Bed.query.filter_by(status='maintenance').count(),
        'reserved':    Bed.query.filter_by(status='reserved').count(),
        'total_wards': Ward.query.filter_by(is_active=True).count(),
    }
    stats['occupancy_pct'] = round(
        stats['occupied'] / stats['total'] * 100, 1) if stats['total'] else 0
    return jsonify({'success': True, 'stats': stats})
