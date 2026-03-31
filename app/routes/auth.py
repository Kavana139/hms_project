"""
MediCore HMS — Auth Routes
"""
from flask import (Blueprint, render_template, request, redirect,
                   url_for, jsonify, session, current_app)
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta

from app import db, limiter
from app.services.auth_service import (
    authenticate_user, verify_2fa, enable_2fa,
    setup_2fa, get_dashboard_redirect, log_action
)
from app.models.user import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('20 per minute')
def login():
    if current_user.is_authenticated:
        return redirect(get_dashboard_redirect(current_user.role_name))

    if request.method == 'GET':
        return render_template('auth/login.html')

    data     = request.get_json() or request.form
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    remember = bool(data.get('remember', False))

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400

    user, error = authenticate_user(username, password, ip_address=request.remote_addr)

    if error:
        return jsonify({'success': False, 'message': error}), 401

    if user.two_fa_enabled:
        session['2fa_user_id']  = user.id
        session['2fa_remember'] = remember
        return jsonify({'success': True, 'requires_2fa': True,
                        'redirect': url_for('auth.verify_2fa_route')})

    _complete_login(user, remember)
    return jsonify({'success': True, 'requires_2fa': False,
                    'redirect': get_dashboard_redirect(user.role_name)})


@auth_bp.route('/2fa', methods=['GET', 'POST'])
def verify_2fa_route():
    user_id = session.get('2fa_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    if request.method == 'GET':
        return render_template('auth/2fa.html')

    data  = request.get_json() or request.form
    token = (data.get('token') or '').strip()
    user  = User.query.get(user_id)

    if not user:
        session.pop('2fa_user_id', None)
        return jsonify({'success': False, 'message': 'Session expired. Please login again.'}), 401

    if not verify_2fa(user, token):
        return jsonify({'success': False, 'message': 'Invalid code. Please try again.'}), 401

    remember = session.pop('2fa_remember', False)
    session.pop('2fa_user_id', None)
    _complete_login(user, remember)
    return jsonify({'success': True, 'redirect': get_dashboard_redirect(user.role_name)})


@auth_bp.route('/setup-2fa', methods=['GET', 'POST'])
@login_required
def setup_2fa_route():
    if request.method == 'GET':
        secret, qr_b64 = setup_2fa(current_user)
        return jsonify({'success': True, 'secret': secret, 'qr_code': qr_b64})
    data  = request.get_json() or request.form
    token = (data.get('token') or '').strip()
    if enable_2fa(current_user, token):
        return jsonify({'success': True, 'message': '2FA enabled successfully!'})
    return jsonify({'success': False, 'message': 'Invalid code. Please try again.'}), 400


@auth_bp.route('/logout')
@login_required
def logout():
    log_action(user_id=current_user.id, action='LOGOUT', module='auth',
               description='User logged out')
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit('5 per minute')
def forgot_password():
    if request.method == 'GET':
        return render_template('auth/forgot_password.html')

    data  = request.get_json() or request.form
    email = (data.get('email') or '').strip().lower()
    user  = User.query.filter_by(email=email).first()

    if user and user.is_active:
        token     = _generate_reset_token(user)
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        try:
            from app.services.notification_service import send_email
            send_email(to=user.email,
                       subject='Reset your MediCore HMS password',
                       body=f'Dear {user.full_name},\n\nReset link:\n{reset_url}\n\nExpires in 1 hour.\n\nMediCore HMS')
        except Exception:
            pass
        log_action(user_id=user.id, action='PASSWORD_RESET_REQUESTED', module='auth',
                   description=f'Reset requested for {email}')

    return jsonify({'success': True, 'message': 'If that email exists, a reset link has been sent.'})


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = _verify_reset_token(token)
    if not user:
        return render_template('auth/login.html', error='Invalid or expired reset link.')

    if request.method == 'GET':
        return render_template('auth/reset_password.html', token=token)

    data         = request.get_json() or request.form
    new_password = data.get('password') or ''
    confirm      = data.get('confirm_password') or ''

    if len(new_password) < 8:
        return jsonify({'success': False, 'message': 'Password must be at least 8 characters.'}), 400
    if new_password != confirm:
        return jsonify({'success': False, 'message': 'Passwords do not match.'}), 400

    user.set_password(new_password)
    user.login_attempts = 0
    user.locked_until   = None
    db.session.commit()
    log_action(user_id=user.id, action='PASSWORD_RESET', module='auth',
               description='Password reset successfully')
    return jsonify({'success': True, 'message': 'Password reset! Please login.',
                    'redirect': url_for('auth.login')})


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    data         = request.get_json() or request.form
    old_password = data.get('old_password') or ''
    new_password = data.get('new_password') or ''
    confirm      = data.get('confirm_password') or ''

    if not current_user.check_password(old_password):
        return jsonify({'success': False, 'message': 'Current password is incorrect.'}), 400
    if len(new_password) < 8:
        return jsonify({'success': False, 'message': 'New password must be at least 8 characters.'}), 400
    if new_password != confirm:
        return jsonify({'success': False, 'message': 'Passwords do not match.'}), 400

    current_user.set_password(new_password)
    db.session.commit()
    log_action(user_id=current_user.id, action='PASSWORD_CHANGED', module='auth',
               description='Password changed by user')
    return jsonify({'success': True, 'message': 'Password changed successfully!'})


@auth_bp.route('/me')
@login_required
def me():
    return jsonify({'success': True, 'user': current_user.to_dict()})


# ── Helpers ───────────────────────────────────────────────────

def _complete_login(user, remember=False):
    login_user(user, remember=remember,
               duration=timedelta(hours=24 if remember else 8))
    user.last_login = datetime.utcnow()
    db.session.commit()


def _generate_reset_token(user):
    from itsdangerous import URLSafeTimedSerializer
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps(user.email, salt='password-reset')


def _verify_reset_token(token, max_age=3600):
    from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = s.loads(token, salt='password-reset', max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None
    return User.query.filter_by(email=email).first()
