"""
MediCore HMS — Entry Point
Run with: python run.py
"""
import os
from app import create_app, socketio

app = create_app(os.environ.get('FLASK_ENV', 'development'))

# Root redirect
from flask import redirect, url_for
from flask_login import current_user

@app.route('/')
def index():
    if current_user.is_authenticated:
        redirects = {
            'admin':        '/admin/dashboard',
            'doctor':       '/doctor/dashboard',
            'receptionist': '/receptionist/dashboard',
            'pharmacist':   '/pharmacy/dashboard',
            'lab_tech':     '/lab/dashboard',
            'patient':      '/patient/dashboard',
        }
        return redirect(redirects.get(current_user.role_name, '/auth/login'))
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    print("=" * 60)
    print("  🏥  MediCore HMS — Starting Server")
    print("=" * 60)
    print(f"  Environment : {os.environ.get('FLASK_ENV', 'development')}")
    print(f"  URL         : http://localhost:5000")
    print(f"  Debug       : {app.config['DEBUG']}")
    print("=" * 60)
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=app.config['DEBUG'],
        use_reloader=True,
        log_output=True
    )
