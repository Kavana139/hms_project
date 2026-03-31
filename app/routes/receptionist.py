"""
MediCore HMS — Receptionist Routes
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, date, timedelta
from app import db
from app.models.user import User, HospitalSetting
from app.models.patient import Patient
from app.models.doctor import Doctor, Department, DoctorSchedule
from app.models.appointment import Appointment
from app.models.clinical import Ward, Bed, Admission, Invoice, InvoiceItem, Notification

receptionist_bp = Blueprint('receptionist', __name__)

def receptionist_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not (current_user.is_receptionist() or current_user.is_admin()):
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        return f(*args, **kwargs)
    return decorated


@receptionist_bp.route('/dashboard')
@receptionist_required
def dashboard():
    return render_template('receptionist/dashboard.html')


# ── Stats ─────────────────────────────────────────────────────

@receptionist_bp.route('/api/stats')
@receptionist_required
def api_stats():
    today = date.today()
    return jsonify({'success': True, 'stats': {
        'appointments_today': Appointment.query.filter(
            db.func.date(Appointment.appointment_date) == today).count(),
        'checked_in': Appointment.query.filter(
            db.func.date(Appointment.appointment_date) == today,
            Appointment.status.in_(['checked_in','in_progress'])).count(),
        'completed': Appointment.query.filter(
            db.func.date(Appointment.appointment_date) == today,
            Appointment.status == 'completed').count(),
        'beds_available': Bed.query.filter_by(status='available', is_active=True).count(),
        'total_patients': Patient.query.filter_by(is_active=True).count(),
        'no_shows': Appointment.query.filter(
            db.func.date(Appointment.appointment_date) == today,
            Appointment.status == 'no_show').count(),
    }})


# ── Patient Registration ──────────────────────────────────────

@receptionist_bp.route('/api/patients/search')
@receptionist_required
def search_patients():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'success': True, 'patients': []})
    patients = Patient.query.filter(
        db.or_(
            Patient.first_name.ilike(f'%{q}%'),
            Patient.last_name.ilike(f'%{q}%'),
            Patient.uhid.ilike(f'%{q}%'),
            Patient.phone.ilike(f'%{q}%'),
        )
    ).filter_by(is_active=True).limit(10).all()
    return jsonify({'success': True, 'patients': [p.to_dict() for p in patients]})


@receptionist_bp.route('/api/patients/register', methods=['POST'])
@receptionist_required
def register_patient():
    data = request.get_json() or {}
    for field in ['first_name', 'last_name', 'phone', 'gender']:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'{field} is required'}), 400
    # Generate UHID
    prefix = HospitalSetting.get('uhid_prefix', 'MED')
    year   = datetime.utcnow().year
    count  = Patient.query.count() + 1
    uhid   = f'{prefix}-{year}{count:04d}'
    # Parse DOB
    dob = None
    if data.get('date_of_birth'):
        try: dob = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
        except: pass
    patient = Patient(
        uhid              = uhid,
        first_name        = data['first_name'].strip(),
        last_name         = data['last_name'].strip(),
        date_of_birth     = dob,
        gender            = data['gender'],
        blood_group       = data.get('blood_group', 'unknown'),
        phone             = data['phone'].strip(),
        emergency_phone   = data.get('emergency_phone', ''),
        email             = data.get('email', ''),
        address           = data.get('address', ''),
        city              = data.get('city', ''),
        state             = data.get('state', ''),
        pincode           = data.get('pincode', ''),
        marital_status    = data.get('marital_status'),
        occupation        = data.get('occupation', ''),
        insurance_provider= data.get('insurance_provider', ''),
        insurance_id      = data.get('insurance_id', ''),
        tpa_name          = data.get('tpa_name', ''),
    )
    db.session.add(patient)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Patient registered with UHID: {uhid}',
                    'patient': patient.to_dict()})


@receptionist_bp.route('/api/patients/<int:pid>')
@receptionist_required
def get_patient(pid):
    p = Patient.query.get_or_404(pid)
    appts = Appointment.query.filter_by(patient_id=pid).order_by(
        Appointment.appointment_date.desc()).limit(5).all()
    return jsonify({'success': True, 'patient': {
        **p.to_dict(),
        'date_of_birth': p.date_of_birth.isoformat() if p.date_of_birth else None,
        'address': p.address, 'city': p.city, 'state': p.state,
        'phone': p.phone, 'emergency_phone': p.emergency_phone,
        'email': p.email, 'insurance_provider': p.insurance_provider,
        'recent_appointments': [{
            'date': a.appointment_date.strftime('%d %b %Y'),
            'doctor': Doctor.query.get(a.doctor_id).full_name if Doctor.query.get(a.doctor_id) else '?',
            'status': a.status,
        } for a in appts],
    }})


# ── Appointments ──────────────────────────────────────────────

@receptionist_bp.route('/api/appointments/today')
@receptionist_required
def today_appointments():
    today = date.today()
    appts = Appointment.query.filter(
        db.func.date(Appointment.appointment_date) == today
    ).order_by(Appointment.token_number).all()
    result = []
    for a in appts:
        p = Patient.query.get(a.patient_id)
        d = Doctor.query.get(a.doctor_id)
        result.append({
            'id': a.id, 'token': a.token_number,
            'patient_name': p.full_name if p else '?',
            'patient_uhid': p.uhid if p else '?',
            'doctor_name':  d.full_name if d else '?',
            'time': a.appointment_time.strftime('%H:%M') if a.appointment_time else '',
            'type': a.appt_type, 'status': a.status,
            'reason': a.reason or '',
        })
    return jsonify({'success': True, 'appointments': result})


@receptionist_bp.route('/api/appointments/book', methods=['POST'])
@receptionist_required
def book_appointment():
    data = request.get_json() or {}
    required = ['patient_id', 'doctor_id', 'appointment_date', 'appointment_time']
    for f in required:
        if not data.get(f):
            return jsonify({'success': False, 'message': f'{f} is required'}), 400
    try:
        appt_date = datetime.strptime(data['appointment_date'], '%Y-%m-%d').date()
        appt_time = datetime.strptime(data['appointment_time'], '%H:%M').time()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date/time format'}), 400
    # Check for duplicate
    existing = Appointment.query.filter_by(
        doctor_id=data['doctor_id'],
        appointment_date=appt_date,
        appointment_time=appt_time,
    ).filter(Appointment.status.notin_(['cancelled'])).first()
    if existing:
        return jsonify({'success': False, 'message': 'This slot is already booked'}), 409
    # Get next token number
    token = (db.session.query(db.func.coalesce(db.func.max(Appointment.token_number), 0))
             .filter(Appointment.doctor_id == data['doctor_id'],
                     Appointment.appointment_date == appt_date).scalar() or 0) + 1
    appt_no = f'APT{datetime.utcnow().strftime("%Y%m%d%H%M%S")}'
    appt = Appointment(
        appointment_no   = appt_no,
        patient_id       = data['patient_id'],
        doctor_id        = data['doctor_id'],
        department_id    = data.get('department_id'),
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
    return jsonify({'success': True,
                    'message': f'Appointment booked! Token: {token}',
                    'appointment_no': appt_no, 'token': token})


@receptionist_bp.route('/api/appointments/<int:aid>/checkin', methods=['POST'])
@receptionist_required
def checkin(aid):
    appt = Appointment.query.get_or_404(aid)
    appt.status = 'checked_in'
    db.session.commit()
    # Notify doctor
    doc = Doctor.query.get(appt.doctor_id)
    if doc:
        p = Patient.query.get(appt.patient_id)
        db.session.add(Notification(
            user_id=doc.user_id, title='Patient Checked In',
            message=f'Token {appt.token_number}: {p.full_name if p else "Patient"} is ready',
            notif_type='info', module='appointment', reference_id=aid))
        db.session.commit()
    return jsonify({'success': True, 'message': 'Patient checked in!'})


@receptionist_bp.route('/api/appointments/<int:aid>/cancel', methods=['POST'])
@receptionist_required
def cancel_appointment(aid):
    data  = request.get_json() or {}
    appt  = Appointment.query.get_or_404(aid)
    appt.status        = 'cancelled'
    appt.cancel_reason = data.get('reason', '')
    db.session.commit()
    return jsonify({'success': True, 'message': 'Appointment cancelled'})


# ── Doctor Availability ───────────────────────────────────────

@receptionist_bp.route('/api/doctors/available')
@receptionist_required
def available_doctors():
    dept_id = request.args.get('department_id')
    q = Doctor.query.join(User).filter(Doctor.is_available == True)
    if dept_id:
        q = q.filter(Doctor.department_id == int(dept_id))
    doctors = q.all()
    return jsonify({'success': True, 'doctors': [d.to_dict() for d in doctors]})


@receptionist_bp.route('/api/doctors/<int:did>/slots')
@receptionist_required
def doctor_slots(did):
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'success': False, 'message': 'date required'}), 400
    try:
        appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date'}), 400
    day_name  = appt_date.strftime('%A').lower()
    schedule  = DoctorSchedule.query.filter_by(
        doctor_id=did, day_of_week=day_name, is_active=True).first()
    if not schedule:
        return jsonify({'success': True, 'slots': [], 'message': 'Doctor not available on this day'})
    # Generate slots
    from datetime import datetime as dt, time as dtime
    slots    = []
    current  = dt.combine(appt_date, schedule.start_time)
    end_dt   = dt.combine(appt_date, schedule.end_time)
    booked   = {a.appointment_time.strftime('%H:%M')
                for a in Appointment.query.filter_by(
                    doctor_id=did, appointment_date=appt_date
                ).filter(Appointment.status.notin_(['cancelled'])).all()}
    while current < end_dt:
        slot_str = current.strftime('%H:%M')
        slots.append({'time': slot_str, 'available': slot_str not in booked})
        current += timedelta(minutes=schedule.slot_duration)
    return jsonify({'success': True, 'slots': slots,
                    'doctor': Doctor.query.get(did).full_name})


@receptionist_bp.route('/api/doctors/<int:did>/schedule')
@receptionist_required
def doctor_schedule_view(did):
    """Return doctor's weekly schedule — used to show available days"""
    schedules = DoctorSchedule.query.filter_by(
        doctor_id=did, is_active=True).all()
    return jsonify({'success': True, 'schedules': [{
        'day_of_week': s.day_of_week,
        'start_time':  s.start_time.strftime('%H:%M'),
        'end_time':    s.end_time.strftime('%H:%M'),
        'slot_duration': s.slot_duration,
        'max_patients':  s.max_patients,
    } for s in schedules]})


