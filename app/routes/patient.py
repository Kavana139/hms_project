"""
MediCore HMS — Patient Portal Routes  (FINAL COMPLETE)
=======================================================
Login   : Email OR Phone + Password
Auth    : OTP verify, Forgot password reset, Self-registration
Features:
  Book / view / cancel appointments with doctor slots
  Visit history with diagnosis & follow-up
  Prescriptions + PDF download
  Lab reports with results + PDF download
  Vitals history for Chart.js graphs
  Bills view + Razorpay online payment
  Health timeline (visits + prescriptions + lab)
  Doctor profiles with star ratings
  In-app notifications
  Profile view
"""

from flask import (Blueprint, render_template, request,
                   jsonify, session, Response, redirect, url_for)
from flask_login import (login_user, logout_user,
                          login_required, current_user)
from functools import wraps
from datetime import datetime, date, timedelta
import secrets

from app import db
from app.models.user        import User, Role, HospitalSetting
from app.models.patient     import (Patient, PatientAllergy,
                                    PatientChronicCondition)
from app.models.doctor      import (Doctor, Department,
                                    DoctorSchedule, DoctorRating)
from app.models.appointment import Appointment, Visit, SOAPNote, Vital
from app.models.pharmacy    import Prescription, PrescriptionItem, Drug
from app.models.clinical    import (LabOrder, LabOrderItem, LabTest,
                                    Invoice, InvoiceItem,
                                    Payment, Notification)

patient_bp = Blueprint('patient', __name__)

# In-memory OTP store — {identifier: {otp, expires, user_id}}
_otp_store: dict = {}


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────

