import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ── Core ──────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY', 'medicore-dev-secret')
    DEBUG = False
    TESTING = False

    # ── Database ──────────────────────────────────────────
    # Build URL from parts to safely handle special chars in password
    @staticmethod
    def _build_db_url():
        from urllib.parse import quote_plus
        user = os.environ.get('DB_USERNAME', 'root')
        pwd  = os.environ.get('DB_PASSWORD', 'password')
        host = os.environ.get('DB_HOST', 'localhost')
        port = os.environ.get('DB_PORT', '3306')
        name = os.environ.get('DB_NAME', 'medicore_hms')
        return f"mysql+pymysql://{user}:{quote_plus(pwd)}@{host}:{port}/{name}"

    SQLALCHEMY_DATABASE_URI = _build_db_url.__func__()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'pool_size': 10,
        'max_overflow': 20,
    }

    # ── JWT ───────────────────────────────────────────────
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'medicore-jwt-secret')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        seconds=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 3600)))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        seconds=int(os.environ.get('JWT_REFRESH_TOKEN_EXPIRES', 604800)))
    JWT_TOKEN_LOCATION = ['cookies', 'headers']
    JWT_COOKIE_SECURE = False
    JWT_COOKIE_CSRF_PROTECT = True

    # ── Mail ──────────────────────────────────────────────
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER',
        'MediCore HMS <noreply@medicorehms.com>')

    # ── Twilio ────────────────────────────────────────────
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
    TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER',
        'whatsapp:+14155238886')

    # ── Razorpay ──────────────────────────────────────────
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')

    # ── Hospital ──────────────────────────────────────────
    HOSPITAL_NAME = os.environ.get('HOSPITAL_NAME', 'MediCore Hospital')
    HOSPITAL_ADDRESS = os.environ.get('HOSPITAL_ADDRESS', '123 Medical Lane')
    HOSPITAL_PHONE = os.environ.get('HOSPITAL_PHONE', '+91-9876543210')
    HOSPITAL_EMAIL = os.environ.get('HOSPITAL_EMAIL', 'info@medicorehospital.com')
    HOSPITAL_GST = os.environ.get('HOSPITAL_GST_NUMBER', '27AABCU9603R1ZX')
    HOSPITAL_LOGO = os.environ.get('HOSPITAL_LOGO', 'app/static/images/logo.png')

    # ── Files ─────────────────────────────────────────────
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'app/static/uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16777216))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}

    # ── Security ──────────────────────────────────────────
    MAX_LOGIN_ATTEMPTS = int(os.environ.get('MAX_LOGIN_ATTEMPTS', 5))
    # Rate limiter — use in-memory to avoid Redis dependency
    RATELIMIT_STORAGE_URI      = 'memory://'
    RATELIMIT_DEFAULT          = '200 per minute'
    RATELIMIT_HEADERS_ENABLED  = False
    LOCKOUT_DURATION = int(os.environ.get('LOCKOUT_DURATION', 900))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.environ.get('PERMANENT_SESSION_LIFETIME', 3600)))

    # ── Socket.IO ─────────────────────────────────────────
    SOCKETIO_ASYNC_MODE = 'eventlet'
    SOCKETIO_CORS_ALLOWED_ORIGINS = '*'

    # ── Pagination ────────────────────────────────────────
    ITEMS_PER_PAGE = 20


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    JWT_COOKIE_SECURE = True
    SQLALCHEMY_ECHO = False


class TestingConfig(Config):
    TESTING               = True
    DEBUG                 = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED      = False
    RATELIMIT_ENABLED     = False
    RATELIMIT_STORAGE_URI = 'memory://'
    MAIL_SUPPRESS_SEND    = True
    SERVER_NAME           = None


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
