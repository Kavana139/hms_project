from app import db
from datetime import datetime


class Patient(db.Model):
    __tablename__ = 'patients'
    id                 = db.Column(db.Integer, primary_key=True)
    user_id            = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), unique=True)
    uhid               = db.Column(db.String(20), nullable=False, unique=True)
    first_name         = db.Column(db.String(80), nullable=False)
    last_name          = db.Column(db.String(80), nullable=False)
    date_of_birth      = db.Column(db.Date)
    gender             = db.Column(db.Enum('male','female','other'))
    blood_group        = db.Column(db.Enum('A+','A-','B+','B-','O+','O-','AB+','AB-','unknown'), default='unknown')
    phone              = db.Column(db.String(20))
    emergency_phone    = db.Column(db.String(20))
    email              = db.Column(db.String(120))
    address            = db.Column(db.Text)
    city               = db.Column(db.String(80))
    state              = db.Column(db.String(80))
    pincode            = db.Column(db.String(10))
    nationality        = db.Column(db.String(50), default='Indian')
    marital_status     = db.Column(db.Enum('single','married','divorced','widowed','other'))
    occupation         = db.Column(db.String(100))
    religion           = db.Column(db.String(50))
    photo              = db.Column(db.String(255))
    insurance_provider = db.Column(db.String(100))
    insurance_id       = db.Column(db.String(80))
    tpa_name           = db.Column(db.String(100))
    referred_by        = db.Column(db.String(100))
    registration_date  = db.Column(db.Date, default=datetime.utcnow)
    is_active          = db.Column(db.Boolean, default=True)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at         = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    allergies          = db.relationship('PatientAllergy', backref='patient', lazy='dynamic')
    chronic_conditions = db.relationship('PatientChronicCondition', backref='patient', lazy='dynamic')
    appointments       = db.relationship('Appointment', backref='patient', lazy='dynamic')
    visits             = db.relationship('Visit', backref='patient', lazy='dynamic')

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def age(self):
        if self.date_of_birth:
            today = datetime.utcnow().date()
            dob   = self.date_of_birth
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return None

    def to_dict(self):
        return {
            'id': self.id, 'uhid': self.uhid,
            'full_name': self.full_name, 'age': self.age,
            'gender': self.gender, 'blood_group': self.blood_group,
            'phone': self.phone, 'email': self.email,
        }

    def __repr__(self):
        return f'<Patient {self.uhid} - {self.full_name}>'


class PatientAllergy(db.Model):
    __tablename__ = 'patient_allergies'
    id         = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    allergen   = db.Column(db.String(100), nullable=False)
    reaction   = db.Column(db.String(255))
    severity   = db.Column(db.Enum('mild','moderate','severe'), default='moderate')
    noted_by   = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    noted_at   = db.Column(db.DateTime, default=datetime.utcnow)


class PatientChronicCondition(db.Model):
    __tablename__ = 'patient_chronic_conditions'
    id            = db.Column(db.Integer, primary_key=True)
    patient_id    = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    condition     = db.Column('condition', db.String(150), nullable=False)
    icd10_code    = db.Column(db.String(20))
    diagnosed_on  = db.Column(db.Date)
    notes         = db.Column(db.Text)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
