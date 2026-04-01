"""
MediCore HMS — Testing Configuration
"""
import os


class TestingConfig:
    TESTING             = True
    DEBUG               = False
    WTF_CSRF_ENABLED    = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SECRET_KEY          = 'test-secret-key-not-for-production'
    JWT_SECRET_KEY      = 'test-jwt-secret'
    RATELIMIT_ENABLED   = False
    RATELIMIT_STORAGE_URI = 'memory://'
    MAX_LOGIN_ATTEMPTS  = 5
    LOCKOUT_DURATION    = 900
    UPLOAD_FOLDER       = '/tmp/medicore_test_uploads'
    MAIL_SUPPRESS_SEND  = True
    SERVER_NAME         = None