def patient_required(f):
    """Decorator: requires patient role.
    Non-patient staff are redirected to patient login so their staff
    session is preserved — allows admin/doctor to simultaneously use
    the patient portal with a separate patient account.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.path.startswith('/patient/api/'):
                return jsonify({'success': False,
                                'message': 'Please log in.',
                                'redirect': '/patient/login'}), 401
            from flask import redirect, url_for
            return redirect(url_for('patient.mobile_login'))
        if not current_user.is_patient_role():
            if request.path.startswith('/patient/api/'):
                return jsonify({'success': False,
                                'message': 'Patient login required.',
                                'redirect': '/patient/login'}), 403
            from flask import redirect, url_for
            return redirect(url_for('patient.mobile_login'))
        return f(*args, **kwargs)
    return decorated


def _patient():
    """Return the Patient row linked to current user."""
    return Patient.query.filter_by(user_id=current_user.id).first()


def _hospital():
    """Return hospital details from settings."""
    return {
        'name':    HospitalSetting.get('hospital_name',    'MediCore Hospital'),
        'address': HospitalSetting.get('hospital_address', ''),
        'phone':   HospitalSetting.get('hospital_phone',   ''),
        'gst':     HospitalSetting.get('gst_number',       ''),
    }


def _send_otp(identifier: str, user_id: int, channel: str = 'email'):
    """Generate OTP, store it, and send via email/SMS."""
    otp     = str(secrets.randbelow(900000) + 100000)
    expires = datetime.utcnow() + timedelta(minutes=10)
    _otp_store[identifier] = {'otp': otp, 'expires': expires,
                               'user_id': user_id}
    msg  = (f'Your MediCore HMS verification code is: {otp}. '
            f'Valid for 10 minutes. Do not share this OTP.')
    user = User.query.get(user_id)

    if channel == 'email' and user and user.email:
        try:
            from app.services.notification_service import send_email
            send_email(user.email, 'MediCore HMS — Verification Code', msg)
        except Exception:
            pass
    if channel == 'sms' and user and user.phone:
        try:
            from app.services.notification_service import send_sms
            send_sms(user.phone, msg)
        except Exception:
            pass

    # Always save as in-app notification so patient can see it
    try:
        db.session.add(Notification(
            user_id=user_id, title='Verification Code',
            message=f'Your OTP is: {otp} (valid 10 min)',
            notif_type='info', module='auth'))
        db.session.commit()
    except Exception:
        db.session.rollback()


# ─────────────────────────────────────────────────────────────
#  PAGE ROUTES
# ─────────────────────────────────────────────────────────────


def _vital_to_safe_dict(v):
    """Normalize vital field names: model uses systolic_bp/pulse_rate/weight_kg,
    frontend expects bp_systolic/pulse/weight."""
    if not v: return None
    return {
        'bp_systolic':  v.systolic_bp,
        'bp_diastolic': v.diastolic_bp,
        'pulse':        v.pulse_rate,
        'temperature':  float(v.temperature) if v.temperature else None,
        'spo2':         v.spo2,
        'weight':       float(v.weight_kg) if v.weight_kg else None,
        'height':       float(v.height_cm) if v.height_cm else None,
        'bmi':          float(v.bmi) if v.bmi else None,
        'blood_sugar':  float(v.blood_sugar) if v.blood_sugar else None,
        'recorded_at':  v.recorded_at.isoformat() if v.recorded_at else None,
    }

@patient_bp.route('/login')
def mobile_login():
    # If already logged in as patient, go to app
    if current_user.is_authenticated and current_user.is_patient_role():
        return redirect(url_for('patient.app_view'))
    # Staff logged in as admin/doctor/etc. can still view the patient login page
    # — they will log in with a patient account; Flask-Login supports one session
    # per browser, so patient login will switch the active session to patient.
    # For the demo, show a notice if a staff session is active.
    staff_logged_in = current_user.is_authenticated and not current_user.is_patient_role()
    return render_template('patient/login.html', staff_logged_in=staff_logged_in)


@patient_bp.route('/app')
@patient_required
def app_view():
    return render_template('patient/app.html')


@patient_bp.route('/dashboard')
@patient_required
def dashboard():
    return render_template('patient/app.html')


# ─────────────────────────────────────────────────────────────
#  AUTH — REGISTRATION
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json() or {}

    required_fields = ['first_name', 'last_name', 'phone',
                        'email', 'password', 'gender']
    for field in required_fields:
        if not str(data.get(field, '')).strip():
            return jsonify({
                'success': False,
                'message': f'{field.replace("_", " ").title()} is required'
            }), 400

    email    = data['email'].strip().lower()
    phone    = data['phone'].strip()
    password = data['password']

    if len(password) < 6:
        return jsonify({'success': False,
                        'message': 'Password must be at least 6 characters'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False,
                        'message': 'Email already registered. Please log in.'}), 409
    if Patient.query.filter_by(phone=phone).first():
        return jsonify({'success': False,
                        'message': 'Phone number already registered.'}), 409

    role = Role.query.filter_by(name='patient').first()
    if not role:
        return jsonify({'success': False,
                        'message': 'Patient role not configured. Contact admin.'}), 500

    # Unique username from email prefix
    base = email.split('@')[0].lower()
    base = ''.join(c for c in base if c.isalnum() or c == '_')
    username, counter = base, 1
    while User.query.filter_by(username=username).first():
        username = f'{base}{counter}'
        counter += 1

    user = User(username=username, email=email, phone=phone,
                role_id=role.id,
                first_name=data['first_name'].strip(),
                last_name=data['last_name'].strip(),
                gender=data.get('gender'),
                is_active=True, is_verified=False)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    # Unique UHID
    prefix = HospitalSetting.get('uhid_prefix', 'MED')
    year   = datetime.utcnow().year
    seq    = Patient.query.count() + 1
    uhid   = f'{prefix}-{year}{seq:04d}'
    while Patient.query.filter_by(uhid=uhid).first():
        seq += 1
        uhid = f'{prefix}-{year}{seq:04d}'

    dob = None
    if data.get('date_of_birth'):
        try:
            dob = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
        except ValueError:
            pass

    patient = Patient(
        user_id=user.id, uhid=uhid,
        first_name=data['first_name'].strip(),
        last_name=data['last_name'].strip(),
        date_of_birth=dob,
        gender=data.get('gender'),
        blood_group=data.get('blood_group', 'unknown'),
        phone=phone, email=email,
        address=data.get('address', ''),
        city=data.get('city', ''),
        state=data.get('state', ''),
    )
    db.session.add(patient)
    db.session.commit()

    _send_otp(email, user.id, channel='email')
    return jsonify({
        'success': True,
        'message': (f'Registration successful! Your UHID is {uhid}. '
                    f'A verification code has been sent to your email.'),
        'uhid': uhid,
    })


# ─────────────────────────────────────────────────────────────
#  AUTH — LOGIN
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/login', methods=['POST'])
def api_login():
    data       = request.get_json() or {}
    identifier = (data.get('identifier') or
                  data.get('email') or
                  data.get('phone') or '').strip()
    password   = data.get('password', '')

    if not identifier or not password:
        return jsonify({'success': False,
                        'message': 'Email/phone and password are required'}), 400

    user = (User.query.filter_by(email=identifier.lower()).first() or
            User.query.filter_by(phone=identifier).first())

    if not user or not user.is_patient_role():
        return jsonify({'success': False,
                        'message': 'No patient account found with this email/phone.'}), 401
    if not user.is_active:
        return jsonify({'success': False,
                        'message': 'Your account has been deactivated. Contact the hospital.'}), 401
    if user.is_locked():
        mins = max(1, int((user.locked_until - datetime.utcnow()).total_seconds() / 60))
        return jsonify({'success': False,
                        'message': f'Account locked. Try again in {mins} minutes.'}), 401
    if not user.check_password(password):
        user.login_attempts = (user.login_attempts or 0) + 1
        if user.login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        db.session.commit()
        remaining = max(0, 5 - (user.login_attempts or 0))
        return jsonify({'success': False,
                        'message': f'Incorrect password. {remaining} attempts remaining.'}), 401

    user.login_attempts = 0
    user.locked_until   = None
    user.last_login     = datetime.utcnow()
    db.session.commit()
    login_user(user, remember=True, duration=timedelta(days=30))

    p = Patient.query.filter_by(user_id=user.id).first()
    return jsonify({
        'success':  True,
        'message':  f'Welcome back, {user.first_name}!',
        'redirect': '/patient/app',
        'patient':  p.to_dict() if p else None,
    })


# ─────────────────────────────────────────────────────────────
#  AUTH — OTP
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/send-otp', methods=['POST'])
def api_send_otp():
    data       = request.get_json() or {}
    identifier = (data.get('identifier') or '').strip()
    channel    = data.get('channel', 'email')
    if not identifier:
        return jsonify({'success': False,
                        'message': 'Email or phone is required'}), 400
    user = (User.query.filter_by(email=identifier.lower()).first() or
            User.query.filter_by(phone=identifier).first())
    if user:
        _send_otp(identifier, user.id, channel=channel)
    return jsonify({'success': True,
                    'message': f'If an account exists, an OTP has been sent.'})


@patient_bp.route('/api/verify-otp', methods=['POST'])
def api_verify_otp():
    data       = request.get_json() or {}
    identifier = (data.get('identifier') or '').strip()
    otp        = (data.get('otp') or '').strip()
    purpose    = data.get('purpose', 'verify')   # 'verify' | 'reset'

    stored = _otp_store.get(identifier)
    if not stored:
        return jsonify({'success': False,
                        'message': 'OTP not found. Please request a new one.'}), 400
    if datetime.utcnow() > stored['expires']:
        _otp_store.pop(identifier, None)
        return jsonify({'success': False,
                        'message': 'OTP has expired. Please request a new one.'}), 400
    if stored['otp'] != otp:
        return jsonify({'success': False,
                        'message': 'Invalid OTP. Please try again.'}), 400

    user = User.query.get(stored['user_id'])
    if not user:
        return jsonify({'success': False, 'message': 'User not found.'}), 404
    _otp_store.pop(identifier, None)

    if purpose == 'verify':
        user.is_verified = True
        db.session.commit()
        login_user(user, remember=True, duration=timedelta(days=30))
        return jsonify({'success': True,
                        'message': 'Account verified! Welcome to MediCore.',
                        'redirect': '/patient/app'})
    if purpose == 'reset':
        session['reset_user_id'] = user.id
        return jsonify({'success': True,
                        'message': 'OTP verified. Please set your new password.',
                        'can_reset': True})
    return jsonify({'success': True})


@patient_bp.route('/api/reset-password', methods=['POST'])
def api_reset_password():
    data    = request.get_json() or {}
    uid     = session.get('reset_user_id')
    new_pwd = data.get('password', '')
    confirm = data.get('confirm_password', '')

    if not uid:
        return jsonify({'success': False,
                        'message': 'Session expired. Please request OTP again.'}), 400
    if len(new_pwd) < 6:
        return jsonify({'success': False,
                        'message': 'Password must be at least 6 characters.'}), 400
    if new_pwd != confirm:
        return jsonify({'success': False,
                        'message': 'Passwords do not match.'}), 400

    user = User.query.get(uid)
    if not user:
        return jsonify({'success': False, 'message': 'User not found.'}), 404
    user.set_password(new_pwd)
    user.login_attempts = 0
    user.locked_until   = None
    session.pop('reset_user_id', None)
    db.session.commit()
    return jsonify({'success': True,
                    'message': 'Password reset successfully! Please log in.'})


@patient_bp.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return jsonify({'success': True, 'redirect': '/patient/login'})


# ─────────────────────────────────────────────────────────────
#  PROFILE
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/profile')
@patient_required
def api_profile():
    p = _patient()
    if not p:
        return jsonify({'success': True, 'patient': None,
                        'message': 'Profile not linked. Contact reception.'})
    allergies  = PatientAllergy.query.filter_by(patient_id=p.id).all()
    conditions = PatientChronicCondition.query.filter_by(patient_id=p.id).all()
    last_vital = Vital.query.filter_by(patient_id=p.id).order_by(
                     Vital.recorded_at.desc()).first()
    return jsonify({'success': True, 'patient': {
        'id':                 p.id,
        'uhid':               p.uhid,
        'full_name':          p.full_name,
        'first_name':         p.first_name,
        'age':                p.age,
        'gender':             p.gender,
        'blood_group':        p.blood_group,
        'phone':              p.phone,
        'email':              p.email,
        'date_of_birth':      p.date_of_birth.isoformat() if p.date_of_birth else None,
        'address':            p.address or '',
        'city':               p.city or '',
        'state':              p.state or '',
        'insurance_provider': p.insurance_provider or '',
        'insurance_id':       p.insurance_id or '',
        'is_verified':        current_user.is_verified,
        'allergies': [
            {'allergen': a.allergen, 'severity': a.severity}
            for a in allergies
        ],
        'conditions': [
            {'condition': c.condition, 'icd10_code': c.icd10_code}
            for c in conditions
        ],
        'last_vitals': _vital_to_safe_dict(last_vital) if last_vital else None,
    }})


@patient_bp.route('/api/profile/update', methods=['POST'])
@patient_required
def api_profile_update():
    p    = _patient()
    data = request.get_json() or {}
    if not p:
        return jsonify({'success': False, 'message': 'Profile not found.'}), 404
    updatable = ['address', 'city', 'state', 'pincode',
                 'emergency_phone', 'occupation', 'blood_group']
    for field in updatable:
        if field in data:
            setattr(p, field, data[field])
    if data.get('date_of_birth'):
        try:
            p.date_of_birth = datetime.strptime(
                data['date_of_birth'], '%Y-%m-%d').date()
        except ValueError:
            pass
    db.session.commit()
    return jsonify({'success': True, 'message': 'Profile updated!'})


# ─────────────────────────────────────────────────────────────
#  HOME SUMMARY
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/summary')
@patient_required
def api_summary():
    p = _patient()
    if not p:
        return jsonify({'success': True, 'summary': {}})

    today     = date.today()
    next_appt = Appointment.query.filter(
        Appointment.patient_id == p.id,
        Appointment.appointment_date >= today,
        Appointment.status.notin_(['cancelled']),
    ).order_by(Appointment.appointment_date,
               Appointment.appointment_time).first()

    last_vital    = Vital.query.filter_by(patient_id=p.id).order_by(
                        Vital.recorded_at.desc()).first()
    pending_bills = Invoice.query.filter(
                        Invoice.patient_id == p.id,
                        Invoice.balance > 0).count()
    lab_count     = LabOrder.query.filter_by(
                        patient_id=p.id, status='completed').count()
    unread        = Notification.query.filter_by(
                        user_id=current_user.id, is_read=False).count()
    allergy_count = PatientAllergy.query.filter_by(patient_id=p.id).count()

    na = None
    if next_appt:
        doc = Doctor.query.get(next_appt.doctor_id)
        na  = {
            'id':     next_appt.id,
            'date':   next_appt.appointment_date.strftime('%d %b %Y'),
            'time':   next_appt.appointment_time.strftime('%H:%M') if next_appt.appointment_time else '',
            'doctor': doc.full_name if doc else '?',
            'spec':   doc.specialization if doc else '',
            'token':  next_appt.token_number,
        }

    return jsonify({'success': True, 'summary': {
        'patient_name':  p.first_name,
        'full_name':     p.full_name,
        'uhid':          p.uhid,
        'blood_group':   p.blood_group,
        'upcoming_appt': na,
        'last_vitals':   _vital_to_safe_dict(last_vital) if last_vital else None,
        'pending_bills': pending_bills,
        'lab_reports':   lab_count,
        'notifications': unread,
        'allergies':     allergy_count,
    }})


# ─────────────────────────────────────────────────────────────
#  DEPARTMENTS & DOCTORS
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/departments')
@patient_required
def api_departments():
    depts = Department.query.filter_by(is_active=True).all()
    return jsonify({'success': True, 'departments': [
        {'id': d.id, 'name': d.name, 'floor': d.floor}
        for d in depts
    ]})


@patient_bp.route('/api/doctors')
@patient_required
def api_doctors():
    dept_id = request.args.get('department_id')
    search  = request.args.get('search', '').strip()

    q = Doctor.query.join(User, Doctor.user_id == User.id).filter(
        Doctor.is_available == True)
    if dept_id:
        q = q.filter(Doctor.department_id == int(dept_id))
    if search:
        q = q.filter(db.or_(
            User.first_name.ilike(f'%{search}%'),
            User.last_name.ilike(f'%{search}%'),
            Doctor.specialization.ilike(f'%{search}%'),
        ))

    result = []
    for doc in q.all():
        dept = Department.query.get(doc.department_id) if doc.department_id else None
        result.append({
            'id':               doc.id,
            'full_name':        doc.full_name,
            'specialization':   doc.specialization or '',
            'qualification':    doc.qualification or '',
            'experience_years': doc.experience_years or 0,
            'department':       dept.name if dept else '',
            'department_id':    doc.department_id,
            'consultation_fee': float(doc.consultation_fee or 0),
            'bio':              doc.bio or '',
            'rating':           float(doc.rating or 0),
        })
    return jsonify({'success': True, 'doctors': result})


@patient_bp.route('/api/doctors/<int:did>/schedule')
@patient_required
def api_doctor_schedule(did):
    schedules = DoctorSchedule.query.filter_by(
        doctor_id=did, is_active=True).all()
    return jsonify({'success': True, 'schedules': [
        {'day':   s.day_of_week,
         'start': s.start_time.strftime('%H:%M'),
         'end':   s.end_time.strftime('%H:%M'),
         'slots': s.slot_duration}
        for s in schedules
    ]})


@patient_bp.route('/api/doctors/<int:did>/slots')
@patient_required
def api_doctor_slots(did):
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'success': False, 'message': 'date is required'}), 400
    try:
        appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400
    if appt_date < date.today():
        return jsonify({'success': True, 'slots': [],
                        'message': 'Cannot book past dates'})

    day_name = appt_date.strftime('%A').lower()
    schedule = DoctorSchedule.query.filter_by(
        doctor_id=did, day_of_week=day_name, is_active=True).first()
    if not schedule:
        return jsonify({
            'success': True, 'slots': [],
            'message': f'Doctor is not available on {appt_date.strftime("%A")}s'
        })

    booked = {
        a.appointment_time.strftime('%H:%M')
        for a in Appointment.query.filter(
            Appointment.doctor_id == did,
            Appointment.appointment_date == appt_date,
            Appointment.status.notin_(['cancelled']),
        ).all()
    }

    slots   = []
    current = datetime.combine(appt_date, schedule.start_time)
    end_dt  = datetime.combine(appt_date, schedule.end_time)
    while current < end_dt:
        t = current.strftime('%H:%M')
        slots.append({'time': t, 'available': t not in booked})
        current += timedelta(minutes=schedule.slot_duration)

    doc = Doctor.query.get(did)
    return jsonify({
        'success': True, 'slots': slots,
        'doctor':  doc.full_name if doc else '',
        'fee':     float(doc.consultation_fee or 0) if doc else 0,
    })


# ─────────────────────────────────────────────────────────────
#  DOCTOR RATINGS
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/doctors/<int:did>/ratings')
@patient_required
def api_doctor_ratings(did):
    doc     = Doctor.query.get_or_404(did)
    ratings = DoctorRating.query.filter_by(doctor_id=did).order_by(
                  DoctorRating.created_at.desc()).limit(10).all()
    return jsonify({
        'success': True,
        'average': float(doc.rating or 0),
        'count':   len(ratings),
        'ratings': [
            {'rating':  r.rating,
             'comment': r.comment or '',
             'date':    r.created_at.strftime('%b %Y')}
            for r in ratings
        ],
    })


@patient_bp.route('/api/doctors/<int:did>/rate', methods=['POST'])
@patient_required
def api_rate_doctor(did):
    p    = _patient()
    data = request.get_json() or {}
    rating  = int(data.get('rating', 0))
    comment = data.get('comment', '').strip()

    if not 1 <= rating <= 5:
        return jsonify({'success': False,
                        'message': 'Rating must be between 1 and 5'}), 400
    visited = Appointment.query.filter_by(
        patient_id=p.id, doctor_id=did, status='completed').first()
    if not visited:
        return jsonify({'success': False,
                        'message': 'You can only rate doctors you have visited.'}), 403

    existing = DoctorRating.query.filter_by(
        doctor_id=did, patient_id=p.id).first()
    if existing:
        existing.rating  = rating
        existing.comment = comment
    else:
        db.session.add(DoctorRating(
            doctor_id=did, patient_id=p.id,
            rating=rating, comment=comment))

    db.session.flush()
    avg = db.session.query(
        db.func.avg(DoctorRating.rating)
    ).filter_by(doctor_id=did).scalar()
    doc = Doctor.query.get(did)
    if doc and avg:
        doc.rating = round(float(avg), 1)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Thank you for your rating!'})


# ─────────────────────────────────────────────────────────────
#  APPOINTMENTS
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/appointments')
@patient_required
def api_appointments():
    p = _patient()
    if not p:
        return jsonify({'success': True, 'upcoming': [], 'past': []})
    today = date.today()

    upcoming = Appointment.query.filter(
        Appointment.patient_id == p.id,
        Appointment.appointment_date >= today,
        Appointment.status.notin_(['cancelled']),
    ).order_by(Appointment.appointment_date,
               Appointment.appointment_time).all()

    past = Appointment.query.filter(
        Appointment.patient_id == p.id,
        Appointment.appointment_date < today,
    ).order_by(Appointment.appointment_date.desc()).limit(20).all()

    def _fmt(a):
        doc  = Doctor.query.get(a.doctor_id)
        dept = Department.query.get(a.department_id) if a.department_id else None
        return {
            'id':             a.id,
            'appointment_no': a.appointment_no,
            'date':           a.appointment_date.strftime('%d %b %Y'),
            'date_iso':       a.appointment_date.isoformat(),
            'time':           a.appointment_time.strftime('%H:%M') if a.appointment_time else '',
            'doctor':         doc.full_name if doc else '?',
            'doctor_id':      doc.id if doc else None,
            'specialization': doc.specialization if doc else '',
            'department':     dept.name if dept else '',
            'token':          a.token_number,
            'type':           a.appt_type,
            'status':         a.status,
            'reason':         a.reason or '',
        }

    return jsonify({'success': True,
                    'upcoming': [_fmt(a) for a in upcoming],
                    'past':     [_fmt(a) for a in past]})


@patient_bp.route('/api/appointments/book', methods=['POST'])
@patient_required
def api_book_appointment():
    p    = _patient()
    data = request.get_json() or {}
    if not p:
        return jsonify({'success': False,
                        'message': 'Patient profile not found. Contact reception.'}), 404

    for field in ['doctor_id', 'appointment_date', 'appointment_time']:
        if not data.get(field):
            return jsonify({'success': False,
                            'message': f'{field.replace("_"," ").title()} is required'}), 400
    try:
        appt_date = datetime.strptime(data['appointment_date'], '%Y-%m-%d').date()
        appt_time = datetime.strptime(data['appointment_time'], '%H:%M').time()
    except ValueError:
        return jsonify({'success': False,
                        'message': 'Invalid date or time format'}), 400
    if appt_date < date.today():
        return jsonify({'success': False,
                        'message': 'Cannot book past dates'}), 400

    # Double-check slot is still free
    clash = Appointment.query.filter(
        Appointment.doctor_id == int(data['doctor_id']),
        Appointment.appointment_date == appt_date,
        Appointment.appointment_time == appt_time,
        Appointment.status.notin_(['cancelled']),
    ).first()
    if clash:
        return jsonify({'success': False,
                        'message': 'This slot was just booked by someone else. '
                                   'Please choose another.'}), 409

    token = (db.session.query(
        db.func.coalesce(db.func.max(Appointment.token_number), 0)
    ).filter(
        Appointment.doctor_id == int(data['doctor_id']),
        Appointment.appointment_date == appt_date,
    ).scalar() or 0) + 1

    doc  = Doctor.query.get(int(data['doctor_id']))
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
    db.session.add(Notification(
        user_id    = current_user.id,
        title      = 'Appointment Confirmed',
        message    = (f'Your appointment with {doc.full_name if doc else "Doctor"} '
                      f'on {appt_date.strftime("%d %b")} at '
                      f'{appt_time.strftime("%H:%M")} — Token #{token}'),
        notif_type = 'success',
        module     = 'appointment',
    ))
    db.session.commit()

    return jsonify({
        'success':        True,
        'message':        f'Appointment booked successfully! Token #{token}',
        'token':          token,
        'appointment_no': appt.appointment_no,
        'date':           appt_date.strftime('%d %b %Y'),
        'time':           appt_time.strftime('%H:%M'),
        'doctor':         doc.full_name if doc else '?',
    })


@patient_bp.route('/api/appointments/<int:aid>/cancel', methods=['POST'])
@patient_required
def api_cancel_appointment(aid):
    p    = _patient()
    appt = Appointment.query.get_or_404(aid)
    if appt.patient_id != p.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    if appt.status in ['completed', 'in_progress']:
        return jsonify({'success': False,
                        'message': 'Cannot cancel a completed or in-progress appointment.'}), 400
    appt.status        = 'cancelled'
    appt.cancel_reason = 'Cancelled by patient via portal'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Appointment cancelled.'})


# ─────────────────────────────────────────────────────────────
#  VISITS
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/visits')
@patient_required
def api_visits():
    p = _patient()
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
            'date_iso':        v.visit_date.isoformat(),
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


# ─────────────────────────────────────────────────────────────
#  PRESCRIPTIONS
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/prescriptions')
@patient_required
def api_prescriptions():
    p = _patient()
    if not p:
        return jsonify({'success': True, 'prescriptions': []})
    rxs = Prescription.query.filter_by(patient_id=p.id).order_by(
              Prescription.created_at.desc()).limit(20).all()
    result = []
    for rx in rxs:
        doc   = Doctor.query.get(rx.doctor_id)
        items = PrescriptionItem.query.filter_by(prescription_id=rx.id).all()
        drugs = []
        for i in items:
            drug = Drug.query.get(i.drug_id)
            drugs.append({
                'name':         drug.name if drug else '?',
                'generic':      drug.generic_name if drug else '',
                'drug_type':    drug.drug_type if drug else '',
                'dosage':       i.dosage or '',
                'frequency':    i.frequency or '',
                'duration':     i.duration or '',
                'quantity':     i.quantity,
                'instructions': i.instructions or '',
                'is_dispensed': i.is_dispensed,
            })
        result.append({
            'id':              rx.id,
            'prescription_no': rx.prescription_no,
            'date':            rx.created_at.strftime('%d %b %Y'),
            'doctor':          doc.full_name if doc else '?',
            'status':          rx.status,
            'notes':           rx.notes or '',
            'drugs':           drugs,
        })
    return jsonify({'success': True, 'prescriptions': result})


@patient_bp.route('/api/prescriptions/<int:rx_id>/pdf')
@patient_required
def api_prescription_pdf(rx_id):
    p  = _patient()
    rx = Prescription.query.get_or_404(rx_id)
    if rx.patient_id != p.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    doc   = Doctor.query.get(rx.doctor_id)
    items = PrescriptionItem.query.filter_by(prescription_id=rx_id).all()
    drugs = []
    for i in items:
        drug = Drug.query.get(i.drug_id)
        drugs.append({
            'name':         drug.name if drug else '?',
            'generic':      drug.generic_name if drug else '',
            'dosage':       i.dosage or '',
            'frequency':    i.frequency or '',
            'duration':     i.duration or '',
            'quantity':     i.quantity,
            'instructions': i.instructions or '',
        })
    rx_data = {
        'prescription_no': rx.prescription_no,
        'date':       rx.created_at.strftime('%d %b %Y'),
        'doctor':     doc.full_name if doc else '?',
        'department': doc.specialization if doc else '',
        'notes':      rx.notes or '',
        'drugs':      drugs,
    }
    patient_data = {
        'full_name':   p.full_name, 'uhid': p.uhid,
        'age':         p.age,       'gender': p.gender,
        'blood_group': p.blood_group,
    }
    try:
        from app.services.pdf_service import generate_prescription_pdf
        pdf_bytes = generate_prescription_pdf(rx_data, patient_data, _hospital())
        return Response(pdf_bytes, mimetype='application/pdf', headers={
            'Content-Disposition': f'attachment; filename=Rx_{rx.prescription_no}.pdf'
        })
    except Exception as e:
        return jsonify({'success': False,
                        'message': f'PDF error: {e}. Install: pip install reportlab'}), 500


# ─────────────────────────────────────────────────────────────
#  LAB REPORTS
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/lab-reports')
@patient_required
def api_lab_reports():
    p = _patient()
    if not p:
        return jsonify({'success': True, 'reports': []})
    orders = LabOrder.query.filter_by(
                 patient_id=p.id, status='completed').order_by(
                 LabOrder.completed_at.desc()).limit(20).all()
    result = []
    for o in orders:
        doc   = Doctor.query.get(o.doctor_id)
        items = LabOrderItem.query.filter_by(order_id=o.id).all()
        tests = []
        for i in items:
            test = LabTest.query.get(i.test_id)
            tests.append({
                'name':     test.name if test else '?',
                'result':   i.result_value or '—',
                'unit':     i.result_unit or '',
                'normal':   i.normal_range or '',
                'flag':     i.flag or 'normal',
                'critical': i.is_critical,
            })
        result.append({
            'id':           o.id,
            'order_no':     o.order_no,
            'date':         o.completed_at.strftime('%d %b %Y') if o.completed_at else '—',
            'date_iso':     o.completed_at.date().isoformat() if o.completed_at else '',
            'doctor':       doc.full_name if doc else '?',
            'has_critical': any(i.is_critical for i in items),
            'test_count':   len(items),
            'tests':        tests,
        })
    return jsonify({'success': True, 'reports': result})


@patient_bp.route('/api/lab-reports/<int:order_id>/pdf')
@patient_required
def api_lab_report_pdf(order_id):
    p     = _patient()
    order = LabOrder.query.get_or_404(order_id)
    if order.patient_id != p.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    doc   = Doctor.query.get(order.doctor_id)
    items = LabOrderItem.query.filter_by(order_id=order_id).all()
    tests = []
    for i in items:
        test = LabTest.query.get(i.test_id)
        tests.append({
            'name':     test.name if test else '?',
            'result':   i.result_value or '—',
            'unit':     i.result_unit or '',
            'normal':   i.normal_range or '',
            'flag':     i.flag or 'normal',
            'critical': i.is_critical,
        })
    report_data = {
        'order_no':     order.order_no,
        'ordered_at':   order.ordered_at.strftime('%d %b %Y %H:%M'),
        'completed_at': order.completed_at.strftime('%d %b %Y %H:%M') if order.completed_at else '—',
        'doctor':       doc.full_name if doc else '?',
        'tests':        tests,
    }
    patient_data = {
        'full_name':   p.full_name, 'uhid': p.uhid,
        'age':         p.age,       'gender': p.gender,
        'blood_group': p.blood_group,
    }
    try:
        from app.services.pdf_service import generate_lab_report_pdf
        pdf_bytes = generate_lab_report_pdf(report_data, patient_data, _hospital())
        return Response(pdf_bytes, mimetype='application/pdf', headers={
            'Content-Disposition': f'attachment; filename=Lab_{order.order_no}.pdf'
        })
    except Exception as e:
        return jsonify({'success': False,
                        'message': f'PDF error: {e}. Install: pip install reportlab'}), 500


# ─────────────────────────────────────────────────────────────
#  VITALS HISTORY
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/vitals/history')
@patient_required
def api_vitals_history():
    p = _patient()
    if not p:
        return jsonify({'success': True, 'vitals': []})
    vitals = Vital.query.filter_by(patient_id=p.id).order_by(
                 Vital.recorded_at.asc()).limit(20).all()
    return jsonify({'success': True, 'vitals': [
        {
            'date':         v.recorded_at.strftime('%d %b'),
            'date_iso':     v.recorded_at.date().isoformat(),
            'systolic_bp':  v.systolic_bp,
            'diastolic_bp': v.diastolic_bp,
            'pulse_rate':   v.pulse_rate,
            'temperature':  float(v.temperature) if v.temperature else None,
            'spo2':         v.spo2,
            'weight_kg':    float(v.weight_kg) if v.weight_kg else None,
            'bmi':          float(v.bmi) if v.bmi else None,
            'blood_sugar':  float(v.blood_sugar) if v.blood_sugar else None,
        }
        for v in vitals
    ]})


# ─────────────────────────────────────────────────────────────
#  BILLS & RAZORPAY
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/bills')
@patient_required
def api_bills():
    p = _patient()
    if not p:
        return jsonify({'success': True, 'bills': []})
    invoices = Invoice.query.filter_by(patient_id=p.id).order_by(
                   Invoice.created_at.desc()).limit(20).all()
    result = []
    for inv in invoices:
        items = InvoiceItem.query.filter_by(invoice_id=inv.id).all()
        result.append({
            'id':         inv.id,
            'invoice_no': inv.invoice_no,
            'date':       inv.invoice_date.strftime('%d %b %Y') if inv.invoice_date else '—',
            'subtotal':   float(inv.subtotal),
            'discount':   float(inv.discount_amt),
            'gst':        float(inv.gst_amount),
            'total':      float(inv.total_amount),
            'paid':       float(inv.paid_amount),
            'balance':    float(inv.balance),
            'status':     inv.status,
            'items': [
                {'description': i.description, 'type': i.item_type,
                 'qty': i.quantity, 'price': float(i.unit_price),
                 'total': float(i.total_price)}
                for i in items
            ],
        })
    return jsonify({'success': True, 'bills': result})


@patient_bp.route('/api/bills/<int:inv_id>/create-order', methods=['POST'])
@patient_required
def api_create_razorpay_order(inv_id):
    p   = _patient()
    inv = Invoice.query.get_or_404(inv_id)
    if inv.patient_id != p.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    if float(inv.balance) <= 0:
        return jsonify({'success': False,
                        'message': 'No outstanding balance on this invoice'}), 400
    try:
        import razorpay
        key_id     = HospitalSetting.get('razorpay_key_id', '')
        key_secret = HospitalSetting.get('razorpay_key_secret', '')
        if not key_id or not key_secret:
            return jsonify({'success': False,
                            'message': 'Payment gateway not configured. '
                                       'Contact the hospital.'}), 503
        client = razorpay.Client(auth=(key_id, key_secret))
        order  = client.order.create({
            'amount':   int(float(inv.balance) * 100),
            'currency': 'INR',
            'receipt':  inv.invoice_no,
            'notes':    {'invoice_id': inv_id, 'uhid': p.uhid},
        })
        return jsonify({
            'success':    True,
            'order_id':   order['id'],
            'amount':     int(float(inv.balance) * 100),
            'currency':   'INR',
            'key_id':     key_id,
            'invoice_no': inv.invoice_no,
            'patient':    p.full_name,
            'email':      p.email or '',
            'phone':      p.phone or '',
        })
    except ImportError:
        return jsonify({'success': False,
                        'message': 'razorpay not installed. Run: pip install razorpay'}), 503
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@patient_bp.route('/api/bills/<int:inv_id>/verify-payment', methods=['POST'])
@patient_required
def api_verify_payment(inv_id):
    p    = _patient()
    inv  = Invoice.query.get_or_404(inv_id)
    data = request.get_json() or {}
    if inv.patient_id != p.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    try:
        import razorpay
        import os as _os2
        _key_id     = (HospitalSetting.get('razorpay_key_id', '') or
                       _os2.environ.get('RAZORPAY_KEY_ID', ''))
        _key_secret = (HospitalSetting.get('razorpay_key_secret', '') or
                       _os2.environ.get('RAZORPAY_KEY_SECRET', ''))
        client = razorpay.Client(auth=(_key_id, _key_secret))
        client.utility.verify_payment_signature({
            'razorpay_order_id':   data.get('order_id'),
            'razorpay_payment_id': data.get('payment_id'),
            'razorpay_signature':  data.get('signature'),
        })
        amt = float(inv.balance)
        db.session.add(Payment(
            payment_no     = f'PAY{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
            invoice_id     = inv_id,
            patient_id     = p.id,
            amount         = amt,
            payment_mode   = 'razorpay',
            transaction_id = data.get('payment_id'),
            status         = 'success',
        ))
        inv.paid_amount  = float(inv.paid_amount) + amt
        inv.balance      = 0
        inv.status       = 'paid'
        inv.payment_mode = 'razorpay'
        db.session.add(Notification(
            user_id    = current_user.id,
            title      = 'Payment Successful',
            message    = f'Payment of ₹{amt:.2f} for {inv.invoice_no} confirmed.',
            notif_type = 'success',
            module     = 'billing',
        ))
        db.session.commit()
        return jsonify({'success': True,
                        'message': 'Payment verified and recorded!'})
    except Exception as e:
        return jsonify({'success': False,
                        'message': f'Payment verification failed: {e}'}), 400


# ─────────────────────────────────────────────────────────────
#  HEALTH TIMELINE
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/timeline')
@patient_required
def api_timeline():
    p = _patient()
    if not p:
        return jsonify({'success': True, 'timeline': []})

    events = []

    for v in Visit.query.filter_by(patient_id=p.id).order_by(
            Visit.visit_date.desc()).limit(10).all():
        doc  = Doctor.query.get(v.doctor_id)
        soap = SOAPNote.query.filter_by(visit_id=v.id).first()
        events.append({
            'type':     'visit',
            'date':     v.visit_date.strftime('%d %b %Y'),
            'date_iso': v.visit_date.isoformat(),
            'title':    f'Consultation — {doc.full_name if doc else "Doctor"}',
            'detail':   soap.assessment if soap else (v.chief_complaint or 'Consultation'),
            'color':    'blue', 'icon': '🏥',
        })

    for rx in Prescription.query.filter_by(patient_id=p.id).order_by(
            Prescription.created_at.desc()).limit(8).all():
        items = PrescriptionItem.query.filter_by(prescription_id=rx.id).all()
        names = ', '.join(
            Drug.query.get(i.drug_id).name
            for i in items if Drug.query.get(i.drug_id)
        )[:60]
        events.append({
            'type':     'prescription',
            'date':     rx.created_at.strftime('%d %b %Y'),
            'date_iso': rx.created_at.date().isoformat(),
            'title':    f'Prescription — {rx.prescription_no}',
            'detail':   names or '—',
            'color':    'teal', 'icon': '💊',
            'rx_id':    rx.id,
        })

    for lab in LabOrder.query.filter_by(
            patient_id=p.id, status='completed').order_by(
            LabOrder.completed_at.desc()).limit(8).all():
        items       = LabOrderItem.query.filter_by(order_id=lab.id).all()
        has_crit    = any(i.is_critical for i in items)
        events.append({
            'type':         'lab',
            'date':         lab.completed_at.strftime('%d %b %Y') if lab.completed_at else '—',
            'date_iso':     lab.completed_at.date().isoformat() if lab.completed_at else '',
            'title':        f'Lab Report — {lab.order_no}',
            'detail':       f'{len(items)} test(s)' + (' ⚠ Critical' if has_crit else ''),
            'color':        'purple', 'icon': '🔬',
            'has_critical': has_crit,
            'order_id':     lab.id,
        })

    events.sort(key=lambda e: e.get('date_iso', ''), reverse=True)
    return jsonify({'success': True, 'timeline': events})


# ─────────────────────────────────────────────────────────────
#  NOTIFICATIONS
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/notifications')
@patient_required
def api_notifications():
    notifs = Notification.query.filter_by(
                 user_id=current_user.id).order_by(
                 Notification.created_at.desc()).limit(30).all()
    unread = Notification.query.filter_by(
                 user_id=current_user.id, is_read=False).count()
    return jsonify({
        'success':       True,
        'notifications': [n.to_dict() for n in notifs],
        'unread':        unread,
    })


@patient_bp.route('/api/notifications/mark-read', methods=['POST'])
@patient_required
def api_mark_read():
    Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({'is_read': True, 'read_at': datetime.utcnow()})
    db.session.commit()
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────
#  HEALTH STATS & VITALS CHART
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/health-stats')
@patient_required
def api_health_stats():
    p = _patient()
    if not p:
        return jsonify({'success': False, 'message': 'Profile not found'}), 404
    # Last 10 vitals for charts
    vitals = Vital.query.filter_by(patient_id=p.id)        .order_by(Vital.recorded_at.desc()).limit(10).all()
    vitals = list(reversed(vitals))
    # Chronic conditions
    from app.models.patient import PatientChronicCondition
    conditions = PatientChronicCondition.query.filter_by(patient_id=p.id).all()
    allergies  = PatientAllergy.query.filter_by(patient_id=p.id).all()
    # Active prescriptions count
    active_rx = Prescription.query.filter_by(
        patient_id=p.id, status='active').count()
    # Completed lab orders this month
    from datetime import datetime as dt_
    start_month = date.today().replace(day=1)
    lab_this_month = LabOrder.query.filter(
        LabOrder.patient_id == p.id,
        LabOrder.status == 'completed',
        db.func.date(LabOrder.created_at) >= start_month,
    ).count()
    return jsonify({'success': True, 'health_stats': {
        'vitals_chart': [v.to_dict() for v in vitals],
        'conditions':   [{'name': c.condition, 'since': c.diagnosed_on.strftime('%Y') if c.diagnosed_on else ''} for c in conditions],
        'allergies':    [{'name': a.allergen, 'severity': a.severity} for a in allergies],
        'active_prescriptions': active_rx,
        'lab_this_month': lab_this_month,
        'bmi': _calc_bmi(vitals[-1] if vitals else None),
    }})

def _calc_bmi(vital):
    if not vital:
        return None
    try:
        w = float(vital.weight or 0)
        h = float(vital.height or 0) / 100  # cm → m
        if w and h:
            bmi = round(w / (h * h), 1)
            if bmi < 18.5:   cat = 'Underweight'
            elif bmi < 25:   cat = 'Normal'
            elif bmi < 30:   cat = 'Overweight'
            else:            cat = 'Obese'
            return {'value': bmi, 'category': cat}
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────
#  MEDICINE REMINDERS (in-app, stored in notifications)
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/reminders')
@patient_required
def api_reminders():
    """Return active prescriptions formatted as medicine reminders."""
    p = _patient()
    if not p:
        return jsonify({'success': True, 'reminders': []})
    rxs = Prescription.query.filter_by(
        patient_id=p.id, status='active').order_by(
        Prescription.created_at.desc()).limit(20).all()
    reminders = []
    for rx in rxs:
        items = PrescriptionItem.query.filter_by(prescription_id=rx.id).all()
        doc   = Doctor.query.get(rx.doctor_id)
        for item in items:
            drug = Drug.query.get(item.drug_id) if item.drug_id else None
            reminders.append({
                'rx_id':      rx.id,
                'drug_name':  drug.name if drug else 'Unknown Drug',
                'dosage':     item.dosage or '',
                'frequency':  item.frequency or '',
                'duration':   item.duration or '',
                'instructions': item.instructions or '',
                'doctor':     doc.user.full_name if doc and doc.user else '',
                'prescribed_date': rx.created_at.strftime('%d %b %Y'),
            })
    return jsonify({'success': True, 'reminders': reminders})


# ─────────────────────────────────────────────────────────────
#  UPCOMING APPOINTMENTS CALENDAR
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/appointments/upcoming')
@patient_required
def api_upcoming_appointments():
    p = _patient()
    if not p:
        return jsonify({'success': True, 'appointments': []})
    today = date.today()
    appts = Appointment.query.filter(
        Appointment.patient_id == p.id,
        Appointment.appointment_date >= today,
        Appointment.status.notin_(['cancelled']),
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).limit(10).all()
    result = []
    for a in appts:
        doc  = Doctor.query.get(a.doctor_id)
        dept = None
        if doc and doc.department_id:
            from app.models.doctor import Department
            dept = Department.query.get(doc.department_id)
        result.append({
            'id':     a.id,
            'date':   a.appointment_date.strftime('%Y-%m-%d'),
            'date_display': a.appointment_date.strftime('%d %b %Y'),
            'time':   a.appointment_time.strftime('%H:%M') if a.appointment_time else '',
            'doctor': doc.user.full_name if doc and doc.user else '',
            'specialization': doc.specialization if doc else '',
            'department': dept.name if dept else '',
            'status': a.status,
            'token':  a.token_number,
            'reason': a.reason or '',
            'is_today': a.appointment_date == today,
            'is_tomorrow': a.appointment_date == today + timedelta(days=1),
        })
    return jsonify({'success': True, 'appointments': result})


# ─────────────────────────────────────────────────────────────
#  RECENT VISITS SUMMARY
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/visits/recent')
@patient_required
def api_recent_visits():
    p = _patient()
    if not p:
        return jsonify({'success': True, 'visits': []})
    visits = Visit.query.filter_by(patient_id=p.id)        .order_by(Visit.visit_date.desc()).limit(5).all()
    result = []
    for v in visits:
        doc  = Doctor.query.get(v.doctor_id) if v.doctor_id else None
        soap = v.soap_notes.order_by(None).first()
        result.append({
            'id':         v.id,
            'date':       v.visit_date.strftime('%d %b %Y') if v.visit_date else '',
            'doctor':     doc.user.full_name if doc and doc.user else '',
            'diagnosis':  (soap.assessment or '') if soap else '',
            'icd10':      (soap.icd10_code or '') if soap else '',
            'chief_complaint': v.chief_complaint or '',
            'follow_up_date': soap.follow_up_date.strftime('%d %b %Y') if soap and soap.follow_up_date else None,
        })
    return jsonify({'success': True, 'visits': result})


# ─────────────────────────────────────────────────────────────
#  DOCTOR SEARCH
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/doctors/search')
@patient_required
def api_doctors_search():
    q    = request.args.get('q', '').strip()
    dept = request.args.get('department_id', '')
    query = Doctor.query.join(User).filter(Doctor.is_available == True)
    if q:
        query = query.filter(db.or_(
            User.first_name.ilike(f'%{q}%'),
            User.last_name.ilike(f'%{q}%'),
            Doctor.specialization.ilike(f'%{q}%'),
        ))
    if dept:
        query = query.filter(Doctor.department_id == int(dept))
    doctors = query.limit(20).all()
    result = []
    for d in doctors:
        from app.models.doctor import Department as Dept_
        dept_obj = Dept_.query.get(d.department_id) if d.department_id else None
        result.append({
            'id':             d.id,
            'name':           d.user.full_name if d.user else '',
            'specialization': d.specialization or '',
            'department':     dept_obj.name if dept_obj else '',
            'qualification':  d.qualification or '',
            'experience':     d.experience_years or 0,
            'fee':            float(d.consultation_fee or 0),
            'rating':         float(d.rating or 0),
            'available':      d.is_available,
        })
    return jsonify({'success': True, 'doctors': result})


# ─────────────────────────────────────────────────────────────
#  ADMITTED PATIENT STATUS
# ─────────────────────────────────────────────────────────────

@patient_bp.route('/api/admission-status')
@patient_required
def api_admission_status():
    p = _patient()
    if not p:
        return jsonify({'success': True, 'admission': None})
    from app.models.clinical import Admission, Ward, Bed
    admission = Admission.query.filter_by(
        patient_id=p.id, status='admitted').first()
    if not admission:
        return jsonify({'success': True, 'admission': None})
    doc = Doctor.query.get(admission.doctor_id)
    return jsonify({'success': True, 'admission': {
        'admission_no':   admission.admission_no,
        'ward':           admission.ward.name if admission.ward else '',
        'ward_type':      admission.ward.ward_type if admission.ward else '',
        'bed':            admission.bed.bed_number if admission.bed else '',
        'doctor':         doc.user.full_name if doc and doc.user else '',
        'admitted_on':    admission.admission_date.strftime('%d %b %Y'),
        'reason':         admission.admission_reason or '',
        'expected_discharge': admission.expected_discharge.strftime('%d %b %Y') if admission.expected_discharge else None,
    }})
