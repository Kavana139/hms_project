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
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.doctor import doctor_bp
    from app.routes.receptionist import receptionist_bp
    from app.routes.pharmacy import pharmacy_bp
    from app.routes.lab import lab_bp
    #from app.routes.patient import patient_bp
    from app.routes.billing import billing_bp
    from app.routes.ward import ward_bp
    from app.routes.ot import ot_bp
    from app.routes.inventory import inventory_bp
    from app.routes.emergency import emergency_bp
    from app.routes.bloodbank import bloodbank_bp
    from app.routes.notifications import notifications_bp
    from app.routes.calendar import calendar_bp
    from app.routes.reports import reports_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(doctor_bp, url_prefix='/doctor')
    app.register_blueprint(receptionist_bp, url_prefix='/receptionist')
    app.register_blueprint(pharmacy_bp, url_prefix='/pharmacy')
    app.register_blueprint(lab_bp, url_prefix='/lab')
    #app.register_blueprint(patient_bp, url_prefix='/patient')
    app.register_blueprint(billing_bp, url_prefix='/billing')
    app.register_blueprint(ward_bp, url_prefix='/ward')
    app.register_blueprint(ot_bp, url_prefix='/ot')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(emergency_bp, url_prefix='/emergency')
    app.register_blueprint(bloodbank_bp, url_prefix='/bloodbank')
    app.register_blueprint(notifications_bp, url_prefix='/notifications')
    app.register_blueprint(calendar_bp, url_prefix='/calendar')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(api_bp, url_prefix='/api')

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
