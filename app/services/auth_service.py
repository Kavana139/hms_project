"""
MediCore HMS — Auth Service
Handles login, 2FA, credential generation, audit logging
"""
import secrets
import string
import pyotp
import qrcode
import io, base64
from datetime import datetime, timedelta
from flask import current_app, request
from app import db
from app.models.user import User, AuditLog, Role
from app.models.patient import Patient


def generate_uhid():
    """Generate unique UHID like MED-20240001"""
    from app.models.user import HospitalSetting
    prefix = HospitalSetting.get('uhid_prefix', 'MED')
    year   = datetime.utcnow().year
    count  = Patient.query.count() + 1
    return f'{prefix}-{year}{count:04d}'


def generate_password(length=10):
    """Generate a strong alphanumeric password — no special chars to avoid URL encoding issues"""
    chars = string.ascii_letters + string.digits  # safe: no %, $, @, # which break DATABASE_URL
    while True:
        pwd = ''.join(secrets.choice(chars) for _ in range(length))
        # Only require upper + lower + digit — no special chars
        if (any(c.isupper() for c in pwd) and
            any(c.islower() for c in pwd) and
            any(c.isdigit() for c in pwd)):
            return pwd


def generate_username(first_name, last_name, role_name):
    """Generate username like dr.sharma or rec.patel"""
    prefixes = {
        'doctor': 'dr', 'receptionist': 'rec',
        'pharmacist': 'ph', 'lab_tech': 'lab',
        'admin': 'admin', 'patient': 'pt',
    }
    prefix = prefixes.get(role_name, 'user')
    base   = f'{prefix}.{(last_name or first_name or "user").lower()}'
    base   = ''.join(c for c in base if c.isalnum() or c == '.')

    username = base
    counter  = 1
    while User.query.filter_by(username=username).first():
        username = f'{base}{counter}'
        counter += 1
    return username


def create_user(first_name, last_name, email, phone, role_name,
                gender=None, dob=None, password=None, created_by=None):
    """
    Create a new user with auto-generated credentials.
    Returns (user, plain_password) tuple.
    """
    role = Role.query.filter_by(name=role_name).first()
    if not role:
        raise ValueError(f'Role {role_name} not found')

    if User.query.filter_by(email=email).first():
        raise ValueError('Email already registered')

    plain_password = password or generate_password()
    username       = generate_username(first_name, last_name, role_name)

    user = User(
        username      = username,
        email         = email,
        phone         = phone,
        role_id       = role.id,
        first_name    = first_name,
        last_name     = last_name,
        gender        = gender,
        date_of_birth = dob,
        is_active     = True,
        is_verified   = True,
    )
    user.set_password(plain_password)
    db.session.add(user)
    db.session.flush()

    log_action(
        user_id     = created_by,
        action      = 'CREATE_USER',
        module      = 'auth',
        description = f'Created user {username} with role {role_name}',
        new_value   = {'username': username, 'email': email, 'role': role_name},
    )

    db.session.commit()
    return user, plain_password


def authenticate_user(username_or_email, password, ip_address=None):
    """
    Authenticate a user. Returns (user, error_message).
    Handles lockout after MAX_LOGIN_ATTEMPTS.
    """
    max_attempts = current_app.config.get('MAX_LOGIN_ATTEMPTS', 5)
    lockout_secs = current_app.config.get('LOCKOUT_DURATION', 900)

    user = (User.query.filter_by(username=username_or_email).first() or
            User.query.filter_by(email=username_or_email).first())

    if not user:
        return None, 'Invalid username or password'

    if not user.is_active:
        return None, 'Your account has been deactivated. Contact admin.'

    if user.is_locked():
        remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
        return None, f'Account locked. Try again in {remaining} minutes.'

    if not user.check_password(password):
        user.login_attempts = (user.login_attempts or 0) + 1
        if user.login_attempts >= max_attempts:
            user.locked_until = datetime.utcnow() + timedelta(seconds=lockout_secs)
            log_action(user_id=user.id, action='ACCOUNT_LOCKED', module='auth',
                      description=f'Account locked after {max_attempts} failed attempts',
                      ip_address=ip_address)
        db.session.commit()
        remaining = max_attempts - user.login_attempts
        if remaining > 0:
            return None, f'Invalid password. {remaining} attempts remaining.'
        return None, 'Account locked due to too many failed attempts.'

    # Success
    user.login_attempts = 0
    user.locked_until   = None
    user.last_login     = datetime.utcnow()
    db.session.commit()

    log_action(user_id=user.id, action='LOGIN', module='auth',
              description='Successful login', ip_address=ip_address)

    return user, None


def setup_2fa(user):
    """Generate 2FA secret and QR code for a user"""
    secret = pyotp.random_base32()
    user.two_fa_secret  = secret
    user.two_fa_enabled = False  # not enabled until verified
    db.session.commit()

    hospital_name = current_app.config.get('HOSPITAL_NAME', 'MediCore HMS')
    totp = pyotp.TOTP(secret)
    uri  = totp.provisioning_uri(name=user.email, issuer_name=hospital_name)

    # Generate QR code as base64
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img    = qr.make_image(fill_color='black', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_b64 = base64.b64encode(buffer.getvalue()).decode()

    return secret, qr_b64


def verify_2fa(user, token):
    """Verify a TOTP token"""
    if not user.two_fa_secret:
        return False
    totp = pyotp.TOTP(user.two_fa_secret)
    return totp.verify(token, valid_window=1)


def enable_2fa(user, token):
    """Enable 2FA after verifying setup token"""
    if verify_2fa(user, token):
        user.two_fa_enabled = True
        db.session.commit()
        log_action(user_id=user.id, action='ENABLE_2FA', module='auth',
                  description='Two-factor authentication enabled')
        return True
    return False


def disable_2fa(user, token):
    """Disable 2FA"""
    if verify_2fa(user, token):
        user.two_fa_enabled = False
        user.two_fa_secret  = None
        db.session.commit()
        log_action(user_id=user.id, action='DISABLE_2FA', module='auth',
                  description='Two-factor authentication disabled')
        return True
    return False


def get_dashboard_redirect(role_name):
    """Return the correct dashboard URL for a role"""
    redirects = {
        'admin':        '/admin/dashboard',
        'doctor':       '/doctor/dashboard',
        'receptionist': '/receptionist/dashboard',
        'pharmacist':   '/pharmacy/dashboard',
        'lab_tech':     '/lab/dashboard',
        'patient':      '/patient/dashboard',
    }
    return redirects.get(role_name, '/')


def log_action(user_id=None, action='', module='', description='',
               ip_address=None, old_value=None, new_value=None):
    """Write to audit log"""
    try:
        if ip_address is None:
            try:
                ip_address = request.remote_addr
            except RuntimeError:
                ip_address = None
        log = AuditLog(
            user_id     = user_id,
            action      = action,
            module      = module,
            description = description,
            ip_address  = ip_address,
            old_value   = old_value,
            new_value   = new_value,
        )
        db.session.add(log)
    except Exception:
        pass  # Never let audit logging break the main flow
