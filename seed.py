"""
MediCore HMS — Database Seed Script
Run ONCE after: flask db upgrade
Usage: python seed.py
"""
import os
os.environ.setdefault('FLASK_ENV', 'development')

from app import create_app, db
from app.models.user import Role, User, HospitalSetting
from app.models.doctor import Department

app = create_app('development')

with app.app_context():
    print("=" * 50)
    print("  MediCore HMS — Seeding Database")
    print("=" * 50)

    # ── 1. Roles ──────────────────────────────────────────
    roles = ['admin', 'doctor', 'receptionist', 'pharmacist', 'lab_tech', 'patient']
    for name in roles:
        if not Role.query.filter_by(name=name).first():
            db.session.add(Role(name=name, description=f'{name.title()} role'))
            print(f"  ✔ Role created: {name}")
        else:
            print(f"  - Role exists: {name}")
    db.session.commit()

    # ── 2. Admin user ─────────────────────────────────────
    admin_role = Role.query.filter_by(name='admin').first()
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username   = 'admin',
            email      = 'admin@medicore.local',
            phone      = '+91-9000000000',
            role_id    = admin_role.id,
            first_name = 'System',
            last_name  = 'Admin',
            is_active  = True,
            is_verified= True,
        )
        admin.set_password('Admin@1234')
        db.session.add(admin)
        db.session.commit()
        print("  ✔ Admin user created  →  admin / Admin@1234")
    else:
        print("  - Admin user exists")

    # ── 3. Departments ────────────────────────────────────
    departments = [
        ('General Medicine', 'GM'), ('Cardiology', 'CARD'),
        ('Orthopedics', 'ORTH'), ('Pediatrics', 'PED'),
        ('Gynecology', 'GYN'), ('Neurology', 'NEURO'),
        ('Dermatology', 'DERM'), ('ENT', 'ENT'),
        ('Ophthalmology', 'OPH'), ('Radiology', 'RAD'),
        ('Pathology', 'PATH'), ('Pharmacy', 'PHARM'),
    ]
    for name, code in departments:
        if not Department.query.filter_by(name=name).first():
            db.session.add(Department(name=name, code=code, is_active=True))
            print(f"  ✔ Department: {name}")
    db.session.commit()

    # ── 4. Hospital settings ──────────────────────────────
    settings = {
        'hospital_name':    'MediCore Hospital',
        'hospital_address': '123 Medical Lane, Healthcare City',
        'hospital_phone':   '+91-9876543210',
        'hospital_email':   'info@medicorehospital.com',
        'gst_number':       '27AABCU9603R1ZX',
        'uhid_prefix':      'MED',
        'razorpay_key_id':      '',
        'razorpay_key_secret':  '',
    }
    for key, val in settings.items():
        if not HospitalSetting.query.filter_by(setting_key=key).first():
            db.session.add(HospitalSetting(setting_key=key, setting_value=val))
    db.session.commit()
    print("  ✔ Hospital settings initialized")

    print("=" * 50)
    print("  ✅ Seed complete!")
    print("  Login: http://localhost:5000/auth/login")
    print("  User : admin  |  Pass: Admin@1234")
    print("=" * 50)