# ── Departments ───────────────────────────────────────────────

@receptionist_bp.route('/api/departments')
@receptionist_required
def api_departments():
    depts = Department.query.filter_by(is_active=True).all()
    return jsonify({'success': True,
                    'departments': [{'id': d.id, 'name': d.name} for d in depts]})


# ── Bed Management ────────────────────────────────────────────

@receptionist_bp.route('/api/beds')
@receptionist_required
def api_beds():
    ward_id = request.args.get('ward_id')
    q = Bed.query.join(Ward)
    if ward_id:
        q = q.filter(Bed.ward_id == int(ward_id))
    beds = q.filter(Bed.is_active == True).all()
    return jsonify({'success': True, 'beds': [b.to_dict() for b in beds]})


@receptionist_bp.route('/api/wards')
@receptionist_required
def api_wards():
    wards = Ward.query.filter_by(is_active=True).all()
    result = []
    for w in wards:
        total     = Bed.query.filter_by(ward_id=w.id, is_active=True).count()
        available = Bed.query.filter_by(ward_id=w.id, status='available').count()
        occupied  = Bed.query.filter_by(ward_id=w.id, status='occupied').count()
        result.append({
            'id': w.id, 'name': w.name, 'ward_type': w.ward_type,
            'floor': w.floor, 'total': total,
            'available': available, 'occupied': occupied,
            'charge_per_day': float(w.charge_per_day),
        })
    return jsonify({'success': True, 'wards': result})


