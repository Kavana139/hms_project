from app import db
from datetime import datetime


# ── LAB ───────────────────────────────────────────────────────

class LabTest(db.Model):
    __tablename__ = 'lab_tests'
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(150), nullable=False)
    code           = db.Column(db.String(30), unique=True)
    category       = db.Column(db.String(80))
    sample_type    = db.Column(db.String(80))
    turnaround_hrs = db.Column(db.Integer, default=24)
    cost           = db.Column(db.Numeric(10,2), default=0.00)
    normal_range   = db.Column(db.Text)
    unit           = db.Column(db.String(30))
    description    = db.Column(db.Text)
    is_active      = db.Column(db.Boolean, default=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)


class LabOrder(db.Model):
    __tablename__ = 'lab_orders'
    id                  = db.Column(db.Integer, primary_key=True)
    order_no            = db.Column(db.String(30), unique=True)
    patient_id          = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id           = db.Column(db.Integer, db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    visit_id            = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'))
    priority            = db.Column(db.Enum('routine','urgent','stat'), default='routine')
    status              = db.Column(db.Enum('ordered','sample_collected','processing','completed','cancelled'), default='ordered')
    notes               = db.Column(db.Text)
    ordered_at          = db.Column(db.DateTime, default=datetime.utcnow)
    sample_collected_at = db.Column(db.DateTime)
    completed_at        = db.Column(db.DateTime)

    items   = db.relationship('LabOrderItem', backref='order', lazy='dynamic')
    patient = db.relationship('Patient', backref='lab_orders')
    doctor  = db.relationship('Doctor', backref='lab_orders')


class LabOrderItem(db.Model):
    __tablename__ = 'lab_order_items'
    id           = db.Column(db.Integer, primary_key=True)
    order_id     = db.Column(db.Integer, db.ForeignKey('lab_orders.id', ondelete='CASCADE'), nullable=False)
    test_id      = db.Column(db.Integer, db.ForeignKey('lab_tests.id', ondelete='CASCADE'), nullable=False)
    status       = db.Column(db.Enum('pending','processing','completed'), default='pending')
    result_value = db.Column(db.String(255))
    result_unit  = db.Column(db.String(30))
    normal_range = db.Column(db.String(100))
    is_critical  = db.Column(db.Boolean, default=False)
    flag         = db.Column(db.Enum('normal','high','low','critical'), default='normal')
    notes        = db.Column(db.Text)
    done_by      = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    done_at      = db.Column(db.DateTime)
    test         = db.relationship('LabTest')


# ── WARD & BED ────────────────────────────────────────────────

class Ward(db.Model):
    __tablename__ = 'wards'
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(80), nullable=False)
    ward_type      = db.Column(db.Enum('general','private','semi_private','icu','nicu','ot','emergency'), default='general')
    floor          = db.Column(db.String(20))
    total_beds     = db.Column(db.Integer, default=0)
    charge_per_day = db.Column(db.Numeric(10,2), default=0.00)
    description    = db.Column(db.Text)
    is_active      = db.Column(db.Boolean, default=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    beds           = db.relationship('Bed', backref='ward', lazy='dynamic')


class Bed(db.Model):
    __tablename__ = 'beds'
    id         = db.Column(db.Integer, primary_key=True)
    bed_number = db.Column(db.String(20), nullable=False)
    ward_id    = db.Column(db.Integer, db.ForeignKey('wards.id', ondelete='CASCADE'), nullable=False)
    bed_type   = db.Column(db.Enum('standard','electric','icu','nicu'), default='standard')
    status     = db.Column(db.Enum('available','occupied','cleaning','maintenance','reserved'), default='available')
    features   = db.Column(db.String(255))
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'bed_number': self.bed_number,
            'ward': self.ward.name if self.ward else None,
            'status': self.status, 'bed_type': self.bed_type,
        }


