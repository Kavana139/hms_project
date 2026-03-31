from app import db
from datetime import datetime


class Appointment(db.Model):
    __tablename__ = 'appointments'
    id               = db.Column(db.Integer, primary_key=True)
    appointment_no   = db.Column(db.String(30), unique=True)
    patient_id       = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id        = db.Column(db.Integer, db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    department_id    = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'))
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    token_number     = db.Column(db.Integer)
    appt_type        = db.Column(db.Enum('new','follow_up','emergency','teleconsult'), default='new')
    status           = db.Column(db.Enum('scheduled','confirmed','checked_in','in_progress','completed','cancelled','no_show'), default='scheduled')
    reason           = db.Column(db.Text)
    notes            = db.Column(db.Text)
    booked_by        = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    cancel_reason    = db.Column(db.String(255))
    reminder_sent    = db.Column(db.Boolean, default=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    doctor     = db.relationship('Doctor', backref='appointments')
    department = db.relationship('Department', backref='appointments')

    def to_dict(self):
        return {
            'id': self.id,
            'appointment_no': self.appointment_no,
            'patient_id': self.patient_id,
            'doctor_id': self.doctor_id,
            'doctor_name': self.doctor.full_name if self.doctor else None,
            'appointment_date': self.appointment_date.isoformat() if self.appointment_date else None,
            'appointment_time': self.appointment_time.strftime('%H:%M') if self.appointment_time else None,
            'token_number': self.token_number,
            'appt_type': self.appt_type,
            'status': self.status,
        }

    def __repr__(self):
        return f'<Appointment {self.appointment_no}>'


class Visit(db.Model):
    __tablename__ = 'visits'
    id             = db.Column(db.Integer, primary_key=True)
    visit_no       = db.Column(db.String(30), unique=True)
    patient_id     = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    doctor_id      = db.Column(db.Integer, db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id', ondelete='SET NULL'))
    visit_type     = db.Column(db.Enum('opd','ipd','emergency','teleconsult'), default='opd')
    visit_date     = db.Column(db.DateTime, default=datetime.utcnow)
    chief_complaint= db.Column(db.Text)
    status         = db.Column(db.Enum('open','closed'), default='open')
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    doctor      = db.relationship('Doctor', backref='visits')
    soap_notes  = db.relationship('SOAPNote', backref='visit', lazy='dynamic')
    vitals      = db.relationship('Vital', backref='visit', lazy='dynamic')


class SOAPNote(db.Model):
    __tablename__ = 'soap_notes'
    id             = db.Column(db.Integer, primary_key=True)
    visit_id       = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False)
    subjective     = db.Column(db.Text)
    objective      = db.Column(db.Text)
    assessment     = db.Column(db.Text)
    plan           = db.Column(db.Text)
    icd10_code     = db.Column(db.String(20))
    icd10_desc     = db.Column(db.String(255))
    follow_up_days = db.Column(db.Integer)
    follow_up_date = db.Column(db.Date)
    written_by     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Vital(db.Model):
    __tablename__ = 'vitals'
    id               = db.Column(db.Integer, primary_key=True)
    patient_id       = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    visit_id         = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'))
    systolic_bp      = db.Column(db.Integer)
    diastolic_bp     = db.Column(db.Integer)
    pulse_rate       = db.Column(db.Integer)
    temperature      = db.Column(db.Numeric(4,1))
    temp_unit        = db.Column(db.Enum('C','F'), default='F')
    respiratory_rate = db.Column(db.Integer)
    spo2             = db.Column(db.Integer)
    weight_kg        = db.Column(db.Numeric(5,2))
    height_cm        = db.Column(db.Numeric(5,1))
    bmi              = db.Column(db.Numeric(4,1))
    blood_sugar      = db.Column(db.Numeric(6,1))
    sugar_type       = db.Column(db.Enum('fasting','random','pp'), default='random')
    notes            = db.Column(db.Text)
    recorded_by      = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    recorded_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'systolic_bp': self.systolic_bp, 'diastolic_bp': self.diastolic_bp,
            'pulse_rate': self.pulse_rate, 'temperature': float(self.temperature or 0),
            'spo2': self.spo2, 'weight_kg': float(self.weight_kg or 0),
            'height_cm': float(self.height_cm or 0), 'bmi': float(self.bmi or 0),
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None,
        }
