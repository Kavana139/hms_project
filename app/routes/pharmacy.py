"""
MediCore HMS — Pharmacy Routes
"""
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, date, timedelta
from app import db
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.pharmacy import Drug, DrugInventory, Prescription, PrescriptionItem, Supplier
from app.models.clinical import Notification

pharmacy_bp = Blueprint('pharmacy', __name__)

def pharmacy_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not (current_user.is_pharmacist() or current_user.is_admin()):
            return jsonify({'success': False, 'message': 'Pharmacy access required'}), 403
        return f(*args, **kwargs)
    return decorated


@pharmacy_bp.route('/dashboard')
@pharmacy_required
def dashboard():
    return render_template('pharmacy/dashboard.html')


# ── Stats ─────────────────────────────────────────────────────

@pharmacy_bp.route('/api/stats')
@pharmacy_required
def api_stats():
    today     = date.today()
    threshold = today + timedelta(days=30)
    return jsonify({'success': True, 'stats': {
        'pending_rx':    Prescription.query.filter_by(status='active').count(),
        'dispensed_today': Prescription.query.filter(
            db.func.date(Prescription.dispensed_at) == today,
            Prescription.status == 'dispensed').count(),
        'low_stock':     DrugInventory.query.filter(
            DrugInventory.quantity <= DrugInventory.reorder_level).count(),
        'expiring_soon': DrugInventory.query.filter(
            DrugInventory.expiry_date <= threshold,
            DrugInventory.expiry_date >= today,
            DrugInventory.quantity > 0).count(),
        'total_drugs':   Drug.query.filter_by(is_active=True).count(),
        'out_of_stock':  DrugInventory.query.filter(DrugInventory.quantity == 0).count(),
    }})


# ── Prescription Queue ────────────────────────────────────────

@pharmacy_bp.route('/api/prescriptions')
@pharmacy_required
def api_prescriptions():
    status = request.args.get('status', 'active')
    rxs    = Prescription.query.filter_by(status=status).order_by(
        Prescription.created_at.desc()).limit(50).all()
    result = []
    for rx in rxs:
        try:
            p   = Patient.query.get(rx.patient_id)
            doc = Doctor.query.get(rx.doctor_id)
            items = PrescriptionItem.query.filter_by(prescription_id=rx.id).all()
            items_data = []
            for i in items:
                drug = Drug.query.get(i.drug_id)
                items_data.append({
                    'drug_id':      i.drug_id,
                    'drug_name':    drug.name if drug else '?',
                    'dosage':       i.dosage or '',
                    'frequency':    i.frequency or '',
                    'duration':     i.duration or '',
                    'quantity':     i.quantity or 0,
                    'instructions': i.instructions or '',
                    'is_dispensed': i.is_dispensed,
                })
            result.append({
                'id':              rx.id,
                'prescription_no': rx.prescription_no or f'RX-{rx.id}',
                'patient_name':    p.full_name if p else '?',
                'patient_uhid':    p.uhid if p else '?',
                'doctor_name':     doc.full_name if doc else '?',
                'status':          rx.status,
                'created_at':      rx.created_at.strftime('%d %b %Y %H:%M') if rx.created_at else '',
                'notes':           rx.notes or '',
                'item_count':      len(items_data),
                'items':           items_data,
            })
        except Exception as e:
            current_app.logger.error(f'Error processing prescription {rx.id}: {e}')
            continue
    return jsonify({'success': True, 'prescriptions': result})


@pharmacy_bp.route('/api/prescriptions/<int:rx_id>/dispense', methods=['POST'])
@pharmacy_required
def dispense_prescription(rx_id):
    rx    = Prescription.query.get_or_404(rx_id)
    items = PrescriptionItem.query.filter_by(prescription_id=rx_id).all()
    errors = []
    for item in items:
        inv = DrugInventory.query.filter_by(drug_id=item.drug_id).filter(
            DrugInventory.quantity >= item.quantity
        ).order_by(DrugInventory.expiry_date).first()
        if not inv:
            drug = Drug.query.get(item.drug_id)
            errors.append(f'{drug.name if drug else "Drug"}: insufficient stock')
            continue
        inv.quantity    -= item.quantity
        item.is_dispensed = True
    if errors:
        db.session.rollback()
        return jsonify({'success': False, 'message': '; '.join(errors)}), 400
    rx.status       = 'dispensed'
    rx.dispensed_by = current_user.id
    rx.dispensed_at = datetime.utcnow()
    # Notify patient
    p = Patient.query.get(rx.patient_id)
    if p and p.user_id:
        db.session.add(Notification(
            user_id=p.user_id, title='Prescription Ready',
            message=f'Your prescription {rx.prescription_no} has been dispensed',
            notif_type='success', module='pharmacy'))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Prescription dispensed successfully!'})


@pharmacy_bp.route('/api/prescriptions/<int:rx_id>/partial', methods=['POST'])
@pharmacy_required
def partial_dispense(rx_id):
    rx   = Prescription.query.get_or_404(rx_id)
    data = request.get_json() or {}
    for item_data in data.get('items', []):
        item = PrescriptionItem.query.get(item_data['item_id'])
        if not item: continue
        qty = item_data.get('quantity', 0)
        if qty <= 0: continue
        inv = DrugInventory.query.filter_by(drug_id=item.drug_id).filter(
            DrugInventory.quantity >= qty
        ).order_by(DrugInventory.expiry_date).first()
        if inv:
            inv.quantity  -= qty
            item.is_dispensed = True
    rx.status = 'partial'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Partial dispense saved'})


