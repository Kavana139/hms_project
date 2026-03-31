"""
MediCore HMS — Patient Portal Routes
Mobile-first with email/phone login, OTP, and rich features
"""
from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from datetime import datetime, date, timedelta
import secrets
import re

from app import db
from app.models.user import User, Role, HospitalSetting
from app.models.patient import Patient, PatientAllergy, PatientChronicCondition
from app.models.doctor import Doctor, Department, DoctorSchedule
from app.models.appointment import Appointment, Visit, SOAPNote, Vital
from app.models.pharmacy import Prescription, PrescriptionItem, Drug
from app.models.clinical import (LabOrder, LabOrderItem, LabTest,
    Invoice, InvoiceItem, Payment, Notification)

patient_bp = Blueprint('patient', __name__)

# ── OTP Store (in-memory, replace with Redis in production) ───
_otp_store = {}  # {identifier: {otp, expires, user_id}}


def patient_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_patient_role():
            return jsonify({'success': False, 'message': 'Patient access required'}), 403
        return f(*args, **kwargs)
    return decorated


def get_patient():
    return Patient.query.filter_by(user_id=current_user.id).first()


# ── Mobile Login Page ─────────────────────────────────────────

@patient_bp.route('/login')
def mobile_login():
    if current_user.is_authenticated and current_user.is_patient_role():
        return render_template('patient/app.html')
    return render_template('patient/login.html')


@patient_bp.route('/app')
@patient_required
def app_view():
    return render_template('patient/app.html')


@patient_bp.route('/dashboard')
@patient_required
def dashboard():
    return render_template('patient/app.html')


# ── Auth: Self Registration ───────────────────────────────────

