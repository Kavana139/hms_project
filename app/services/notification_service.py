"""
MediCore HMS — Notification Service
Handles Email (SMTP), SMS (Twilio), WhatsApp (Twilio)
"""
import logging
from datetime import datetime
from flask import current_app
from app import db

logger = logging.getLogger(__name__)


# ── Email ─────────────────────────────────────────────────────

def send_email(to, subject, body, html_body=None):
    """Send email via SMTP"""
    try:
        from flask_mail import Message
        from app import mail
        msg = Message(
            subject    = subject,
            recipients = [to],
            body       = body,
            html       = html_body,
        )
        mail.send(msg)
        _log_notification(channel='email', recipient=to,
                          subject=subject, message=body, status='sent')
        return True
    except Exception as e:
        logger.error(f'Email failed to {to}: {e}')
        _log_notification(channel='email', recipient=to,
                          subject=subject, message=body,
                          status='failed', error=str(e))
        return False


# ── SMS ───────────────────────────────────────────────────────

def send_sms(to_phone, message):
    """Send SMS via Twilio"""
    try:
        from twilio.rest import Client
        sid    = current_app.config.get('TWILIO_ACCOUNT_SID')
        token  = current_app.config.get('TWILIO_AUTH_TOKEN')
        from_  = current_app.config.get('TWILIO_PHONE_NUMBER')
        if not all([sid, token, from_]):
            logger.warning('Twilio not configured')
            return False
        client = Client(sid, token)
        client.messages.create(body=message, from_=from_, to=to_phone)
        _log_notification(channel='sms', recipient=to_phone,
                          message=message, status='sent')
        return True
    except Exception as e:
        logger.error(f'SMS failed to {to_phone}: {e}')
        _log_notification(channel='sms', recipient=to_phone,
                          message=message, status='failed', error=str(e))
        return False


# ── WhatsApp ──────────────────────────────────────────────────

def send_whatsapp(to_phone, message):
    """Send WhatsApp message via Twilio"""
    try:
        from twilio.rest import Client
        sid    = current_app.config.get('TWILIO_ACCOUNT_SID')
        token  = current_app.config.get('TWILIO_AUTH_TOKEN')
        from_  = current_app.config.get('TWILIO_WHATSAPP_NUMBER',
                                         'whatsapp:+14155238886')
        if not all([sid, token]):
            logger.warning('WhatsApp (Twilio) not configured')
            return False
        to_wa  = f'whatsapp:{to_phone}' if not to_phone.startswith('whatsapp:') else to_phone
        client = Client(sid, token)
        client.messages.create(body=message, from_=from_, to=to_wa)
        _log_notification(channel='whatsapp', recipient=to_phone,
                          message=message, status='sent')
        return True
    except Exception as e:
        logger.error(f'WhatsApp failed to {to_phone}: {e}')
        _log_notification(channel='whatsapp', recipient=to_phone,
                          message=message, status='failed', error=str(e))
        return False


# ── Template Renderer ─────────────────────────────────────────

def render_template_str(template_body, variables):
    """Replace {{variable}} placeholders in template"""
    for key, value in variables.items():
        template_body = template_body.replace(f'{{{{{key}}}}}', str(value))
    return template_body


# ── Appointment Notifications ─────────────────────────────────

def notify_appointment_confirmed(appointment):
    """Send appointment confirmation to patient"""
    try:
        from app.models.patient import Patient
        from app.models.doctor import Doctor
        patient = Patient.query.get(appointment.patient_id)
        doctor  = Doctor.query.get(appointment.doctor_id)
        if not patient:
            return
        msg = (f'Dear {patient.full_name}, your appointment with '
               f'{doctor.full_name if doctor else "Doctor"} is confirmed on '
               f'{appointment.appointment_date.strftime("%d %b %Y")} at '
               f'{appointment.appointment_time.strftime("%H:%M")}. '
               f'Token: {appointment.token_number}. MediCore HMS')
        if patient.phone:
            send_sms(patient.phone, msg)
            send_whatsapp(patient.phone, msg)
        if patient.email:
            send_email(patient.email, 'Appointment Confirmed — MediCore HMS', msg)
    except Exception as e:
        logger.error(f'Appointment notification error: {e}')