@receptionist_bp.route('/api/admit', methods=['POST'])
@receptionist_required
def admit_patient():
    data = request.get_json() or {}
    required = ['patient_id', 'doctor_id', 'bed_id', 'ward_id']
    for f in required:
        if not data.get(f):
            return jsonify({'success': False, 'message': f'{f} is required'}), 400
    bed = Bed.query.get_or_404(data['bed_id'])
    if bed.status != 'available':
        return jsonify({'success': False, 'message': 'Bed is not available'}), 409
    admission = Admission(
        admission_no     = f'ADM{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
        patient_id       = data['patient_id'],
        doctor_id        = data['doctor_id'],
        bed_id           = data['bed_id'],
        ward_id          = data['ward_id'],
        admission_reason = data.get('reason', ''),
        admitted_by      = current_user.id,
    )
    bed.status = 'occupied'
    db.session.add(admission)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Patient admitted successfully!',
                    'admission_no': admission.admission_no})


# ── Billing ───────────────────────────────────────────────────

@receptionist_bp.route('/api/billing/create', methods=['POST'])
@receptionist_required
def create_bill():
    data = request.get_json() or {}
    if not data.get('patient_id'):
        return jsonify({'success': False, 'message': 'patient_id required'}), 400
    gst_rate = float(HospitalSetting.get('gst_rate', '18') or 18)
    subtotal = sum(float(i.get('amount', 0)) for i in data.get('items', []))
    gst_amt  = round(subtotal * gst_rate / 100, 2)
    total    = round(subtotal + gst_amt, 2)
    inv_no   = f'INV{datetime.utcnow().strftime("%Y%m%d%H%M%S")}'
    invoice  = Invoice(
        invoice_no   = inv_no,
        patient_id   = data['patient_id'],
        visit_id     = data.get('visit_id'),
        subtotal     = subtotal,
        gst_pct      = gst_rate,
        gst_amount   = gst_amt,
        total_amount = total,
        balance      = total,
        status       = 'pending',
        created_by   = current_user.id,
    )
    db.session.add(invoice)
    db.session.flush()
    for item in data.get('items', []):
        db.session.add(InvoiceItem(
            invoice_id  = invoice.id,
            item_type   = item.get('type', 'consultation'),
            description = item.get('description', ''),
            quantity    = item.get('quantity', 1),
            unit_price  = float(item.get('amount', 0)),
            total_price = float(item.get('amount', 0)) * item.get('quantity', 1),
        ))
    db.session.commit()
    return jsonify({'success': True, 'invoice_no': inv_no,
                    'total': total, 'message': f'Invoice {inv_no} created!'})
