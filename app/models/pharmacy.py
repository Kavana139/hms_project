from app import db
from datetime import datetime


class Drug(db.Model):
    __tablename__ = 'drugs'
    id                = db.Column(db.Integer, primary_key=True)
    name              = db.Column(db.String(150), nullable=False)
    generic_name      = db.Column(db.String(150))
    brand_name        = db.Column(db.String(150))
    category          = db.Column(db.String(80))
    drug_type         = db.Column(db.Enum('tablet','capsule','syrup','injection','cream','drops','inhaler','other'), default='tablet')
    manufacturer      = db.Column(db.String(100))
    unit              = db.Column(db.String(30))
    description       = db.Column(db.Text)
    contraindications = db.Column(db.Text)
    side_effects      = db.Column(db.Text)
    is_active         = db.Column(db.Boolean, default=True)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    inventory    = db.relationship('DrugInventory', backref='drug', lazy='dynamic')
    interactions = db.relationship('DrugInteraction', foreign_keys='DrugInteraction.drug_id_1', backref='drug1', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name,
            'generic_name': self.generic_name, 'drug_type': self.drug_type,
            'category': self.category,
        }


class DrugInteraction(db.Model):
    __tablename__ = 'drug_interactions'
    id          = db.Column(db.Integer, primary_key=True)
    drug_id_1   = db.Column(db.Integer, db.ForeignKey('drugs.id', ondelete='CASCADE'), nullable=False)
    drug_id_2   = db.Column(db.Integer, db.ForeignKey('drugs.id', ondelete='CASCADE'), nullable=False)
    severity    = db.Column(db.Enum('mild','moderate','severe','contraindicated'), default='moderate')
    description = db.Column(db.Text)
    drug2       = db.relationship('Drug', foreign_keys=[drug_id_2])


class DrugInventory(db.Model):
    __tablename__ = 'drug_inventory'
    id               = db.Column(db.Integer, primary_key=True)
    drug_id          = db.Column(db.Integer, db.ForeignKey('drugs.id', ondelete='CASCADE'), nullable=False)
    batch_number     = db.Column(db.String(50))
    quantity         = db.Column(db.Integer, default=0)
    unit_cost        = db.Column(db.Numeric(10,2), default=0.00)
    selling_price    = db.Column(db.Numeric(10,2), default=0.00)
    expiry_date      = db.Column(db.Date)
    manufacture_date = db.Column(db.Date)
    reorder_level    = db.Column(db.Integer, default=10)
    location         = db.Column(db.String(50))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level

    @property
    def is_expired(self):
        if self.expiry_date:
            return self.expiry_date < datetime.utcnow().date()
        return False


class Prescription(db.Model):
    __tablename__ = 'prescriptions'
    id              = db.Column(db.Integer, primary_key=True)
    prescription_no = db.Column(db.String(30), unique=True)
    visit_id        = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False)
    patient_id      = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id       = db.Column(db.Integer, db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    notes           = db.Column(db.Text)
    status          = db.Column(db.Enum('active','dispensed','cancelled','partial'), default='active')
    dispensed_by    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    dispensed_at    = db.Column(db.DateTime)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    items  = db.relationship('PrescriptionItem', backref='prescription', lazy='dynamic')
    doctor = db.relationship('Doctor', backref='prescriptions')


class PrescriptionItem(db.Model):
    __tablename__ = 'prescription_items'
    id              = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id', ondelete='CASCADE'), nullable=False)
    drug_id         = db.Column(db.Integer, db.ForeignKey('drugs.id', ondelete='CASCADE'), nullable=False)
    dosage          = db.Column(db.String(50))
    frequency       = db.Column(db.String(80))
    duration        = db.Column(db.String(50))
    quantity        = db.Column(db.Integer, default=1)
    instructions    = db.Column(db.Text)
    is_dispensed    = db.Column(db.Boolean, default=False)
    drug            = db.relationship('Drug')


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(150), nullable=False)
    contact_name = db.Column(db.String(100))
    phone        = db.Column(db.String(20))
    email        = db.Column(db.String(120))
    address      = db.Column(db.Text)
    gst_number   = db.Column(db.String(30))
    is_active    = db.Column(db.Boolean, default=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
