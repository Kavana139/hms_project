"""
MediCore HMS — Billing Routes
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, date, timedelta
from app import db
from app.models.user import User, HospitalSetting
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Visit
from app.models.clinical import (Invoice, InvoiceItem, Payment,
    Notification)

billing_bp = Blueprint('billing', __name__)

def billing_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not (current_user.is_receptionist() or current_user.is_admin()):
            return jsonify({'success': False, 'message': 'Billing access required'}), 403
        return f(*args, **kwargs)
    return decorated


@billing_bp.route('/dashboard')
@billing_required
def dashboard():
    return render_template('billing/dashboard.html')


# ── Stats ─────────────────────────────────────────────────────

@billing_bp.route('/api/stats')
@billing_required
def api_stats():
    today = date.today()
    week_start = today - timedelta(days=7)
    revenue_today = db.session.query(
        db.func.coalesce(db.func.sum(Invoice.total_amount), 0)
    ).filter(db.func.date(Invoice.created_at) == today,
             Invoice.status == 'paid').scalar() or 0
    revenue_week = db.session.query(
        db.func.coalesce(db.func.sum(Invoice.total_amount), 0)
    ).filter(Invoice.invoice_date >= week_start,
             Invoice.status == 'paid').scalar() or 0
    return jsonify({'success': True, 'stats': {
        'revenue_today':   float(revenue_today),
        'revenue_week':    float(revenue_week),
        'pending_bills':   Invoice.query.filter_by(status='pending').count(),
        'partial_bills':   Invoice.query.filter_by(status='partial').count(),
        'paid_today':      Invoice.query.filter(
            db.func.date(Invoice.created_at) == today,
            Invoice.status == 'paid').count(),
        'total_invoices':  Invoice.query.count(),
    }})


# ── Invoices ──────────────────────────────────────────────────

@billing_bp.route('/api/invoices')
@billing_required
def api_invoices():
    status  = request.args.get('status', '')
    search  = request.args.get('search', '')
    page    = int(request.args.get('page', 1))
    per_pg  = 20
    q = Invoice.query.join(Patient, Invoice.patient_id == Patient.id)
    if status:
        q = q.filter(Invoice.status == status)
    if search:
        q = q.filter(db.or_(
            Patient.first_name.ilike(f'%{search}%'),
            Patient.last_name.ilike(f'%{search}%'),
            Invoice.invoice_no.ilike(f'%{search}%'),
        ))
    total    = q.count()
    invoices = q.order_by(Invoice.created_at.desc()).offset(
        (page-1)*per_pg).limit(per_pg).all()
    result = []
    for inv in invoices:
        p = Patient.query.get(inv.patient_id)
        result.append({
            'id':          inv.id,
            'invoice_no':  inv.invoice_no,
            'patient':     p.full_name if p else '?',
            'uhid':        p.uhid if p else '?',
            'date':        inv.invoice_date.strftime('%d %b %Y') if inv.invoice_date else '—',
            'total':       float(inv.total_amount),
            'paid':        float(inv.paid_amount),
            'balance':     float(inv.balance),
            'status':      inv.status,
        })
    return jsonify({'success': True, 'invoices': result,
                    'total': total, 'page': page,
                    'pages': (total + per_pg - 1) // per_pg})


@billing_bp.route('/api/invoices/<int:inv_id>')
@billing_required
def get_invoice(inv_id):
    inv   = Invoice.query.get_or_404(inv_id)
    p     = Patient.query.get(inv.patient_id)
    items = InvoiceItem.query.filter_by(invoice_id=inv_id).all()
    payments = Payment.query.filter_by(invoice_id=inv_id).all()
    hospital = {
        'name':    HospitalSetting.get('hospital_name', 'MediCore Hospital'),
        'address': HospitalSetting.get('hospital_address', ''),
        'phone':   HospitalSetting.get('hospital_phone', ''),
        'gst':     HospitalSetting.get('gst_number', ''),
        'symbol':  HospitalSetting.get('currency_symbol', '₹'),
    }
    return jsonify({'success': True,
        'hospital': hospital,
        'invoice': {
            'id': inv.id, 'invoice_no': inv.invoice_no,
            'date': inv.invoice_date.strftime('%d %b %Y') if inv.invoice_date else '—',
            'patient': p.full_name if p else '?',
            'uhid': p.uhid if p else '?',
            'phone': p.phone if p else '',
            'subtotal':     float(inv.subtotal),
            'discount_pct': float(inv.discount_pct),
            'discount_amt': float(inv.discount_amt),
            'gst_pct':      float(inv.gst_pct),
            'gst_amount':   float(inv.gst_amount),
            'total':        float(inv.total_amount),
            'paid':         float(inv.paid_amount),
            'balance':      float(inv.balance),
            'status':       inv.status,
            'items': [{
                'description': i.description,
                'item_type':   i.item_type,
                'quantity':    i.quantity,
                'unit_price':  float(i.unit_price),
                'total':       float(i.total_price),
            } for i in items],
            'payments': [{
                'amount': float(pay.amount),
                'mode':   pay.payment_mode,
                'date':   pay.paid_at.strftime('%d %b %Y %H:%M'),
                'status': pay.status,
            } for pay in payments],
        }
    })


@billing_bp.route('/api/invoices/create', methods=['POST'])
@billing_required
def create_invoice():
    data     = request.get_json() or {}
    if not data.get('patient_id'):
        return jsonify({'success': False, 'message': 'patient_id required'}), 400
    gst_rate = float(data.get('gst_pct', HospitalSetting.get('gst_rate', '18') or 18))
    subtotal = sum(float(i.get('unit_price', 0)) * int(i.get('quantity', 1))
                   for i in data.get('items', []))
    disc_pct = float(data.get('discount_pct', 0))
    disc_amt = round(subtotal * disc_pct / 100, 2)
    taxable  = subtotal - disc_amt
    gst_amt  = round(taxable * gst_rate / 100, 2)
    total    = round(taxable + gst_amt, 2)
    inv_no   = f'INV{datetime.utcnow().strftime("%Y%m%d%H%M%S")}'
    invoice  = Invoice(
        invoice_no   = inv_no,
        patient_id   = int(data['patient_id']),
        visit_id     = data.get('visit_id'),
        admission_id = data.get('admission_id'),
        invoice_date = date.today(),
        subtotal     = subtotal,
        discount_pct = disc_pct,
        discount_amt = disc_amt,
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
        qty   = int(item.get('quantity', 1))
        price = float(item.get('unit_price', 0))
        db.session.add(InvoiceItem(
            invoice_id  = invoice.id,
            item_type   = item.get('item_type', 'consultation'),
            description = item.get('description', ''),
            quantity    = qty,
            unit_price  = price,
            total_price = qty * price,
        ))
    db.session.commit()
    # Notify patient
    p = Patient.query.get(data['patient_id'])
    if p and p.user_id:
        db.session.add(Notification(
            user_id=p.user_id, title='New Invoice',
            message=f'Invoice {inv_no} for ₹{total:.2f} has been generated',
            notif_type='info', module='billing'))
        db.session.commit()
    return jsonify({'success': True, 'invoice_no': inv_no,
                    'invoice_id': invoice.id, 'total': total,
                    'message': f'Invoice {inv_no} created!'})


# ── Payments ──────────────────────────────────────────────────

@billing_bp.route('/api/invoices/<int:inv_id>/pay', methods=['POST'])
@billing_required
def record_payment(inv_id):
    inv  = Invoice.query.get_or_404(inv_id)
    data = request.get_json() or {}
    amt  = float(data.get('amount', 0))
    if amt <= 0:
        return jsonify({'success': False, 'message': 'Amount must be > 0'}), 400
    if amt > float(inv.balance):
        return jsonify({'success': False, 'message': 'Amount exceeds balance'}), 400
    pay = Payment(
        payment_no   = f'PAY{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
        invoice_id   = inv_id,
        patient_id   = inv.patient_id,
        amount       = amt,
        payment_mode = data.get('mode', 'cash'),
        transaction_id = data.get('transaction_id', ''),
        status       = 'success',
        collected_by = current_user.id,
    )
    inv.paid_amount = float(inv.paid_amount) + amt
    inv.balance     = float(inv.total_amount) - float(inv.paid_amount)
    inv.status      = 'paid' if inv.balance <= 0 else 'partial'
    inv.payment_mode = data.get('mode', 'cash')
    db.session.add(pay)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Payment recorded!',
                    'payment_no': pay.payment_no,
                    'balance': float(inv.balance),
                    'status': inv.status})


@billing_bp.route('/api/invoices/<int:inv_id>/discount', methods=['POST'])
@billing_required
def apply_discount(inv_id):
    inv  = Invoice.query.get_or_404(inv_id)
    data = request.get_json() or {}
    disc = float(data.get('discount_pct', 0))
    if not 0 <= disc <= 100:
        return jsonify({'success': False, 'message': 'Discount must be 0-100%'}), 400
    disc_amt    = round(float(inv.subtotal) * disc / 100, 2)
    taxable     = float(inv.subtotal) - disc_amt
    gst_amt     = round(taxable * float(inv.gst_pct) / 100, 2)
    total       = round(taxable + gst_amt, 2)
    inv.discount_pct = disc
    inv.discount_amt = disc_amt
    inv.gst_amount   = gst_amt
    inv.total_amount = total
    inv.balance      = total - float(inv.paid_amount)
    db.session.commit()
    return jsonify({'success': True, 'total': total, 'message': 'Discount applied!'})


# ── Revenue Reports ───────────────────────────────────────────

@billing_bp.route('/api/revenue/daily')
@billing_required
def daily_revenue():
    labels, data = [], []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        rev = db.session.query(
            db.func.coalesce(db.func.sum(Invoice.total_amount), 0)
        ).filter(Invoice.invoice_date == d,
                 Invoice.status == 'paid').scalar() or 0
        labels.append(d.strftime('%a'))
        data.append(float(rev))
    return jsonify({'success': True, 'labels': labels, 'data': data})


@billing_bp.route('/api/patients/search')
@billing_required
def search_patients():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'success': True, 'patients': []})
    patients = Patient.query.filter(
        db.or_(Patient.first_name.ilike(f'%{q}%'),
               Patient.last_name.ilike(f'%{q}%'),
               Patient.uhid.ilike(f'%{q}%'),
               Patient.phone.ilike(f'%{q}%'))
    ).limit(10).all()
    return jsonify({'success': True,
                    'patients': [p.to_dict() for p in patients]})
