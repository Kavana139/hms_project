"""
MediCore HMS — Application Factory
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_mail import Mail
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import config

# ── Extensions (created here, initialized in create_app) ──
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
socketio = SocketIO()
mail = Mail()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)


def create_app(config_name='default'):
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    # Load config
    app.config.from_object(config[config_name])

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    jwt.init_app(app)
    CORS(app)
    limiter.init_app(app)

    socketio.init_app(app,
        async_mode='eventlet',
        cors_allowed_origins='*',
        logger=False,
        engineio_logger=False)

    # Login manager settings
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # ── User loader ───────────────────────────────────────
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ── Register Blueprints ───────────────────────────────
    import traceback

    def safe_import(module_path, bp_name):
        try:
            import importlib
            m = importlib.import_module(module_path)
            return getattr(m, bp_name)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(
                f"Failed to import {bp_name} from {module_path}: {e}\n{traceback.format_exc()}")
            return None

    blueprints = [
        ('app.routes.auth',           'auth_bp',           '/auth'),
        ('app.routes.admin',          'admin_bp',          '/admin'),
        ('app.routes.doctor',         'doctor_bp',         '/doctor'),
        ('app.routes.receptionist',   'receptionist_bp',   '/receptionist'),
        ('app.routes.pharmacy',       'pharmacy_bp',       '/pharmacy'),
        ('app.routes.lab',            'lab_bp',            '/lab'),
        ('app.routes.patient',        'patient_bp',        '/patient'),
        ('app.routes.billing',        'billing_bp',        '/billing'),
        ('app.routes.ward',           'ward_bp',           '/ward'),
        ('app.routes.ot',             'ot_bp',             '/ot'),
        ('app.routes.inventory',      'inventory_bp',      '/inventory'),
        ('app.routes.emergency',      'emergency_bp',      '/emergency'),
        ('app.routes.bloodbank',      'bloodbank_bp',      '/bloodbank'),
        ('app.routes.notifications',  'notifications_bp',  '/notifications'),
        ('app.routes.calendar',       'calendar_bp',       '/calendar'),
        ('app.routes.reports',        'reports_bp',        '/reports'),
        ('app.routes.api',            'api_bp',            '/api'),
    ]
    for module_path, bp_name, prefix in blueprints:
        bp = safe_import(module_path, bp_name)
        if bp is not None:
            try:
                app.register_blueprint(bp, url_prefix=prefix)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to register {bp_name}: {e}")

    # ── Register SocketIO events ──────────────────────────
    from app.sockets import notifications, bed_status, ot_status
    notifications.register_events(socketio)
    bed_status.register_events(socketio)
    ot_status.register_events(socketio)

    # ── Shell context ─────────────────────────────────────
    @app.shell_context_processor
    def make_shell_context():
        return {'db': db, 'app': app}

    # ── Create upload folder ──────────────────────────────
    import os
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    return app

def create_root_redirect(app):
    """Add root redirect after app creation"""
    from flask import redirect, url_for
    from flask_login import current_user

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            redirects = {
                'admin': '/admin/dashboard',
                'doctor': '/doctor/dashboard',
                'receptionist': '/receptionist/dashboard',
                'pharmacist': '/pharmacy/dashboard',
                'lab_tech': '/lab/dashboard',
                'patient': '/patient/dashboard',
            }
            return redirect(redirects.get(current_user.role_name, '/auth/login'))
        return redirect(url_for('auth.login'))
