from app import db
from datetime import datetime


class Department(db.Model):
    __tablename__ = 'departments'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    head_doctor = db.Column(db.Integer)
    floor       = db.Column(db.String(20))
    phone_ext   = db.Column(db.String(10))
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    doctors     = db.relationship('Doctor', backref='department', lazy='dynamic')

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'floor': self.floor, 'is_active': self.is_active}

    def __repr__(self):
        return f'<Department {self.name}>'


class Doctor(db.Model):
    __tablename__ = 'doctors'
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    department_id    = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'))
    employee_id      = db.Column(db.String(30), unique=True)
    specialization   = db.Column(db.String(150))
    qualification    = db.Column(db.String(255))
    experience_years = db.Column(db.Integer, default=0)
    registration_no  = db.Column(db.String(80))
    consultation_fee = db.Column(db.Numeric(10,2), default=0.00)
    bio              = db.Column(db.Text)
    rating           = db.Column(db.Numeric(3,1), default=0.0)
    signature_image  = db.Column(db.String(255))
    is_available     = db.Column(db.Boolean, default=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user      = db.relationship('User', backref='doctor_profile')
    schedules = db.relationship('DoctorSchedule', backref='doctor', lazy='dynamic')
    leaves    = db.relationship('DoctorLeave', backref='doctor', lazy='dynamic')

    @property
    def full_name(self):
        return f'Dr. {self.user.full_name}' if self.user else 'Unknown'

    def to_dict(self):
        return {
            'id': self.id, 'full_name': self.full_name,
            'specialization': self.specialization,
            'department': self.department.name if self.department else None,
            'consultation_fee': float(self.consultation_fee or 0),
            'is_available': self.is_available,
            'rating': float(self.rating or 0) if hasattr(self, 'rating') and self.rating is not None else 0.0,
        }

    def __repr__(self):
        return f'<Doctor {self.full_name}>'


class DoctorSchedule(db.Model):
    __tablename__ = 'doctor_schedules'
    id            = db.Column(db.Integer, primary_key=True)
    doctor_id     = db.Column(db.Integer, db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    day_of_week   = db.Column(db.Enum('monday','tuesday','wednesday','thursday','friday','saturday','sunday'))
    start_time    = db.Column(db.Time, nullable=False)
    end_time      = db.Column(db.Time, nullable=False)
    slot_duration = db.Column(db.Integer, default=15)
    max_patients  = db.Column(db.Integer, default=20)
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)


class DoctorLeave(db.Model):
    __tablename__ = 'doctor_leaves'
    id          = db.Column(db.Integer, primary_key=True)
    doctor_id   = db.Column(db.Integer, db.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    leave_date  = db.Column(db.Date, nullable=False)
    reason      = db.Column(db.String(255))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    status      = db.Column(db.Enum('pending','approved','rejected'), default='pending')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


class DoctorRating(db.Model):
    __tablename__ = 'doctor_ratings'
    id         = db.Column(db.Integer, primary_key=True)
    doctor_id  = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    rating     = db.Column(db.Integer, nullable=False)   # 1-5
    comment    = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    __table_args__ = (
        db.UniqueConstraint('doctor_id', 'patient_id', name='uq_doctor_patient_rating'),
    )
