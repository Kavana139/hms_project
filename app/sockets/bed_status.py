"""
MediCore HMS — Bed Status Socket Events
"""
from flask_socketio import emit


def register_events(socketio):

    @socketio.on('request_bed_status')
    def on_bed_status():
        from app.models.clinical import Bed, Ward
        wards = Ward.query.filter_by(is_active=True).all()
        data  = []
        for w in wards:
            beds = Bed.query.filter_by(ward_id=w.id, is_active=True).all()
            data.append({
                'ward_id':   w.id,
                'ward_name': w.name,
                'beds': [{'id': b.id, 'number': b.bed_number,
                          'status': b.status} for b in beds]
            })
        emit('bed_status_update', {'wards': data})


def broadcast_bed_update(socketio, bed_id, status):
    """Broadcast bed status change to all connected clients"""
    socketio.emit('bed_changed', {
        'bed_id': bed_id,
        'status': status,
    }, broadcast=True)