class Admission(db.Model):
    __tablename__ = 'admissions'
    id                = db.Column(db.Integer, primary_key=True)
    admission_no      = db.Column(db.String(30), unique=True)
    patient_id        = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id         = db.Column(db.Integer, db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    bed_id            = db.Column(db.Integer, db.ForeignKey('beds.id'), nullable=False)
    ward_id           = db.Column(db.Integer, db.ForeignKey('wards.id'), nullable=False)
    admission_date    = db.Column(db.DateTime, default=datetime.utcnow)
    expected_discharge= db.Column(db.Date)
    actual_discharge  = db.Column(db.DateTime)
    admission_reason  = db.Column(db.Text)
    diagnosis         = db.Column(db.Text)
    status            = db.Column(db.Enum('admitted','discharged','transferred','absconded'), default='admitted')
    discharge_summary = db.Column(db.Text)
    admitted_by       = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    discharged_by     = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship('Patient', backref='admissions')
    doctor  = db.relationship('Doctor', backref='admissions')
    bed     = db.relationship('Bed', backref='admissions')
    ward    = db.relationship('Ward', backref='admissions')


# ── BILLING ───────────────────────────────────────────────────

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id           = db.Column(db.Integer, primary_key=True)
    invoice_no   = db.Column(db.String(30), unique=True)
    patient_id   = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    visit_id     = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'))
    admission_id = db.Column(db.Integer, db.ForeignKey('admissions.id', ondelete='SET NULL'))
    invoice_date = db.Column(db.Date, default=datetime.utcnow)
    due_date     = db.Column(db.Date)
    subtotal     = db.Column(db.Numeric(12,2), default=0.00)
    discount_pct = db.Column(db.Numeric(5,2), default=0.00)
    discount_amt = db.Column(db.Numeric(12,2), default=0.00)
    gst_pct      = db.Column(db.Numeric(5,2), default=18.00)
    gst_amount   = db.Column(db.Numeric(12,2), default=0.00)
    total_amount = db.Column(db.Numeric(12,2), default=0.00)
    paid_amount  = db.Column(db.Numeric(12,2), default=0.00)
    balance      = db.Column(db.Numeric(12,2), default=0.00)
    status       = db.Column(db.Enum('draft','pending','partial','paid','cancelled','refunded'), default='pending')
    payment_mode = db.Column(db.Enum('cash','card','upi','net_banking','insurance','razorpay'), default='cash')
    notes        = db.Column(db.Text)
    created_by   = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items   = db.relationship('InvoiceItem', backref='invoice', lazy='dynamic')
    patient = db.relationship('Patient', backref='invoices')


class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    id          = db.Column(db.Integer, primary_key=True)
    invoice_id  = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False)
    item_type   = db.Column(db.Enum('consultation','lab','radiology','pharmacy','room','procedure','other'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    quantity    = db.Column(db.Integer, default=1)
    unit_price  = db.Column(db.Numeric(10,2), default=0.00)
    total_price = db.Column(db.Numeric(12,2), default=0.00)


class Payment(db.Model):
    __tablename__ = 'payments'
    id                  = db.Column(db.Integer, primary_key=True)
    payment_no          = db.Column(db.String(30), unique=True)
    invoice_id          = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False)
    patient_id          = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    amount              = db.Column(db.Numeric(12,2), nullable=False)
    payment_mode        = db.Column(db.Enum('cash','card','upi','net_banking','insurance','razorpay'), default='cash')
    transaction_id      = db.Column(db.String(100))
    razorpay_order_id   = db.Column(db.String(100))
    razorpay_payment_id = db.Column(db.String(100))
    status              = db.Column(db.Enum('pending','success','failed','refunded'), default='pending')
    receipt_path        = db.Column(db.String(255))
    paid_at             = db.Column(db.DateTime, default=datetime.utcnow)
    collected_by        = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))


# ── NOTIFICATIONS ─────────────────────────────────────────────

class Notification(db.Model):
    __tablename__ = 'notifications'
    id           = db.Column(db.BigInteger, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title        = db.Column(db.String(255), nullable=False)
    message      = db.Column(db.Text)
    notif_type   = db.Column(db.Enum('info','success','warning','danger'), default='info')
    module       = db.Column(db.String(50))
    reference_id = db.Column(db.Integer)
    is_read      = db.Column(db.Boolean, default=False)
    read_at      = db.Column(db.DateTime)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'title': self.title,
            'message': self.message, 'notif_type': self.notif_type,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class NotificationLog(db.Model):
    __tablename__ = 'notification_logs'
    id           = db.Column(db.BigInteger, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    channel      = db.Column(db.Enum('email','sms','whatsapp','in_app'), nullable=False)
    recipient    = db.Column(db.String(120))
    subject      = db.Column(db.String(255))
    message      = db.Column(db.Text)
    status       = db.Column(db.Enum('pending','sent','failed'), default='pending')
    error        = db.Column(db.Text)
    sent_at      = db.Column(db.DateTime, default=datetime.utcnow)


# ── ICD10 ─────────────────────────────────────────────────────

class ICD10Code(db.Model):
    __tablename__ = 'icd10_codes'
    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(10), nullable=False, unique=True)
    description = db.Column(db.String(255), nullable=False)
    category    = db.Column(db.String(100))

    def to_dict(self):
        return {'code': self.code, 'description': self.description, 'category': self.category}