def notify_appointment_reminder(appointment):
    """Send 24-hour reminder"""
    try:
        from app.models.patient import Patient
        from app.models.doctor import Doctor
        patient = Patient.query.get(appointment.patient_id)
        doctor  = Doctor.query.get(appointment.doctor_id)
        if not patient:
            return
        msg = (f'Reminder: Your appointment at MediCore Hospital is tomorrow '
               f'{appointment.appointment_date.strftime("%d %b %Y")} at '
               f'{appointment.appointment_time.strftime("%H:%M")} with '
               f'{doctor.full_name if doctor else "Doctor"}. '
               f'Please arrive 10 minutes early.')
        if patient.phone:
            send_sms(patient.phone, msg)
            send_whatsapp(patient.phone, msg)
        appointment.reminder_sent = True
        db.session.commit()
    except Exception as e:
        logger.error(f'Reminder error: {e}')


# ── Lab Notifications ─────────────────────────────────────────

def notify_lab_report_ready(lab_order):
    """Notify patient when lab report is ready"""
    try:
        from app.models.patient import Patient
        patient = Patient.query.get(lab_order.patient_id)
        if not patient:
            return
        msg = (f'Dear {patient.full_name}, your lab report '
               f'(Order: {lab_order.order_no}) is ready. '
               f'View it in your patient portal. MediCore HMS')
        if patient.phone:
            send_sms(patient.phone, msg)
        if patient.email:
            send_email(patient.email, 'Lab Report Ready — MediCore HMS', msg)
    except Exception as e:
        logger.error(f'Lab notification error: {e}')


# ── Invoice Notifications ─────────────────────────────────────

def notify_invoice_generated(invoice):
    """Notify patient about new invoice"""
    try:
        from app.models.patient import Patient
        patient = Patient.query.get(invoice.patient_id)
        if not patient:
            return
        msg = (f'Dear {patient.full_name}, your invoice '
               f'#{invoice.invoice_no} for '
               f'\u20b9{float(invoice.total_amount):.2f} has been generated. '
               f'MediCore HMS')
        if patient.phone:
            send_sms(patient.phone, msg)
        if patient.email:
            send_email(patient.email,
                       f'Invoice #{invoice.invoice_no} — MediCore HMS', msg)
    except Exception as e:
        logger.error(f'Invoice notification error: {e}')


# ── Appointment Reminder Scheduler ───────────────────────────

def schedule_reminders(app):
    """APScheduler job — runs every hour to send 24h reminders"""
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    scheduler = BackgroundScheduler()

    def send_pending_reminders():
        with app.app_context():
            from app.models.appointment import Appointment
            from datetime import date, timedelta
            tomorrow = date.today() + timedelta(days=1)
            appts = Appointment.query.filter_by(
                appointment_date=tomorrow,
                reminder_sent=False,
                status='confirmed'
            ).all()
            for appt in appts:
                notify_appointment_reminder(appt)
            if appts:
                logger.info(f'Sent {len(appts)} appointment reminders')

    scheduler.add_job(
        send_pending_reminders,
        trigger=IntervalTrigger(hours=1),
        id='appointment_reminders',
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


# ── Helper ────────────────────────────────────────────────────

def _log_notification(channel, recipient, message,
                      subject=None, status='sent', error=None,
                      recipient_id=None):
    try:
        from app.models.clinical import NotificationLog
        log = NotificationLog(
            recipient_id = recipient_id,
            channel      = channel,
            recipient    = recipient,
            subject      = subject,
            message      = message,
            status       = status,
            error        = error,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f'Failed to log notification: {e}')
