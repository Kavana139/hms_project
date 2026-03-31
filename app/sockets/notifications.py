"""
MediCore HMS — Socket.IO Notification Events
"""
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user


def register_events(socketio):

    @socketio.on('connect')
    def on_connect():
        if current_user.is_authenticated:
            join_room(f'user_{current_user.id}')
            join_room(f'role_{current_user.role_name}')
            emit('connected', {
                'user_id': current_user.id,
                'role':    current_user.role_name,
            })

    @socketio.on('disconnect')
    def on_disconnect():
        if current_user.is_authenticated:
            leave_room(f'user_{current_user.id}')
            leave_room(f'role_{current_user.role_name}')

    @socketio.on('ping')
    def on_ping():
        emit('pong', {})


def send_notification(socketio, user_id, title, message,
                      notif_type='info', module='', reference_id=None):
    from app import db
    from app.models.clinical import Notification
    from datetime import datetime
    notif = Notification(user_id=user_id, title=title, message=message,
                         notif_type=notif_type, module=module,
                         reference_id=reference_id)
    db.session.add(notif)
    db.session.commit()
    socketio.emit('notification', {
        'id': notif.id, 'title': title, 'message': message,
        'notif_type': notif_type, 'module': module,
        'created_at': datetime.utcnow().isoformat(),
    }, room=f'user_{user_id}')


def send_role_alert(socketio, role_name, title, message, notif_type='info'):
    socketio.emit('notification', {
        'title': title, 'message': message,
        'notif_type': notif_type,
    }, room=f'role_{role_name}')