# ── Drug Inventory ────────────────────────────────────────────

@pharmacy_bp.route('/api/drugs')
@pharmacy_required
def api_drugs():
    search = request.args.get('search', '')
    page   = int(request.args.get('page', 1))
    per_pg = 20
    q = Drug.query.filter_by(is_active=True)
    if search:
        q = q.filter(db.or_(
            Drug.name.ilike(f'%{search}%'),
            Drug.generic_name.ilike(f'%{search}%'),
        ))
    total = q.count()
    drugs = q.order_by(Drug.name).offset((page-1)*per_pg).limit(per_pg).all()
    result = []
    for drug in drugs:
        inv = DrugInventory.query.filter_by(drug_id=drug.id).first()
        result.append({
            'id': drug.id, 'name': drug.name,
            'generic_name': drug.generic_name or '',
            'drug_type': drug.drug_type, 'category': drug.category or '',
            'stock': inv.quantity if inv else 0,
            'reorder_level': inv.reorder_level if inv else 10,
            'selling_price': float(inv.selling_price) if inv else 0,
            'expiry_date': inv.expiry_date.strftime('%d %b %Y') if (inv and inv.expiry_date) else '—',
            'batch': inv.batch_number if inv else '—',
            'is_low': (inv.quantity <= inv.reorder_level) if inv else False,
        })
    return jsonify({'success': True, 'drugs': result,
                    'total': total, 'page': page,
                    'pages': (total + per_pg - 1) // per_pg})


@pharmacy_bp.route('/api/drugs/add', methods=['POST'])
@pharmacy_required
def add_drug():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'success': False, 'message': 'Drug name required'}), 400
    drug = Drug(
        name         = data['name'].strip(),
        generic_name = data.get('generic_name', '').strip(),
        brand_name   = data.get('brand_name', '').strip(),
        category     = data.get('category', '').strip(),
        drug_type    = data.get('drug_type', 'tablet'),
        manufacturer = data.get('manufacturer', '').strip(),
        unit         = data.get('unit', 'strip'),
    )
    db.session.add(drug)
    db.session.flush()
    inv = DrugInventory(
        drug_id       = drug.id,
        batch_number  = data.get('batch_number', ''),
        quantity      = int(data.get('quantity', 0)),
        unit_cost     = float(data.get('unit_cost', 0)),
        selling_price = float(data.get('selling_price', 0)),
        reorder_level = int(data.get('reorder_level', 10)),
        expiry_date   = datetime.strptime(data['expiry_date'], '%Y-%m-%d').date()
                        if data.get('expiry_date') else None,
    )
    db.session.add(inv)
    db.session.commit()
    return jsonify({'success': True, 'message': f'{drug.name} added to inventory!'})


@pharmacy_bp.route('/api/drugs/<int:drug_id>/restock', methods=['POST'])
@pharmacy_required
def restock_drug(drug_id):
    data = request.get_json() or {}
    qty  = int(data.get('quantity', 0))
    if qty <= 0:
        return jsonify({'success': False, 'message': 'Quantity must be > 0'}), 400
    inv = DrugInventory.query.filter_by(drug_id=drug_id).first()
    if inv:
        inv.quantity += qty
        if data.get('batch_number'): inv.batch_number = data['batch_number']
        if data.get('expiry_date'):
            inv.expiry_date = datetime.strptime(data['expiry_date'], '%Y-%m-%d').date()
    else:
        inv = DrugInventory(drug_id=drug_id, quantity=qty,
                            batch_number=data.get('batch_number',''),
                            reorder_level=10)
        db.session.add(inv)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Stock updated! New qty: {inv.quantity}'})


# ── Low Stock & Expiry ────────────────────────────────────────

@pharmacy_bp.route('/api/alerts')
@pharmacy_required
def api_alerts():
    today     = date.today()
    threshold = today + timedelta(days=30)
    low_stock = DrugInventory.query.join(Drug).filter(
        DrugInventory.quantity <= DrugInventory.reorder_level,
        Drug.is_active == True
    ).all()
    expiring  = DrugInventory.query.join(Drug).filter(
        DrugInventory.expiry_date <= threshold,
        DrugInventory.expiry_date >= today,
        DrugInventory.quantity > 0,
        Drug.is_active == True
    ).order_by(DrugInventory.expiry_date).all()
    return jsonify({'success': True,
        'low_stock': [{'drug_id': i.drug_id, 'name': i.drug.name,
                       'current': i.quantity, 'reorder': i.reorder_level} for i in low_stock],
        'expiring':  [{'drug_id': i.drug_id, 'name': i.drug.name,
                       'qty': i.quantity,
                       'expiry': i.expiry_date.strftime('%d %b %Y')} for i in expiring],
    })


# ── Drug Search ───────────────────────────────────────────────

@pharmacy_bp.route('/api/drugs/search')
@pharmacy_required
def drug_search():
    q     = request.args.get('q', '')
    drugs = Drug.query.filter(
        db.or_(Drug.name.ilike(f'%{q}%'), Drug.generic_name.ilike(f'%{q}%'))
    ).filter_by(is_active=True).limit(10).all()
    return jsonify({'success': True, 'drugs': [d.to_dict() for d in drugs]})
