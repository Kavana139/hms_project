"""
MediCore HMS — Notifications API Routes
"""
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.clinical import Notification, NotificationLog
import os

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/api/all')
@login_required
def api_all():
    page    = int(request.args.get('page', 1))
    per_pg  = 20
    notifs  = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc())\
        .offset((page-1)*per_pg).limit(per_pg).all()
    unread  = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({
        'success': True,
        'notifications': [n.to_dict() for n in notifs],
        'unread_count': unread,
    })


@notifications_bp.route('/api/unread-count')
@login_required
def unread_count():
    count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False).count()
    return jsonify({'success': True, 'count': count})


@notifications_bp.route('/api/mark-read', methods=['POST'])
@login_required
def mark_read():
    data = request.get_json() or {}
    notif_id = data.get('id')
    if notif_id:
        notif = Notification.query.filter_by(
            id=notif_id, user_id=current_user.id).first()
        if notif:
            notif.is_read = True
            notif.read_at = datetime.utcnow()
    else:
        Notification.query.filter_by(
            user_id=current_user.id, is_read=False
        ).update({'is_read': True, 'read_at': datetime.utcnow()})
    db.session.commit()
    return jsonify({'success': True})


@notifications_bp.route('/api/delete/<int:notif_id>', methods=['DELETE'])
@login_required
def delete_notification(notif_id):
    notif = Notification.query.filter_by(
        id=notif_id, user_id=current_user.id).first_or_404()
    db.session.delete(notif)
    db.session.commit()
    return jsonify({'success': True})


@notifications_bp.route('/api/test', methods=['POST'])
@login_required
def test_notification():
    """Test Socket.IO notification delivery"""
    from app import socketio
    from app.sockets.notifications import send_notification
    send_notification(
        socketio     = socketio,
        user_id      = current_user.id,
        title        = 'Test Notification',
        message      = 'Socket.IO is working correctly!',
        notif_type   = 'success',
        module       = 'system',
    )
    return jsonify({'success': True, 'message': 'Test notification sent!'})


# ── PWA Routes ────────────────────────────────────────────────

@notifications_bp.route('/manifest.json')
def manifest():
    return send_from_directory(
        os.path.join(current_app.root_path, 'static'),
        'manifest.json',
        mimetype='application/manifest+json'
    )


@notifications_bp.route('/sw.js')
def service_worker():
    return send_from_directory(
        os.path.join(current_app.root_path, 'static'),
        'sw.js',
        mimetype='application/javascript',
        max_age=0
    )
