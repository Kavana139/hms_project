"""
MediCore HMS — OT Status Socket Events
"""
from flask_socketio import emit


def register_events(socketio):

    @socketio.on('request_ot_status')
    def on_ot_status():
        from app.models.clinical import OTRoom, OTSchedule
        # Simple placeholder — will be expanded in OT module
        emit('ot_status_update', {'rooms': []})


def broadcast_ot_update(socketio, room_id, status):
    socketio.emit('ot_changed', {
        'room_id': room_id,
        'status':  status,
    }, broadcast=True)