@patient_bp.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json() or {}
    required = ['first_name', 'last_name', 'phone', 'email', 'password', 'gender']
    for f in required:
        if not data.get(f):
            return jsonify({'success': False, 'message': f'{f} is required'}), 400

    email = data['email'].strip().lower()
    phone = data['phone'].strip()

    # Check duplicates
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Email already registered'}), 409
    if Patient.query.filter_by(phone=phone).first():
        return jsonify({'success': False, 'message': 'Phone number already registered'}), 409

    # Create user
    role = Role.query.filter_by(name='patient').first()
    if not role:
        return jsonify({'success': False, 'message': 'Patient role not found'}), 500

    user = User(
        username    = email.split('@')[0] + str(secrets.randbelow(9999)),
        email       = email,
        phone       = phone,
        role_id     = role.id,
        first_name  = data['first_name'].strip(),
        last_name   = data['last_name'].strip(),
        gender      = data.get('gender'),
        is_active   = True,
        is_verified = False,
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.flush()

    # Generate UHID
    prefix = HospitalSetting.get('uhid_prefix', 'MED')
    year   = datetime.utcnow().year
    count  = Patient.query.count() + 1
    uhid   = f'{prefix}-{year}{count:04d}'

    dob = None
    if data.get('date_of_birth'):
        try: dob = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
        except: pass

    patient = Patient(
        user_id        = user.id,
        uhid           = uhid,
        first_name     = data['first_name'].strip(),
        last_name      = data['last_name'].strip(),
        date_of_birth  = dob,
        gender         = data.get('gender'),
        blood_group    = data.get('blood_group', 'unknown'),
        phone          = phone,
        email          = email,
        address        = data.get('address', ''),
        city           = data.get('city', ''),
        state          = data.get('state', ''),
    )
    db.session.add(patient)
    db.session.commit()

    # Send OTP for verification
    _send_otp(email, user.id, channel='email')

    return jsonify({'success': True,
                    'message': f'Registration successful! Your UHID is {uhid}. Check your email for verification.',
                    'uhid': uhid})


# ── Auth: Login with email or phone ──────────────────────────

@patient_bp.route('/api/login', methods=['POST'])
def api_login():
    data       = request.get_json() or {}
    identifier = (data.get('identifier') or data.get('email') or data.get('phone') or '').strip()
    password   = data.get('password', '')

    if not identifier or not password:
        return jsonify({'success': False, 'message': 'Email/phone and password required'}), 400

    # Find user by email or phone
    user = (User.query.filter_by(email=identifier.lower()).first() or
            User.query.filter_by(phone=identifier).first())

    if not user or not user.is_patient_role():
        return jsonify({'success': False, 'message': 'No patient account found with this email/phone'}), 401

    if not user.is_active:
        return jsonify({'success': False, 'message': 'Account deactivated. Contact hospital.'}), 401

    if user.is_locked():
        remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
        return jsonify({'success': False, 'message': f'Account locked. Try again in {remaining} minutes.'}), 401

    if not user.check_password(password):
        user.login_attempts = (user.login_attempts or 0) + 1
        if user.login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        db.session.commit()
        remaining = 5 - user.login_attempts
        return jsonify({'success': False,
                        'message': f'Invalid password. {max(0,remaining)} attempts remaining.'}), 401

    user.login_attempts = 0
    user.locked_until   = None
    user.last_login     = datetime.utcnow()
    db.session.commit()

    login_user(user, remember=True, duration=timedelta(days=30))
    patient = Patient.query.filter_by(user_id=user.id).first()

    return jsonify({
        'success':  True,
        'message':  f'Welcome back, {user.first_name}!',
        'redirect': '/patient/app',
        'patient': patient.to_dict() if patient else None,
    })


# ── Auth: Send OTP ────────────────────────────────────────────

@patient_bp.route('/api/send-otp', methods=['POST'])
def send_otp():
    data       = request.get_json() or {}
    identifier = (data.get('identifier') or '').strip()
    channel    = data.get('channel', 'email')  # email or sms

    if not identifier:
        return jsonify({'success': False, 'message': 'Email or phone required'}), 400

    user = (User.query.filter_by(email=identifier.lower()).first() or
            User.query.filter_by(phone=identifier).first())

    if not user:
        return jsonify({'success': True, 'message': 'If account exists, OTP has been sent.'})

    _send_otp(identifier, user.id, channel=channel)
    return jsonify({'success': True, 'message': f'OTP sent to your {channel}.'})


# ── Auth: Verify OTP ──────────────────────────────────────────

@patient_bp.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data       = request.get_json() or {}
    identifier = (data.get('identifier') or '').strip()
    otp        = (data.get('otp') or '').strip()
    purpose    = data.get('purpose', 'verify')  # verify or reset

    stored = _otp_store.get(identifier)
    if not stored:
        return jsonify({'success': False, 'message': 'OTP expired or not found'}), 400
    if datetime.utcnow() > stored['expires']:
        del _otp_store[identifier]
        return jsonify({'success': False, 'message': 'OTP expired. Request a new one.'}), 400
    if stored['otp'] != otp:
        return jsonify({'success': False, 'message': 'Invalid OTP. Please try again.'}), 400

    user = User.query.get(stored['user_id'])
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    del _otp_store[identifier]

    if purpose == 'verify':
        user.is_verified = True
        db.session.commit()
        login_user(user, remember=True, duration=timedelta(days=30))
        return jsonify({'success': True, 'message': 'Account verified! Welcome to MediCore.',
                        'redirect': '/patient/app'})
    elif purpose == 'reset':
        session['reset_user_id'] = user.id
        return jsonify({'success': True, 'message': 'OTP verified. Set your new password.',
                        'can_reset': True})

    return jsonify({'success': True})


# ── Auth: Reset Password ──────────────────────────────────────

@patient_bp.route('/api/reset-password', methods=['POST'])
def reset_password():
    data     = request.get_json() or {}
    user_id  = session.get('reset_user_id')
    new_pwd  = data.get('password', '')
    confirm  = data.get('confirm_password', '')

    if not user_id:
        return jsonify({'success': False, 'message': 'Session expired. Request OTP again.'}), 400
    if len(new_pwd) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters.'}), 400
    if new_pwd != confirm:
        return jsonify({'success': False, 'message': 'Passwords do not match.'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    user.set_password(new_pwd)
    user.login_attempts = 0
    user.locked_until   = None
    session.pop('reset_user_id', None)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Password reset successfully! Please login.'})


# ── Auth: Logout ──────────────────────────────────────────────

@patient_bp.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return jsonify({'success': True, 'redirect': '/patient/login'})


# ── Profile ───────────────────────────────────────────────────

@patient_bp.route('/api/profile')
@patient_required
def api_profile():
    p = get_patient()
    if not p:
        return jsonify({'success': True, 'patient': None})
    allergies  = PatientAllergy.query.filter_by(patient_id=p.id).all()
    conditions = PatientChronicCondition.query.filter_by(patient_id=p.id).all()
    last_vitals = Vital.query.filter_by(patient_id=p.id).order_by(
        Vital.recorded_at.desc()).first()
    return jsonify({'success': True, 'patient': {
        'id': p.id, 'uhid': p.uhid, 'full_name': p.full_name,
        'age': p.age, 'gender': p.gender, 'blood_group': p.blood_group,
        'phone': p.phone, 'email': p.email,
        'date_of_birth': p.date_of_birth.isoformat() if p.date_of_birth else None,
        'address': p.address, 'city': p.city, 'state': p.state,
        'insurance_provider': p.insurance_provider or '',
        'allergies':   [{'allergen': a.allergen, 'severity': a.severity} for a in allergies],
        'conditions':  [{'condition': c.condition, 'icd10_code': c.icd10_code} for c in conditions],
        'last_vitals': last_vitals.to_dict() if last_vitals else None,
        'is_verified': current_user.is_verified,
    }})


@patient_bp.route('/api/profile/update', methods=['POST'])
@patient_required
def update_profile():
    p    = get_patient()
    data = request.get_json() or {}
    if not p:
        return jsonify({'success': False, 'message': 'Profile not found'}), 404
    for field in ['address', 'city', 'state', 'pincode',
                  'emergency_phone', 'occupation', 'blood_group']:
        if field in data:
            setattr(p, field, data[field])
    if data.get('date_of_birth'):
        try:
            p.date_of_birth = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
        except: pass
    db.session.commit()
    return jsonify({'success': True, 'message': 'Profile updated!'})


# ── Appointments ──────────────────────────────────────────────

@patient_bp.route('/api/appointments')
@patient_required
def api_appointments():
    p = get_patient()
    if not p:
        return jsonify({'success': True, 'upcoming': [], 'past': []})
    today    = date.today()
    upcoming = Appointment.query.filter(
        Appointment.patient_id == p.id,
        Appointment.appointment_date >= today,
        Appointment.status.notin_(['cancelled'])
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()
    past = Appointment.query.filter(
        Appointment.patient_id == p.id,
        Appointment.appointment_date < today,
    ).order_by(Appointment.appointment_date.desc()).limit(20).all()

    def fmt(a):
        doc = Doctor.query.get(a.doctor_id)
        dept = Department.query.get(a.department_id) if a.department_id else None
        return {
            'id': a.id,
            'appointment_no': a.appointment_no,
            'date': a.appointment_date.strftime('%d %b %Y'),
            'date_iso': a.appointment_date.isoformat(),
            'time': a.appointment_time.strftime('%H:%M') if a.appointment_time else '',
            'doctor': doc.full_name if doc else '?',
            'doctor_id': doc.id if doc else None,
            'specialization': doc.specialization if doc else '',
            'department': dept.name if dept else '',
            'token': a.token_number,
            'type': a.appt_type,
            'status': a.status,
            'reason': a.reason or '',
        }
    return jsonify({'success': True,
                    'upcoming': [fmt(a) for a in upcoming],
                    'past':     [fmt(a) for a in past]})


@patient_bp.route('/api/appointments/book', methods=['POST'])
@patient_required
def book_appointment():
    p    = get_patient()
    data = request.get_json() or {}
    if not p:
        return jsonify({'success': False, 'message': 'Patient profile not found'}), 404
    required = ['doctor_id', 'appointment_date', 'appointment_time']
    for f in required:
        if not data.get(f):
            return jsonify({'success': False, 'message': f'{f} is required'}), 400
    try:
        appt_date = datetime.strptime(data['appointment_date'], '%Y-%m-%d').date()
        appt_time = datetime.strptime(data['appointment_time'], '%H:%M').time()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date/time format'}), 400
    if appt_date < date.today():
        return jsonify({'success': False, 'message': 'Cannot book appointments in the past'}), 400
    existing = Appointment.query.filter_by(
        doctor_id=data['doctor_id'],
        appointment_date=appt_date,
        appointment_time=appt_time,
    ).filter(Appointment.status.notin_(['cancelled'])).first()
    if existing:
        return jsonify({'success': False, 'message': 'This slot is already booked. Please choose another.'}), 409
    token = (db.session.query(
        db.func.coalesce(db.func.max(Appointment.token_number), 0)
    ).filter_by(doctor_id=data['doctor_id'],
                appointment_date=appt_date).scalar() or 0) + 1
    doc = Doctor.query.get(data['doctor_id'])
    appt = Appointment(
        appointment_no   = f'APT{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
        patient_id       = p.id,
        doctor_id        = int(data['doctor_id']),
        department_id    = doc.department_id if doc else None,
        appointment_date = appt_date,
        appointment_time = appt_time,
        token_number     = token,
        appt_type        = data.get('type', 'new'),
        status           = 'confirmed',
        reason           = data.get('reason', ''),
        booked_by        = current_user.id,
    )
    db.session.add(appt)
    db.session.commit()
    # In-app notification
    db.session.add(Notification(
        user_id=current_user.id,
        title='Appointment Confirmed',
        message=f'Your appointment with {doc.full_name if doc else "Doctor"} on {appt_date.strftime("%d %b")} at {appt_time.strftime("%H:%M")} is confirmed. Token #{token}',
        notif_type='success', module='appointment', reference_id=appt.id))
    db.session.commit()
    return jsonify({'success': True,
                    'message': f'Appointment booked successfully! Token #{token}',
                    'token': token,
                    'appointment_no': appt.appointment_no,
                    'date': appt_date.strftime('%d %b %Y'),
                    'time': appt_time.strftime('%H:%M'),
                    'doctor': doc.full_name if doc else '?'})


@patient_bp.route('/api/appointments/<int:aid>/cancel', methods=['POST'])
@patient_required
def cancel_appointment(aid):
    p    = get_patient()
    appt = Appointment.query.get_or_404(aid)
    if appt.patient_id != p.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    if appt.status in ['completed', 'in_progress']:
        return jsonify({'success': False, 'message': 'Cannot cancel an active or completed appointment'}), 400
    appt.status        = 'cancelled'
    appt.cancel_reason = 'Cancelled by patient via portal'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Appointment cancelled successfully.'})


# ── Doctors ───────────────────────────────────────────────────

@patient_bp.route('/api/doctors')
@patient_required
def api_doctors():
    dept_id = request.args.get('department_id')
    search  = request.args.get('search', '')
    q = Doctor.query.join(User).filter(Doctor.is_available == True)
    if dept_id:
        q = q.filter(Doctor.department_id == int(dept_id))
    if search:
        q = q.filter(db.or_(
            User.first_name.ilike(f'%{search}%'),
            User.last_name.ilike(f'%{search}%'),
            Doctor.specialization.ilike(f'%{search}%'),
        ))
    doctors = q.all()
    result  = []
    for doc in doctors:
        dept = Department.query.get(doc.department_id) if doc.department_id else None
        # Count appointments for a simple "experience" indicator
        total_appts = Appointment.query.filter_by(
            doctor_id=doc.id, status='completed').count()
        result.append({
            'id':              doc.id,
            'full_name':       doc.full_name,
            'specialization':  doc.specialization or '',
            'qualification':   doc.qualification or '',
            'experience_years':doc.experience_years or 0,
            'department':      dept.name if dept else '',
            'department_id':   doc.department_id,
            'consultation_fee':float(doc.consultation_fee or 0),
            'bio':             doc.bio or '',
            'total_patients':  total_appts,
        })
    return jsonify({'success': True, 'doctors': result})


@patient_bp.route('/api/doctors/<int:did>/slots')
@patient_required
def doctor_slots(did):
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'success': False, 'message': 'date required'}), 400
    try:
        appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date'}), 400
    if appt_date < date.today():
        return jsonify({'success': True, 'slots': [], 'message': 'Cannot book past dates'})
    day_name = appt_date.strftime('%A').lower()
    schedule = DoctorSchedule.query.filter_by(
        doctor_id=did, day_of_week=day_name, is_active=True).first()
    if not schedule:
        return jsonify({'success': True, 'slots': [],
                        'message': f'Doctor not available on {appt_date.strftime("%A")}s'})
    from datetime import datetime as dt
    slots   = []
    current = dt.combine(appt_date, schedule.start_time)
    end_dt  = dt.combine(appt_date, schedule.end_time)
    booked  = {a.appointment_time.strftime('%H:%M')
               for a in Appointment.query.filter_by(
                   doctor_id=did, appointment_date=appt_date
               ).filter(Appointment.status.notin_(['cancelled'])).all()}
    while current < end_dt:
        slot_str = current.strftime('%H:%M')
        slots.append({'time': slot_str, 'available': slot_str not in booked})
        current += timedelta(minutes=schedule.slot_duration)
    return jsonify({'success': True, 'slots': slots,
                    'doctor': Doctor.query.get(did).full_name,
                    'fee': float(Doctor.query.get(did).consultation_fee or 0)})


@patient_bp.route('/api/doctors/<int:did>/schedule')
@patient_required
def doctor_weekly_schedule(did):
    schedules = DoctorSchedule.query.filter_by(doctor_id=did, is_active=True).all()
    return jsonify({'success': True, 'schedules': [{
        'day': s.day_of_week,
        'start': s.start_time.strftime('%H:%M'),
        'end': s.end_time.strftime('%H:%M'),
        'slots': s.slot_duration,
    } for s in schedules]})


@patient_bp.route('/api/departments')
@patient_required
def api_departments():
    depts = Department.query.filter_by(is_active=True).all()
    return jsonify({'success': True,
                    'departments': [{'id': d.id, 'name': d.name,
                                     'floor': d.floor} for d in depts]})


# ── Medical Records ───────────────────────────────────────────

@patient_bp.route('/api/visits')
@patient_required
def api_visits():
    p = get_patient()
    if not p:
        return jsonify({'success': True, 'visits': []})
    visits = Visit.query.filter_by(patient_id=p.id).order_by(
        Visit.visit_date.desc()).limit(30).all()
    result = []
    for v in visits:
        doc  = Doctor.query.get(v.doctor_id)
        soap = SOAPNote.query.filter_by(visit_id=v.id).first()
        result.append({
            'id':              v.id,
            'date':            v.visit_date.strftime('%d %b %Y'),
            'date_iso':        v.visit_date.date().isoformat(),
            'doctor':          doc.full_name if doc else '?',
            'specialization':  doc.specialization if doc else '',
            'chief_complaint': v.chief_complaint or '',
            'diagnosis':       soap.assessment if soap else '',
            'icd10':           soap.icd10_code if soap else '',
            'icd10_desc':      soap.icd10_desc if soap else '',
            'plan':            soap.plan if soap else '',
            'follow_up_days':  soap.follow_up_days if soap else None,
            'follow_up_date':  soap.follow_up_date.isoformat() if (soap and soap.follow_up_date) else None,
        })
    return jsonify({'success': True, 'visits': result})


@patient_bp.route('/api/vitals/history')
@patient_required
def vitals_history():
    p = get_patient()
    if not p:
        return jsonify({'success': True, 'vitals': []})
    vitals = Vital.query.filter_by(patient_id=p.id).order_by(
        Vital.recorded_at.asc()).limit(20).all()
    return jsonify({'success': True, 'vitals': [{
        'date':        v.recorded_at.strftime('%d %b'),
        'date_iso':    v.recorded_at.date().isoformat(),
        'systolic_bp': v.systolic_bp,
        'diastolic_bp':v.diastolic_bp,
        'pulse_rate':  v.pulse_rate,
        'temperature': float(v.temperature) if v.temperature else None,
        'spo2':        v.spo2,
        'weight_kg':   float(v.weight_kg) if v.weight_kg else None,
        'bmi':         float(v.bmi) if v.bmi else None,
        'blood_sugar': float(v.blood_sugar) if v.blood_sugar else None,
    } for v in vitals]})


@patient_bp.route('/api/prescriptions')
@patient_required
def api_prescriptions():
    p = get_patient()
    if not p:
        return jsonify({'success': True, 'prescriptions': []})
    rxs = Prescription.query.filter_by(patient_id=p.id).order_by(
        Prescription.created_at.desc()).limit(20).all()
    result = []
    for rx in rxs:
        doc   = Doctor.query.get(rx.doctor_id)
        items = PrescriptionItem.query.filter_by(prescription_id=rx.id).all()
        result.append({
            'id':              rx.id,
            'prescription_no': rx.prescription_no,
            'date':            rx.created_at.strftime('%d %b %Y'),
            'doctor':          doc.full_name if doc else '?',
            'status':          rx.status,
            'notes':           rx.notes or '',
            'drugs': [{
                'name':         Drug.query.get(i.drug_id).name if Drug.query.get(i.drug_id) else '?',
                'generic':      Drug.query.get(i.drug_id).generic_name if Drug.query.get(i.drug_id) else '',
                'drug_type':    Drug.query.get(i.drug_id).drug_type if Drug.query.get(i.drug_id) else '',
                'dosage':       i.dosage or '',
                'frequency':    i.frequency or '',
                'duration':     i.duration or '',
                'quantity':     i.quantity,
                'instructions': i.instructions or '',
                'is_dispensed': i.is_dispensed,
            } for i in items],
        })
    return jsonify({'success': True, 'prescriptions': result})


@patient_bp.route('/api/lab-reports')
@patient_required
def api_lab_reports():
    p = get_patient()
    if not p:
        return jsonify({'success': True, 'reports': []})
    orders = LabOrder.query.filter_by(
        patient_id=p.id, status='completed'
    ).order_by(LabOrder.completed_at.desc()).limit(20).all()
    result = []
    for o in orders:
        doc   = Doctor.query.get(o.doctor_id)
        items = LabOrderItem.query.filter_by(order_id=o.id).all()
        result.append({
            'id':           o.id,
            'order_no':     o.order_no,
            'date':         o.completed_at.strftime('%d %b %Y') if o.completed_at else '—',
            'date_iso':     o.completed_at.date().isoformat() if o.completed_at else '',
            'doctor':       doc.full_name if doc else '?',
            'has_critical': any(i.is_critical for i in items),
            'test_count':   len(items),
            'tests': [{
                'name':     LabTest.query.get(i.test_id).name if LabTest.query.get(i.test_id) else '?',
                'result':   i.result_value or '—',
                'unit':     i.result_unit or '',
                'normal':   i.normal_range or '',
                'flag':     i.flag,
                'critical': i.is_critical,
            } for i in items],
        })
    return jsonify({'success': True, 'reports': result})


# ── Bills & Payments ──────────────────────────────────────────

@patient_bp.route('/api/bills')
@patient_required
def api_bills():
    p = get_patient()
    if not p:
        return jsonify({'success': True, 'bills': []})
    invoices = Invoice.query.filter_by(patient_id=p.id).order_by(
        Invoice.created_at.desc()).limit(20).all()
    result = []
    for inv in invoices:
        items = InvoiceItem.query.filter_by(invoice_id=inv.id).all()
        result.append({
            'id':          inv.id,
            'invoice_no':  inv.invoice_no,
            'date':        inv.invoice_date.strftime('%d %b %Y') if inv.invoice_date else '—',
            'subtotal':    float(inv.subtotal),
            'discount':    float(inv.discount_amt),
            'gst':         float(inv.gst_amount),
            'total':       float(inv.total_amount),
            'paid':        float(inv.paid_amount),
            'balance':     float(inv.balance),
            'status':      inv.status,
            'items': [{
                'description': i.description,
                'type':        i.item_type,
                'qty':         i.quantity,
                'price':       float(i.unit_price),
                'total':       float(i.total_price),
            } for i in items],
        })
    return jsonify({'success': True, 'bills': result})


# ── Notifications ─────────────────────────────────────────────

@patient_bp.route('/api/notifications')
@patient_required
def api_notifications():
    notifs = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(30).all()
    unread = Notification.query.filter_by(
        user_id=current_user.id, is_read=False).count()
    return jsonify({'success': True,
                    'notifications': [n.to_dict() for n in notifs],
                    'unread': unread})


@patient_bp.route('/api/notifications/mark-read', methods=['POST'])
@patient_required
def mark_read():
    Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({'is_read': True, 'read_at': datetime.utcnow()})
    db.session.commit()
    return jsonify({'success': True})


# ── Summary (home screen) ─────────────────────────────────────

@patient_bp.route('/api/summary')
@patient_required
def api_summary():
    p = get_patient()
    if not p:
        return jsonify({'success': True, 'summary': {}})
    today    = date.today()
    upcoming = Appointment.query.filter(
        Appointment.patient_id == p.id,
        Appointment.appointment_date >= today,
        Appointment.status.notin_(['cancelled'])
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).first()
    last_vitals = Vital.query.filter_by(patient_id=p.id).order_by(
        Vital.recorded_at.desc()).first()
    pending_bills = Invoice.query.filter_by(
        patient_id=p.id
    ).filter(Invoice.balance > 0).count()
    lab_count = LabOrder.query.filter_by(
        patient_id=p.id, status='completed').count()
    unread = Notification.query.filter_by(
        user_id=current_user.id, is_read=False).count()
    doc = Doctor.query.get(upcoming.doctor_id) if upcoming else None
    return jsonify({'success': True, 'summary': {
        'patient_name':   p.first_name,
        'uhid':           p.uhid,
        'blood_group':    p.blood_group,
        'upcoming_appt':  {
            'date':   upcoming.appointment_date.strftime('%d %b %Y'),
            'time':   upcoming.appointment_time.strftime('%H:%M') if upcoming.appointment_time else '',
            'doctor': doc.full_name if doc else '',
            'token':  upcoming.token_number,
            'id':     upcoming.id,
        } if upcoming else None,
        'last_vitals':    last_vitals.to_dict() if last_vitals else None,
        'pending_bills':  pending_bills,
        'lab_reports':    lab_count,
        'notifications':  unread,
        'allergies':      PatientAllergy.query.filter_by(patient_id=p.id).count(),
    }})


# ── Helpers ───────────────────────────────────────────────────

def _send_otp(identifier, user_id, channel='email'):
    otp     = str(secrets.randbelow(900000) + 100000)  # 6-digit OTP
    expires = datetime.utcnow() + timedelta(minutes=10)
    _otp_store[identifier] = {'otp': otp, 'expires': expires, 'user_id': user_id}

    user = User.query.get(user_id)
    name = user.first_name if user else 'Patient'
    msg  = f'Your MediCore HMS verification code is: {otp}. Valid for 10 minutes.'

    if channel == 'email' and user and user.email:
        try:
            from app.services.notification_service import send_email
            send_email(user.email, 'MediCore HMS — Your OTP', msg)
        except Exception:
            pass

    if channel == 'sms' and user and user.phone:
        try:
            from app.services.notification_service import send_sms
            send_sms(user.phone, msg)
        except Exception:
            pass

    # Always save as in-app notification too
    db.session.add(Notification(
        user_id=user_id, title='Verification Code',
        message=f'Your OTP is: {otp} (valid 10 min)',
        notif_type='info', module='auth'))
    db.session.commit()


# ── PDF Downloads ─────────────────────────────────────────────

@patient_bp.route('/api/prescriptions/<int:rx_id>/pdf')
@patient_required
def download_prescription_pdf(rx_id):
    from flask import send_file, abort
    from app.models.pharmacy import Prescription
    import io
    p  = get_patient()
    rx = Prescription.query.get_or_404(rx_id)
    if rx.patient_id != p.id:
        abort(403)
    try:
        from app.services.pdf_service import generate_prescription_pdf
        pdf_bytes = generate_prescription_pdf(rx_id)
        if not pdf_bytes:
            return jsonify({'success': False, 'message': 'Could not generate PDF'}), 500
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'Prescription_{rx.prescription_no}.pdf'
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@patient_bp.route('/api/lab-reports/<int:order_id>/pdf')
@patient_required
def download_lab_pdf(order_id):
    from flask import send_file, abort
    import io
    p     = get_patient()
    order = LabOrder.query.get_or_404(order_id)
    if order.patient_id != p.id:
        abort(403)
    try:
        from app.services.pdf_service import generate_lab_report_pdf
        pdf_bytes = generate_lab_report_pdf(order_id)
        if not pdf_bytes:
            return jsonify({'success': False, 'message': 'Could not generate PDF'}), 500
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'LabReport_{order.order_no}.pdf'
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ── Razorpay Payment ──────────────────────────────────────────

@patient_bp.route('/api/bills/<int:inv_id>/pay', methods=['POST'])
@patient_required
def initiate_payment(inv_id):
    p   = get_patient()
    inv = Invoice.query.get_or_404(inv_id)
    if inv.patient_id != p.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    if float(inv.balance) <= 0:
        return jsonify({'success': False, 'message': 'Invoice already paid'}), 400
    try:
        from flask import current_app
        import razorpay
        key_id     = current_app.config.get('RAZORPAY_KEY_ID')
        key_secret = current_app.config.get('RAZORPAY_KEY_SECRET')
        if not key_id or not key_secret:
            return jsonify({'success': False, 'message': 'Payment gateway not configured. Contact hospital.'}), 400
        client = razorpay.Client(auth=(key_id, key_secret))
        amount = int(float(inv.balance) * 100)  # paise
        order  = client.order.create({
            'amount':   amount,
            'currency': 'INR',
            'receipt':  inv.invoice_no,
            'notes':    {'patient_id': str(p.id), 'invoice_id': str(inv_id)},
        })
        return jsonify({
            'success':    True,
            'order_id':   order['id'],
            'amount':     amount,
            'currency':   'INR',
            'key_id':     key_id,
            'patient_name': current_user.full_name,
            'email':      current_user.email,
            'phone':      current_user.phone or '',
            'invoice_no': inv.invoice_no,
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Payment error: {str(e)}'}), 500


@patient_bp.route('/api/bills/<int:inv_id>/payment-success', methods=['POST'])
@patient_required
def payment_success(inv_id):
    p    = get_patient()
    inv  = Invoice.query.get_or_404(inv_id)
    data = request.get_json() or {}
    if inv.patient_id != p.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    try:
        from flask import current_app
        import razorpay
        key_id     = current_app.config.get('RAZORPAY_KEY_ID')
        key_secret = current_app.config.get('RAZORPAY_KEY_SECRET')
        client     = razorpay.Client(auth=(key_id, key_secret))
        # Verify signature
        client.utility.verify_payment_signature({
            'razorpay_order_id':   data.get('razorpay_order_id', ''),
            'razorpay_payment_id': data.get('razorpay_payment_id', ''),
            'razorpay_signature':  data.get('razorpay_signature', ''),
        })
        # Record payment
        amt = float(inv.balance)
        pay = Payment(
            payment_no          = f'PAY{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
            invoice_id          = inv_id,
            patient_id          = p.id,
            amount              = amt,
            payment_mode        = 'razorpay',
            transaction_id      = data.get('razorpay_payment_id', ''),
            razorpay_order_id   = data.get('razorpay_order_id', ''),
            razorpay_payment_id = data.get('razorpay_payment_id', ''),
            status              = 'success',
        )
        inv.paid_amount = float(inv.paid_amount) + amt
        inv.balance     = 0
        inv.status      = 'paid'
        inv.payment_mode = 'razorpay'
        db.session.add(pay)
        # Notify
        db.session.add(Notification(
            user_id=current_user.id, title='Payment Successful',
            message=f'Payment of ₹{amt:.2f} for {inv.invoice_no} received. Thank you!',
            notif_type='success', module='billing'))
        db.session.commit()
        return jsonify({'success': True, 'message': f'Payment of ₹{amt:.2f} successful!'})
    except Exception as e:
        return jsonify({'success': False, 'message': 'Payment verification failed'}), 400


# ── Doctor Ratings ────────────────────────────────────────────

@patient_bp.route('/api/doctors/<int:did>/rate', methods=['POST'])
@patient_required
def rate_doctor(did):
    """Simple rating stored in DB as notification/audit"""
    data   = request.get_json() or {}
    rating = int(data.get('rating', 0))
    review = data.get('review', '').strip()
    if not 1 <= rating <= 5:
        return jsonify({'success': False, 'message': 'Rating must be 1-5'}), 400
    p   = get_patient()
    doc = Doctor.query.get_or_404(did)
    # Store as notification to doctor
    db.session.add(Notification(
        user_id    = doc.user_id,
        title      = f'New Rating: {"⭐"*rating}',
        message    = f'Patient {p.full_name} rated you {rating}/5. {review}',
        notif_type = 'info',
        module     = 'rating',
    ))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Thank you for your feedback!'})


# ── Health Timeline ────────────────────────────────────────────

@patient_bp.route('/api/timeline')
@patient_required
def health_timeline():
    """Combined health timeline — visits, lab, prescriptions, admissions"""
    p = get_patient()
    if not p:
        return jsonify({'success': True, 'timeline': []})
    events = []
    # Visits
    visits = Visit.query.filter_by(patient_id=p.id).order_by(
        Visit.visit_date.desc()).limit(30).all()
    for v in visits:
        doc  = Doctor.query.get(v.doctor_id)
        soap = SOAPNote.query.filter_by(visit_id=v.id).first()
        events.append({
            'type':  'visit',
            'date':  v.visit_date.isoformat(),
            'title': f'Visit — {doc.full_name if doc else "Doctor"}',
            'sub':   soap.assessment if soap else (v.chief_complaint or 'General consultation'),
            'icon':  'visit',
            'color': 'blue',
        })
    # Lab orders
    lab_orders = LabOrder.query.filter_by(
        patient_id=p.id, status='completed').order_by(
        LabOrder.completed_at.desc()).limit(15).all()
    for o in lab_orders:
        items = LabOrderItem.query.filter_by(order_id=o.id).all()
        has_critical = any(i.is_critical for i in items)
        events.append({
            'type':  'lab',
            'date':  o.completed_at.isoformat() if o.completed_at else o.ordered_at.isoformat(),
            'title': f'Lab Report — {len(items)} tests',
            'sub':   '⚠ Critical values found' if has_critical else 'All values normal',
            'icon':  'lab',
            'color': 'red' if has_critical else 'teal',
        })
    # Prescriptions
    rxs = Prescription.query.filter_by(patient_id=p.id).order_by(
        Prescription.created_at.desc()).limit(15).all()
    for rx in rxs:
        items = PrescriptionItem.query.filter_by(prescription_id=rx.id).all()
        doc   = Doctor.query.get(rx.doctor_id)
        events.append({
            'type':  'prescription',
            'date':  rx.created_at.isoformat(),
            'title': f'Prescription — {len(items)} medicines',
            'sub':   f'By {doc.full_name if doc else "Doctor"}',
            'icon':  'rx',
            'color': 'purple',
        })
    # Sort by date desc
    events.sort(key=lambda x: x['date'], reverse=True)
    return jsonify({'success': True, 'timeline': events[:40]})


# ── PDF Downloads ─────────────────────────────────────────────

@patient_bp.route('/api/prescriptions/<int:rx_id>/pdf')
@patient_required
def prescription_pdf(rx_id):
    from flask import Response
    from app.services.pdf_service import generate_prescription_pdf
    p   = get_patient()
    rx  = Prescription.query.get_or_404(rx_id)
    if rx.patient_id != p.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    doc = Doctor.query.get(rx.doctor_id)
    items = PrescriptionItem.query.filter_by(prescription_id=rx_id).all()
    hospital = {
        'name':    HospitalSetting.get('hospital_name', 'MediCore Hospital'),
        'address': HospitalSetting.get('hospital_address', ''),
        'phone':   HospitalSetting.get('hospital_phone', ''),
        'gst':     HospitalSetting.get('gst_number', ''),
    }
    rx_data = {
        'prescription_no': rx.prescription_no,
        'date':    rx.created_at.strftime('%d %b %Y'),
        'doctor':  doc.full_name if doc else '?',
        'department': doc.specialization if doc else '',
        'notes':   rx.notes or '',
        'drugs': [{
            'name':         Drug.query.get(i.drug_id).name if Drug.query.get(i.drug_id) else '?',
            'generic':      Drug.query.get(i.drug_id).generic_name if Drug.query.get(i.drug_id) else '',
            'dosage':       i.dosage or '', 'frequency': i.frequency or '',
            'duration':     i.duration or '', 'quantity':  i.quantity,
            'instructions': i.instructions or '',
        } for i in items],
    }
    patient_data = {
        'full_name':   p.full_name, 'uhid': p.uhid,
        'age':         p.age,       'gender': p.gender,
        'blood_group': p.blood_group,
    }
    pdf = generate_prescription_pdf(rx_data, patient_data, hospital)
    return Response(pdf, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename=Rx_{rx.prescription_no}.pdf'})


@patient_bp.route('/api/lab-reports/<int:order_id>/pdf')
@patient_required
def lab_report_pdf(order_id):
    from flask import Response
    from app.services.pdf_service import generate_lab_report_pdf
    p     = get_patient()
    order = LabOrder.query.get_or_404(order_id)
    if order.patient_id != p.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    doc   = Doctor.query.get(order.doctor_id)
    items = LabOrderItem.query.filter_by(order_id=order_id).all()
    hospital = {
        'name':    HospitalSetting.get('hospital_name', 'MediCore Hospital'),
        'address': HospitalSetting.get('hospital_address', ''),
    }
    report_data = {
        'order_no':     order.order_no,
        'ordered_at':   order.ordered_at.strftime('%d %b %Y %H:%M'),
        'completed_at': order.completed_at.strftime('%d %b %Y %H:%M') if order.completed_at else '—',
        'doctor':       doc.full_name if doc else '?',
        'tests': [{
            'name':     LabTest.query.get(i.test_id).name if LabTest.query.get(i.test_id) else '?',
            'result':   i.result_value or '—', 'unit': i.result_unit or '',
            'normal':   i.normal_range or '', 'flag': i.flag, 'critical': i.is_critical,
        } for i in items],
    }
    patient_data = {
        'full_name': p.full_name, 'uhid': p.uhid,
        'age': p.age, 'gender': p.gender, 'blood_group': p.blood_group,
    }
    pdf = generate_lab_report_pdf(report_data, patient_data, hospital)
    return Response(pdf, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename=LabReport_{order.order_no}.pdf'})


# ── Razorpay Payment ──────────────────────────────────────────

@patient_bp.route('/api/bills/<int:inv_id>/create-order', methods=['POST'])
@patient_required
def create_razorpay_order(inv_id):
    p   = get_patient()
    inv = Invoice.query.get_or_404(inv_id)
    if inv.patient_id != p.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    if float(inv.balance) <= 0:
        return jsonify({'success': False, 'message': 'No balance due'}), 400
    try:
        import razorpay
        key_id     = HospitalSetting.get('razorpay_key_id', '')
        key_secret = HospitalSetting.get('razorpay_key_secret', '')
        if not key_id or not key_secret:
            return jsonify({'success': False,
                            'message': 'Payment gateway not configured. Contact hospital.'}), 503
        client = razorpay.Client(auth=(key_id, key_secret))
        amount = int(float(inv.balance) * 100)  # paise
        order  = client.order.create({
            'amount':   amount,
            'currency': 'INR',
            'receipt':  inv.invoice_no,
            'notes':    {'invoice_id': inv_id, 'patient_uhid': p.uhid},
        })
        return jsonify({'success': True,
                        'order_id':   order['id'],
                        'amount':     amount,
                        'currency':   'INR',
                        'key_id':     key_id,
                        'invoice_no': inv.invoice_no,
                        'patient':    p.full_name,
                        'email':      p.email or '',
                        'phone':      p.phone or ''})
    except ImportError:
        return jsonify({'success': False,
                        'message': 'razorpay package not installed. Run: pip install razorpay'}), 503
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@patient_bp.route('/api/bills/<int:inv_id>/verify-payment', methods=['POST'])
@patient_required
def verify_razorpay_payment(inv_id):
    p    = get_patient()
    inv  = Invoice.query.get_or_404(inv_id)
    data = request.get_json() or {}
    if inv.patient_id != p.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    try:
        import razorpay
        key_secret = HospitalSetting.get('razorpay_key_secret', '')
        client     = razorpay.Client(auth=('', key_secret))
        client.utility.verify_payment_signature({
            'razorpay_order_id':   data.get('order_id'),
            'razorpay_payment_id': data.get('payment_id'),
            'razorpay_signature':  data.get('signature'),
        })
        # Record payment
        amt  = float(inv.balance)
        pay  = Payment(
            payment_no     = f'PAY{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
            invoice_id     = inv_id,
            patient_id     = p.id,
            amount         = amt,
            payment_mode   = 'online',
            transaction_id = data.get('payment_id'),
            status         = 'success',
        )
        inv.paid_amount = float(inv.paid_amount) + amt
        inv.balance     = 0
        inv.status      = 'paid'
        inv.payment_mode = 'online'
        db.session.add(pay)
        # Notify
        db.session.add(Notification(
            user_id=current_user.id, title='Payment Successful',
            message=f'Payment of ₹{amt:.2f} for {inv.invoice_no} received.',
            notif_type='success', module='billing'))
        db.session.commit()
        return jsonify({'success': True, 'message': 'Payment verified and recorded!'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Payment verification failed: {e}'}), 400


# ── Health Timeline ───────────────────────────────────────────

@patient_bp.route('/api/timeline')
@patient_required
def api_timeline():
    p = get_patient()
    if not p:
        return jsonify({'success': True, 'timeline': []})
    events = []
    # Visits
    visits = Visit.query.filter_by(patient_id=p.id).order_by(
        Visit.visit_date.desc()).limit(10).all()
    for v in visits:
        doc  = Doctor.query.get(v.doctor_id)
        soap = SOAPNote.query.filter_by(visit_id=v.id).first()
        events.append({
            'type':    'visit',
            'date':    v.visit_date.strftime('%d %b %Y'),
            'date_iso':v.visit_date.isoformat(),
            'title':   f'Visit — {doc.full_name if doc else "Doctor"}',
            'detail':  soap.assessment if soap else (v.chief_complaint or 'Consultation'),
            'icon':    'visit', 'color': 'blue',
        })
    # Prescriptions
    rxs = Prescription.query.filter_by(patient_id=p.id).order_by(
        Prescription.created_at.desc()).limit(8).all()
    for rx in rxs:
        doc = Doctor.query.get(rx.doctor_id)
        items = PrescriptionItem.query.filter_by(prescription_id=rx.id).all()
        events.append({
            'type':    'prescription',
            'date':    rx.created_at.strftime('%d %b %Y'),
            'date_iso':rx.created_at.date().isoformat(),
            'title':   f'Prescription — {rx.prescription_no}',
            'detail':  ', '.join([Drug.query.get(i.drug_id).name for i in items if Drug.query.get(i.drug_id)])[:60],
            'icon':    'rx', 'color': 'teal',
        })
    # Lab Reports
    labs = LabOrder.query.filter_by(patient_id=p.id, status='completed').order_by(
        LabOrder.completed_at.desc()).limit(8).all()
    for lab in labs:
        items = LabOrderItem.query.filter_by(order_id=lab.id).all()
        events.append({
            'type':    'lab',
            'date':    lab.completed_at.strftime('%d %b %Y') if lab.completed_at else '—',
            'date_iso':lab.completed_at.date().isoformat() if lab.completed_at else '',
            'title':   f'Lab Report — {lab.order_no}',
            'detail':  f'{len(items)} tests' + (' | ⚠ Critical values' if any(i.is_critical for i in items) else ''),
            'icon':    'lab', 'color': 'purple',
            'has_critical': any(i.is_critical for i in items),
            'order_id': lab.id,
        })
    # Sort by date descending
    events.sort(key=lambda e: e.get('date_iso',''), reverse=True)
    return jsonify({'success': True, 'timeline': events})


# ── Doctor Ratings ────────────────────────────────────────────

@patient_bp.route('/api/doctors/<int:did>/rate', methods=['POST'])
@patient_required
def rate_doctor(did):
    p    = get_patient()
    data = request.get_json() or {}
    rating  = int(data.get('rating', 0))
    comment = data.get('comment', '').strip()
    if not 1 <= rating <= 5:
        return jsonify({'success': False, 'message': 'Rating must be 1–5'}), 400
    # Check patient has visited this doctor
    visited = Appointment.query.filter_by(
        patient_id=p.id, doctor_id=did, status='completed'
    ).first()
    if not visited:
        return jsonify({'success': False,
                        'message': 'You can only rate doctors you have visited'}), 403
    try:
        from app.models.doctor import DoctorRating
        existing = DoctorRating.query.filter_by(
            doctor_id=did, patient_id=p.id).first()
        if existing:
            existing.rating  = rating
            existing.comment = comment
        else:
            db.session.add(DoctorRating(
                doctor_id=did, patient_id=p.id,
                rating=rating, comment=comment))
        # Update doctor average
        doc = Doctor.query.get_or_404(did)
        from app.models.doctor import DoctorRating as DR
        avg = db.session.query(db.func.avg(DR.rating)).filter_by(doctor_id=did).scalar()
        if avg: doc.rating = round(float(avg), 1)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Thank you for your rating!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@patient_bp.route('/api/doctors/<int:did>/ratings')
@patient_required
def doctor_ratings(did):
    try:
        from app.models.doctor import DoctorRating
        ratings = DoctorRating.query.filter_by(doctor_id=did).order_by(
            DoctorRating.created_at.desc()).limit(10).all()
        doc = Doctor.query.get_or_404(did)
        return jsonify({'success': True,
                        'average': float(doc.rating or 0),
                        'count':   len(ratings),
                        'ratings': [{
                            'rating':  r.rating,
                            'comment': r.comment or '',
                            'date':    r.created_at.strftime('%b %Y'),
                        } for r in ratings]})
    except Exception as e:
        return jsonify({'success': True, 'average': 0, 'count': 0, 'ratings': []})