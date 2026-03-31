"""
MediCore HMS — Laboratory Routes
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, date
from app import db
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.clinical import LabTest, LabOrder, LabOrderItem, Notification

lab_bp = Blueprint('lab', __name__)

def lab_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not (current_user.is_lab_tech() or current_user.is_admin()):
            return jsonify({'success': False, 'message': 'Lab access required'}), 403
        return f(*args, **kwargs)
    return decorated


@lab_bp.route('/dashboard')
@lab_required
def dashboard():
    return render_template('lab/dashboard.html')


# ── Stats ─────────────────────────────────────────────────────

@lab_bp.route('/api/stats')
@lab_required
def api_stats():
    today = date.today()
    return jsonify({'success': True, 'stats': {
        'pending':   LabOrder.query.filter(
            LabOrder.status.in_(['ordered','sample_collected','processing'])).count(),
        'completed_today': LabOrder.query.filter(
            db.func.date(LabOrder.completed_at) == today,
            LabOrder.status == 'completed').count(),
        'urgent':    LabOrder.query.filter(
            LabOrder.priority.in_(['urgent','stat']),
            LabOrder.status.notin_(['completed','cancelled'])).count(),
        'critical':  LabOrderItem.query.filter_by(is_critical=True, flag='critical').count(),
        'ordered_today': LabOrder.query.filter(
            db.func.date(LabOrder.ordered_at) == today).count(),
    }})


# ── Orders Queue ──────────────────────────────────────────────

@lab_bp.route('/api/orders')
@lab_required
def api_orders():
    status = request.args.get('status', 'pending')
    if status == 'pending':
        orders = LabOrder.query.filter(
            LabOrder.status.in_(['ordered','sample_collected','processing'])
        ).order_by(LabOrder.ordered_at.desc()).limit(50).all()
    elif status == 'completed':
        orders = LabOrder.query.filter_by(status='completed').order_by(
            LabOrder.completed_at.desc()).limit(30).all()
    else:
        orders = LabOrder.query.order_by(LabOrder.ordered_at.desc()).limit(30).all()

    result = []
    for o in orders:
        p   = Patient.query.get(o.patient_id)
        doc = Doctor.query.get(o.doctor_id)
        items = LabOrderItem.query.filter_by(order_id=o.id).all()
        result.append({
            'id':         o.id,
            'order_no':   o.order_no,
            'patient':    p.full_name if p else '?',
            'patient_id': o.patient_id,
            'uhid':       p.uhid if p else '?',
            'doctor':     doc.full_name if doc else '?',
            'priority':   o.priority,
            'status':     o.status,
            'ordered_at': o.ordered_at.strftime('%d %b %H:%M'),
            'notes':      o.notes or '',
            'tests': [{
                'item_id':    i.id,
                'test_id':    i.test_id,
                'test_name':  LabTest.query.get(i.test_id).name if LabTest.query.get(i.test_id) else '?',
                'status':     i.status,
                'result':     i.result_value or '',
                'unit':       i.result_unit or '',
                'normal_range': i.normal_range or '',
                'flag':       i.flag,
                'is_critical':i.is_critical,
            } for i in items],
        })
    return jsonify({'success': True, 'orders': result})


# ── Sample Collection ─────────────────────────────────────────

@lab_bp.route('/api/orders/<int:order_id>/collect', methods=['POST'])
@lab_required
def collect_sample(order_id):
    order = LabOrder.query.get_or_404(order_id)
    order.status              = 'sample_collected'
    order.sample_collected_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'message': 'Sample collected!'})


@lab_bp.route('/api/orders/<int:order_id>/process', methods=['POST'])
@lab_required
def start_processing(order_id):
    order = LabOrder.query.get_or_404(order_id)
    order.status = 'processing'
    LabOrderItem.query.filter_by(order_id=order_id, status='pending').update({'status':'processing'})
    db.session.commit()
    return jsonify({'success': True, 'message': 'Processing started'})


# ── Result Entry ──────────────────────────────────────────────

@lab_bp.route('/api/results/enter', methods=['POST'])
@lab_required
def enter_results():
    data  = request.get_json() or {}
    order = LabOrder.query.get_or_404(data.get('order_id'))
    has_critical = False

    for result in data.get('results', []):
        item = LabOrderItem.query.get(result['item_id'])
        if not item: continue
        item.result_value = result.get('value', '')
        item.result_unit  = result.get('unit', '')
        item.normal_range = result.get('normal_range', '')
        item.flag         = result.get('flag', 'normal')
        item.is_critical  = result.get('is_critical', False)
        item.status       = 'completed'
        item.done_by      = current_user.id
        item.done_at      = datetime.utcnow()
        if item.is_critical: has_critical = True

    # Check if all items done
    pending = LabOrderItem.query.filter_by(order_id=order.id, status='processing').count()
    if pending == 0:
        order.status       = 'completed'
        order.completed_at = datetime.utcnow()

    # Critical alert — notify doctor
    if has_critical:
        doc = Doctor.query.get(order.doctor_id)
        if doc:
            p = Patient.query.get(order.patient_id)
            db.session.add(Notification(
                user_id    = doc.user_id,
                title      = '⚠ Critical Lab Result',
                message    = f'Critical result for {p.full_name if p else "patient"} — Order {order.order_no}',
                notif_type = 'danger',
                module     = 'lab',
                reference_id = order.id,
            ))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Results saved!',
                    'has_critical': has_critical,
                    'order_complete': order.status == 'completed'})


# ── Report ────────────────────────────────────────────────────

@lab_bp.route('/api/orders/<int:order_id>/report')
@lab_required
def get_report(order_id):
    order = LabOrder.query.get_or_404(order_id)
    p     = Patient.query.get(order.patient_id)
    doc   = Doctor.query.get(order.doctor_id)
    items = LabOrderItem.query.filter_by(order_id=order_id).all()
    return jsonify({'success': True, 'report': {
        'order_no':    order.order_no,
        'patient':     p.full_name if p else '?',
        'uhid':        p.uhid if p else '?',
        'age_gender':  f'{p.age} yrs / {p.gender}' if p else '?',
        'doctor':      doc.full_name if doc else '?',
        'ordered_at':  order.ordered_at.strftime('%d %b %Y %H:%M'),
        'completed_at':order.completed_at.strftime('%d %b %Y %H:%M') if order.completed_at else '—',
        'tests': [{
            'name':         LabTest.query.get(i.test_id).name if LabTest.query.get(i.test_id) else '?',
            'result':       i.result_value or '—',
            'unit':         i.result_unit or '',
            'normal_range': i.normal_range or '—',
            'flag':         i.flag,
            'is_critical':  i.is_critical,
        } for i in items],
    }})


# ── Test Catalog ──────────────────────────────────────────────

@lab_bp.route('/api/tests')
@lab_required
def api_tests():
    tests = LabTest.query.filter_by(is_active=True).order_by(LabTest.name).all()
    return jsonify({'success': True, 'tests': [{
        'id': t.id, 'name': t.name, 'code': t.code,
        'category': t.category, 'sample_type': t.sample_type,
        'turnaround_hrs': t.turnaround_hrs, 'cost': float(t.cost),
        'normal_range': t.normal_range or '',
    } for t in tests]})


@lab_bp.route('/api/tests/add', methods=['POST'])
@lab_required
def add_test():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'success': False, 'message': 'Name required'}), 400
    test = LabTest(
        name           = data['name'].strip(),
        code           = data.get('code', '').strip().upper(),
        category       = data.get('category', '').strip(),
        sample_type    = data.get('sample_type', 'Blood').strip(),
        turnaround_hrs = int(data.get('turnaround_hrs', 24)),
        cost           = float(data.get('cost', 0)),
        normal_range   = data.get('normal_range', '').strip(),
        unit           = data.get('unit', '').strip(),
    )
    db.session.add(test)
    db.session.commit()
    return jsonify({'success': True, 'message': f'{test.name} added to catalog!'})
