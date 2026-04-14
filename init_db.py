"""
MediCore HMS — One-shot DB initializer
Run this INSTEAD of flask db init/migrate/upgrade when starting fresh.
Usage: python init_db.py
"""
import os
os.environ.setdefault('FLASK_ENV', 'development')

from app import create_app, db

app = create_app('development')

with app.app_context():
    print("Creating all tables...")
    db.create_all()
    print("✔ Tables created")

# Now run seed
exec(open('seed.py').read())
