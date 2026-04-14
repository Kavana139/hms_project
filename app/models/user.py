from app import db
from flask_login import UserMixin
from datetime import datetime
import bcrypt


class Role(db.Model):
    __tablename__ = 'roles'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.String(255))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    users       = db.relationship('User', backref='role', lazy='dynamic')

    def __repr__(self):
        return f'<Role {self.name}>'


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id               = db.Column(db.Integer, primary_key=True)
    uhid             = db.Column(db.String(20), unique=True)
    username         = db.Column(db.String(80), nullable=False, unique=True)
    email            = db.Column(db.String(120), nullable=False, unique=True)
    phone            = db.Column(db.String(20))
    password_hash    = db.Column(db.String(255), nullable=False)
    role_id          = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    first_name       = db.Column(db.String(80))
    last_name        = db.Column(db.String(80))
    gender           = db.Column(db.Enum('male','female','other'))
    date_of_birth    = db.Column(db.Date)
    profile_photo    = db.Column(db.String(255))
    is_active        = db.Column(db.Boolean, default=True)
    is_verified      = db.Column(db.Boolean, default=False)
    two_fa_enabled   = db.Column(db.Boolean, default=False)
    two_fa_secret    = db.Column(db.String(64))
    login_attempts   = db.Column(db.Integer, default=0)
    locked_until     = db.Column(db.DateTime)
    last_login       = db.Column(db.DateTime)
    password_changed = db.Column(db.DateTime)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notifications    = db.relationship('Notification', backref='user', lazy='dynamic')
    audit_logs       = db.relationship('AuditLog', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
        self.password_changed = datetime.utcnow()

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    @property
    def full_name(self):
        return f'{self.first_name or ""} {self.last_name or ""}'.strip() or self.username

    @property
    def role_name(self):
        return self.role.name if self.role else None

    def is_admin(self):        return self.role.name == 'admin'
    def is_doctor(self):       return self.role.name == 'doctor'
    def is_receptionist(self): return self.role.name == 'receptionist'
    def is_pharmacist(self):   return self.role.name == 'pharmacist'
    def is_lab_tech(self):     return self.role.name == 'lab_tech'
    def is_patient_role(self): return self.role.name == 'patient'

    def is_locked(self):
        return bool(self.locked_until and self.locked_until > datetime.utcnow())

    def to_dict(self):
        return {
            'id': self.id, 'username': self.username, 'email': self.email,
            'phone': self.phone, 'full_name': self.full_name,
            'first_name': self.first_name, 'last_name': self.last_name,
            'role': self.role_name, 'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }

    def __repr__(self):
        return f'<User {self.username}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    action      = db.Column(db.String(100), nullable=False)
    module      = db.Column(db.String(50))
    description = db.Column(db.Text)
    ip_address  = db.Column(db.String(45))
    user_agent  = db.Column(db.String(255))
    old_value   = db.Column(db.JSON)
    new_value   = db.Column(db.JSON)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


class Session(db.Model):
    __tablename__ = 'sessions'
    id         = db.Column(db.String(128), primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)


class HospitalSetting(db.Model):
    __tablename__ = 'hospital_settings'
    id            = db.Column(db.Integer, primary_key=True)
    setting_key   = db.Column(db.String(100), nullable=False, unique=True)
    setting_value = db.Column(db.Text)
    setting_type  = db.Column(db.Enum('text','number','boolean','json'), default='text')
    description   = db.Column(db.String(255))
    updated_by    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get(key, default=None):
        s = HospitalSetting.query.filter_by(setting_key=key).first()
        return s.setting_value if s else default

    @staticmethod
    def set_value(key, value, updated_by=None):
        s = HospitalSetting.query.filter_by(setting_key=key).first()
        if s:
            s.setting_value = str(value)
            s.updated_by = updated_by
        else:
            db.session.add(HospitalSetting(setting_key=key, setting_value=str(value), updated_by=updated_by))
        db.session.commit()
