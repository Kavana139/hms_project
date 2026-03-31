"""
MediCore HMS — Doctor Routes
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, timedelta, date
from app import db
from app.models.user import User
from app.models.doctor import Doctor, DoctorSchedule
from app.models.patient import Patient, PatientAllergy, PatientChronicCondition
from app.models.appointment import Appointment, Visit, SOAPNote, Vital
from app.models.pharmacy import Drug, Prescription, PrescriptionItem, DrugInteraction
from app.models.clinical import LabTest, LabOrder, LabOrderItem, Notification, ICD10Code

doctor_bp = Blueprint('doctor', __name__)

def doctor_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_doctor():
            return jsonify({'success': False, 'message': 'Doctor access required'}), 403
        return f(*args, **kwargs)
    return decorated

def get_doctor():
    return Doctor.query.filter_by(user_id=current_user.id).first()

# ── Dashboard ─────────────────────────────────────────────────

@doctor_bp.route('/dashboard')
@doctor_required
def dashboard():
    return render_template('doctor/dashboard.html')

# ── Stats ─────────────────────────────────────────────────────

@doctor_bp.route('/api/stats')
@doctor_required
def api_stats():
    doctor = get_doctor()
    if not doctor:
        return jsonify({'success': False, 'message': 'Doctor profile not found'}), 404
    today = date.today()
    total   = Appointment.query.filter_by(doctor_id=doctor.id, appointment_date=today).count()
    seen    = Appointment.query.filter_by(doctor_id=doctor.id, appointment_date=today, status='completed').count()
    waiting = Appointment.query.filter_by(doctor_id=doctor.id, appointment_date=today, status='checked_in').count()
    pending = Appointment.query.filter(
        Appointment.doctor_id==doctor.id,
        Appointment.appointment_date==today,
        Appointment.status.in_(['scheduled','confirmed'])
    ).count()
    return jsonify({'success': True, 'stats': {
        'today_total': total, 'seen': seen,
        'waiting': waiting, 'pending': pending,
        'doctor_name': doctor.full_name,
        'specialization': doctor.specialization or '',
    }})

# ── Today's Queue ─────────────────────────────────────────────

@doctor_bp.route('/api/queue')
@doctor_required
def api_queue():
    doctor = get_doctor()
    if not doctor:
        return jsonify({'success': False, 'message': 'Doctor profile not found'}), 404
    today = date.today()
    appts = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date == today
    ).order_by(Appointment.token_number).all()
    result = []
    for a in appts:
        p = Patient.query.get(a.patient_id)
        result.append({
            'id': a.id, 'token': a.token_number,
            'patient_id': p.id if p else None,
            'patient_name': p.full_name if p else 'Unknown',
            'age': p.age if p else None,
            'gender': p.gender if p else None,
            'blood_group': p.blood_group if p else None,
            'appt_type': a.appt_type,
            'status': a.status,
            'time': a.appointment_time.strftime('%H:%M') if a.appointment_time else '',
            'reason': a.reason or '',
        })
    return jsonify({'success': True, 'queue': result})

@doctor_bp.route('/api/appointments/<int:appt_id>/status', methods=['POST'])
@doctor_required
def update_appt_status(appt_id):
    appt   = Appointment.query.get_or_404(appt_id)
    data   = request.get_json() or {}
    status = data.get('status')
    if status not in ['in_progress','completed','no_show']:
        return jsonify({'success': False, 'message': 'Invalid status'}), 400
    appt.status = status
    # Auto create visit when consultation starts
    if status == 'in_progress':
        existing = Visit.query.filter_by(appointment_id=appt_id).first()
        if not existing:
            visit = Visit(
                visit_no       = f'V{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
                patient_id     = appt.patient_id,
                doctor_id      = appt.doctor_id,
                appointment_id = appt_id,
                visit_type     = 'opd',
                chief_complaint= appt.reason or '',
            )
            db.session.add(visit)
    db.session.commit()
    return jsonify({'success': True})

# ── Patient Record ────────────────────────────────────────────

@doctor_bp.route('/api/patient/<int:patient_id>')
@doctor_required
def api_patient(patient_id):
    p = Patient.query.get_or_404(patient_id)
    allergies   = PatientAllergy.query.filter_by(patient_id=patient_id).all()
    conditions  = PatientChronicCondition.query.filter_by(patient_id=patient_id).all()
    visits      = Visit.query.filter_by(patient_id=patient_id).order_by(Visit.visit_date.desc()).limit(10).all()
    last_vitals = Vital.query.filter_by(patient_id=patient_id).order_by(Vital.recorded_at.desc()).first()
    return jsonify({'success': True, 'patient': {
        **p.to_dict(),
        'date_of_birth': p.date_of_birth.isoformat() if p.date_of_birth else None,
        'address': p.address, 'city': p.city, 'phone': p.phone,
        'emergency_phone': p.emergency_phone, 'occupation': p.occupation,
        'allergies': [{'allergen': a.allergen, 'severity': a.severity} for a in allergies],
        'conditions': [{'condition': c.condition, 'icd10_code': c.icd10_code} for c in conditions],
        'visits': [{'id': v.id, 'date': v.visit_date.strftime('%d %b %Y'),
                    'chief_complaint': v.chief_complaint, 'status': v.status} for v in visits],
        'last_vitals': last_vitals.to_dict() if last_vitals else None,
    }})

# ── Vitals ────────────────────────────────────────────────────

@doctor_bp.route('/api/vitals', methods=['POST'])
@doctor_required
def save_vitals():
    data = request.get_json() or {}
    if not data.get('patient_id'):
        return jsonify({'success': False, 'message': 'patient_id required'}), 400
    # Calculate BMI
    bmi = None
    w   = data.get('weight_kg')
    h   = data.get('height_cm')
    if w and h:
        try:
            bmi = round(float(w) / ((float(h)/100) ** 2), 1)
        except Exception:
            pass
    vital = Vital(
        patient_id       = data['patient_id'],
        visit_id         = data.get('visit_id'),
        systolic_bp      = data.get('systolic_bp'),
        diastolic_bp     = data.get('diastolic_bp'),
        pulse_rate       = data.get('pulse_rate'),
        temperature      = data.get('temperature'),
        temp_unit        = data.get('temp_unit', 'F'),
        respiratory_rate = data.get('respiratory_rate'),
        spo2             = data.get('spo2'),
        weight_kg        = w,
        height_cm        = h,
        bmi              = bmi,
        blood_sugar      = data.get('blood_sugar'),
        sugar_type       = data.get('sugar_type', 'random'),
        notes            = data.get('notes', ''),
        recorded_by      = current_user.id,
    )
    db.session.add(vital)
    db.session.commit()
    return jsonify({'success': True, 'bmi': bmi, 'message': 'Vitals saved!'})

@doctor_bp.route('/api/vitals/<int:patient_id>/history')
@doctor_required
def vitals_history(patient_id):
    vitals = Vital.query.filter_by(patient_id=patient_id).order_by(Vital.recorded_at.desc()).limit(10).all()
    return jsonify({'success': True, 'vitals': [v.to_dict() for v in vitals]})

# ── SOAP Notes ────────────────────────────────────────────────

@doctor_bp.route('/api/soap', methods=['POST'])
@doctor_required
def save_soap():
    data = request.get_json() or {}
    if not data.get('visit_id'):
        return jsonify({'success': False, 'message': 'visit_id required'}), 400
    existing = SOAPNote.query.filter_by(visit_id=data['visit_id']).first()
    if existing:
        existing.subjective     = data.get('subjective', '')
        existing.objective      = data.get('objective', '')
        existing.assessment     = data.get('assessment', '')
        existing.plan           = data.get('plan', '')
        existing.icd10_code     = data.get('icd10_code', '')
        existing.icd10_desc     = data.get('icd10_desc', '')
        existing.follow_up_days = data.get('follow_up_days')
        existing.updated_at     = datetime.utcnow()
    else:
        soap = SOAPNote(
            visit_id       = data['visit_id'],
            subjective     = data.get('subjective', ''),
            objective      = data.get('objective', ''),
            assessment     = data.get('assessment', ''),
            plan           = data.get('plan', ''),
            icd10_code     = data.get('icd10_code', ''),
            icd10_desc     = data.get('icd10_desc', ''),
            follow_up_days = data.get('follow_up_days'),
            written_by     = current_user.id,
        )
        db.session.add(soap)
        # Close visit
        visit = Visit.query.get(data['visit_id'])
        if visit: visit.status = 'closed'
    db.session.commit()
    return jsonify({'success': True, 'message': 'SOAP notes saved!'})

@doctor_bp.route('/api/soap/<int:visit_id>')
@doctor_required
def get_soap(visit_id):
    soap = SOAPNote.query.filter_by(visit_id=visit_id).first()
    if not soap:
        return jsonify({'success': True, 'soap': None})
    return jsonify({'success': True, 'soap': {
        'subjective': soap.subjective, 'objective': soap.objective,
        'assessment': soap.assessment, 'plan': soap.plan,
        'icd10_code': soap.icd10_code, 'icd10_desc': soap.icd10_desc,
        'follow_up_days': soap.follow_up_days,
    }})

# ── Prescriptions ─────────────────────────────────────────────

@doctor_bp.route('/api/prescription', methods=['POST'])
@doctor_required
def save_prescription():
    doctor = get_doctor()
    data   = request.get_json() or {}
    if not data.get('visit_id') or not data.get('patient_id'):
        return jsonify({'success': False, 'message': 'visit_id and patient_id required'}), 400
    rx = Prescription(
        prescription_no = f'RX{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
        visit_id        = data['visit_id'],
        patient_id      = data['patient_id'],
        doctor_id       = doctor.id,
        notes           = data.get('notes', ''),
        status          = 'active',
    )
    db.session.add(rx)
    db.session.flush()
    for item in data.get('items', []):
        db.session.add(PrescriptionItem(
            prescription_id = rx.id,
            drug_id         = item['drug_id'],
            dosage          = item.get('dosage', ''),
            frequency       = item.get('frequency', ''),
            duration        = item.get('duration', ''),
            quantity        = item.get('quantity', 1),
            instructions    = item.get('instructions', ''),
        ))
    db.session.commit()
    return jsonify({'success': True, 'prescription_id': rx.id,
                    'prescription_no': rx.prescription_no})

# ── Drug Search & Interaction ─────────────────────────────────

@doctor_bp.route('/api/drugs/search')
@doctor_required
def drug_search():
    q     = request.args.get('q', '').strip()
    drugs = Drug.query.filter(
        db.or_(Drug.name.ilike(f'%{q}%'), Drug.generic_name.ilike(f'%{q}%'))
    ).filter_by(is_active=True).limit(15).all()
    return jsonify({'success': True, 'drugs': [d.to_dict() for d in drugs]})

@doctor_bp.route('/api/drugs/interactions')
@doctor_required
def drug_interactions():
    ids  = request.args.getlist('drug_ids', type=int)
    if len(ids) < 2:
        return jsonify({'success': True, 'interactions': []})
    interactions = DrugInteraction.query.filter(
        db.or_(
            db.and_(DrugInteraction.drug_id_1.in_(ids), DrugInteraction.drug_id_2.in_(ids))
        )
    ).all()
    result = []
    for i in interactions:
        d1 = Drug.query.get(i.drug_id_1)
        d2 = Drug.query.get(i.drug_id_2)
        result.append({
            'drug1': d1.name if d1 else '', 'drug2': d2.name if d2 else '',
            'severity': i.severity, 'description': i.description,
        })
    return jsonify({'success': True, 'interactions': result})

# ── ICD-10 Search ─────────────────────────────────────────────

@doctor_bp.route('/api/icd10/search')
@doctor_required
def icd10_search():
    q     = request.args.get('q', '').strip()
    codes = ICD10Code.query.filter(
        db.or_(ICD10Code.code.ilike(f'%{q}%'), ICD10Code.description.ilike(f'%{q}%'))
    ).limit(10).all()
    return jsonify({'success': True, 'codes': [c.to_dict() for c in codes]})

# ── Lab Requests ──────────────────────────────────────────────

@doctor_bp.route('/api/lab-order', methods=['POST'])
@doctor_required
def create_lab_order():
    doctor = get_doctor()
    data   = request.get_json() or {}
    if not data.get('patient_id') or not data.get('tests'):
        return jsonify({'success': False, 'message': 'patient_id and tests required'}), 400
    order = LabOrder(
        order_no   = f'LAB{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
        patient_id = data['patient_id'],
        doctor_id  = doctor.id,
        visit_id   = data.get('visit_id'),
        priority   = data.get('priority', 'routine'),
        notes      = data.get('notes', ''),
    )
    db.session.add(order)
    db.session.flush()
    for test_id in data['tests']:
        db.session.add(LabOrderItem(order_id=order.id, test_id=test_id))
    db.session.commit()
    # Notify lab
    from app.models.user import Role
    lab_users = User.query.join(Role).filter(Role.name == 'lab_tech').all()
    for u in lab_users:
        db.session.add(Notification(
            user_id=u.id, title='New Lab Order',
            message=f'Order {order.order_no} from {doctor.full_name}',
            notif_type='info', module='lab', reference_id=order.id))
    db.session.commit()
    return jsonify({'success': True, 'order_no': order.order_no})

@doctor_bp.route('/api/lab-tests')
@doctor_required
def lab_tests():
    tests = LabTest.query.filter_by(is_active=True).order_by(LabTest.name).all()
    return jsonify({'success': True, 'tests': [{
        'id': t.id, 'name': t.name, 'code': t.code,
        'category': t.category, 'cost': float(t.cost),
        'turnaround_hrs': t.turnaround_hrs,
    } for t in tests]})

# ── My Schedule ───────────────────────────────────────────────

@doctor_bp.route('/api/my-schedule')
@doctor_required
def my_schedule():
    doctor    = get_doctor()
    schedules = DoctorSchedule.query.filter_by(doctor_id=doctor.id, is_active=True).all()
    return jsonify({'success': True, 'schedules': [{
        'day': s.day_of_week, 'start': s.start_time.strftime('%H:%M'),
        'end': s.end_time.strftime('%H:%M'),
        'slots': s.slot_duration, 'max': s.max_patients,
    } for s in schedules]})

# ── Upcoming Appointments ─────────────────────────────────────

@doctor_bp.route('/api/upcoming')
@doctor_required
def upcoming():
    doctor = get_doctor()
    today  = date.today()
    appts  = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date >= today,
        Appointment.status.in_(['scheduled','confirmed'])
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).limit(20).all()
    result = []
    for a in appts:
        p = Patient.query.get(a.patient_id)
        result.append({
            'id': a.id,
            'date': a.appointment_date.strftime('%d %b %Y'),
            'time': a.appointment_time.strftime('%H:%M') if a.appointment_time else '',
            'patient': p.full_name if p else 'Unknown',
            'type': a.appt_type, 'status': a.status,
        })
    return jsonify({'success': True, 'appointments': result})
