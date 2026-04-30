"""
email_service.py — Fixed version
Location: backend/app/services/email_service.py

FIX: Removed recursive self-call `await send_appointment_emails(data)`
     that was at the top of the function body, causing infinite recursion.

Environment variables (.env):
    EMAIL_HOST      = smtp.gmail.com
    EMAIL_PORT      = 587
    EMAIL_USER      = your-gmail@gmail.com
    EMAIL_PASSWORD  = your-16-char-app-password
    EMAIL_FROM_NAME = Smart Health Assistant

Gmail: Account → Security → 2-FA on → App Passwords → generate one → use here.
"""

import asyncio
import logging
import os
import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)

EMAIL_HOST      = os.getenv("EMAIL_HOST",      "smtp.gmail.com")
EMAIL_PORT      = int(os.getenv("EMAIL_PORT",  "587"))
EMAIL_USER      = os.getenv("EMAIL_USER",      "")
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD",  "")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Smart Health Assistant")
EMAIL_ENABLED   = bool(EMAIL_USER and EMAIL_PASSWORD)


@dataclass
class AppointmentEmailData:
    patient_name:          str
    patient_email:         str
    doctor_name:           str
    doctor_email:          Optional[str]
    doctor_phone:          str
    doctor_specialization: str
    clinic_name:           str
    clinic_address:        Optional[str]
    clinic_phone:          Optional[str]
    appointment_date:      str
    appointment_time:      str
    confirmation_code:     str
    consultation_mode:     str
    reason_for_visit:      str
    notes:                 Optional[str] = None


def _mode_label(mode: str) -> str:
    return {"in_person": "In-Person Visit", "online": "Online / Video",
            "phone": "Phone Consultation"}.get(mode, mode)


def _send_smtp(to_address: str, subject: str, html_body: str, text_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{EMAIL_FROM_NAME} <{EMAIL_USER}>"
    msg["To"]      = to_address
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html",  "utf-8"))
    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, to_address, msg.as_string())


def _patient_html(d: AppointmentEmailData) -> str:
    notes_row   = f"<tr><td><b>Notes</b></td><td>{d.notes}</td></tr>" if d.notes else ""
    clinic_addr = d.clinic_address or "—"
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/>
<title>Appointment Confirmed</title></head>
<body style="margin:0;padding:0;background:#f4f7fb;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7fb;padding:32px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.08);">
<tr><td style="background:linear-gradient(135deg,#1a73e8,#0d47a1);padding:36px 40px;text-align:center;">
  <h1 style="margin:0;color:#fff;font-size:26px;font-weight:700;">✅ Appointment Confirmed</h1>
  <p style="margin:8px 0 0;color:#c8e0ff;font-size:14px;">Smart Health Assistant</p>
</td></tr>
<tr><td style="padding:32px 40px 8px;">
  <p style="margin:0;font-size:16px;color:#333;">Dear <b>{d.patient_name}</b>,</p>
  <p style="margin:12px 0 0;font-size:15px;color:#555;line-height:1.6;">Your appointment has been <b>successfully booked</b>.</p>
</td></tr>
<tr><td style="padding:20px 40px;">
  <div style="background:#e8f4fd;border:2px dashed #1a73e8;border-radius:8px;padding:18px;text-align:center;">
    <p style="margin:0;font-size:13px;color:#666;text-transform:uppercase;letter-spacing:1px;">Confirmation Code</p>
    <p style="margin:8px 0 0;font-size:28px;font-weight:800;color:#1a73e8;letter-spacing:4px;">{d.confirmation_code}</p>
  </div>
</td></tr>
<tr><td style="padding:0 40px 24px;">
  <table width="100%" cellpadding="10" cellspacing="0" style="border-collapse:collapse;font-size:14px;">
    <tr style="background:#f8f9fa;"><td style="width:40%;color:#888;font-weight:600;border-bottom:1px solid #eee;">📅 Date</td><td style="color:#333;font-weight:600;border-bottom:1px solid #eee;">{d.appointment_date}</td></tr>
    <tr><td style="color:#888;font-weight:600;border-bottom:1px solid #eee;">🕐 Time</td><td style="color:#333;border-bottom:1px solid #eee;">{d.appointment_time}</td></tr>
    <tr style="background:#f8f9fa;"><td style="color:#888;font-weight:600;border-bottom:1px solid #eee;">👨‍⚕️ Doctor</td><td style="color:#333;border-bottom:1px solid #eee;">{d.doctor_name}<br/><span style="color:#888;font-size:12px;">{d.doctor_specialization}</span></td></tr>
    <tr><td style="color:#888;font-weight:600;border-bottom:1px solid #eee;">📞 Doctor Phone</td><td style="color:#333;border-bottom:1px solid #eee;">{d.doctor_phone}</td></tr>
    <tr style="background:#f8f9fa;"><td style="color:#888;font-weight:600;border-bottom:1px solid #eee;">🏥 Clinic</td><td style="color:#333;border-bottom:1px solid #eee;">{d.clinic_name}<br/><span style="color:#888;font-size:12px;">{clinic_addr}</span></td></tr>
    <tr><td style="color:#888;font-weight:600;border-bottom:1px solid #eee;">📋 Mode</td><td style="color:#333;border-bottom:1px solid #eee;">{_mode_label(d.consultation_mode)}</td></tr>
    <tr style="background:#f8f9fa;"><td style="color:#888;font-weight:600;border-bottom:1px solid #eee;">💬 Reason</td><td style="color:#333;border-bottom:1px solid #eee;">{d.reason_for_visit}</td></tr>
    {notes_row}
  </table>
</td></tr>
<tr><td style="padding:0 40px 24px;">
  <div style="background:#fff8e1;border-left:4px solid #f59e0b;border-radius:4px;padding:16px;">
    <p style="margin:0 0 8px;font-weight:700;color:#92400e;">⚠️ Important Reminders</p>
    <ul style="margin:0;padding-left:20px;color:#78350f;font-size:14px;line-height:1.8;">
      <li>Arrive <b>10 minutes before</b> your appointment.</li>
      <li>Keep your <b>Confirmation Code</b> handy.</li>
      <li>Cancel at least <b>24 hours in advance</b> if needed.</li>
      <li>This platform provides <b>educational guidance only</b> — not a medical diagnosis.</li>
    </ul>
  </div>
</td></tr>
<tr><td style="background:#f8f9fa;padding:24px 40px;text-align:center;border-top:1px solid #eee;">
  <p style="margin:0;font-size:13px;color:#999;">Sent by <b>Smart Health Assistant</b>. Do not reply.</p>
</td></tr>
</table></td></tr></table></body></html>"""


def _patient_text(d: AppointmentEmailData) -> str:
    return f"""Smart Health Assistant — Appointment Confirmation
Confirmation Code : {d.confirmation_code}
Date              : {d.appointment_date}
Time              : {d.appointment_time}
Doctor            : {d.doctor_name} ({d.doctor_specialization})
Clinic            : {d.clinic_name} | {d.clinic_address or '—'}
Mode              : {_mode_label(d.consultation_mode)}
Reason            : {d.reason_for_visit}
{f'Notes             : {d.notes}' if d.notes else ''}
Arrive 10 min early. Cancel 24 hrs in advance if needed.""".strip()


def _doctor_html(d: AppointmentEmailData) -> str:
    notes_row = f"<tr><td><b>Patient Notes</b></td><td>{d.notes}</td></tr>" if d.notes else ""
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/>
<title>New Appointment</title></head>
<body style="margin:0;padding:0;background:#f4f7fb;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7fb;padding:32px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.08);">
<tr><td style="background:linear-gradient(135deg,#059669,#065f46);padding:36px 40px;text-align:center;">
  <h1 style="margin:0;color:#fff;font-size:26px;font-weight:700;">📋 New Appointment Booked</h1>
  <p style="margin:8px 0 0;color:#a7f3d0;font-size:14px;">Smart Health Assistant — Doctor Notification</p>
</td></tr>
<tr><td style="padding:32px 40px 8px;">
  <p style="margin:0;font-size:16px;color:#333;">Dear <b>Dr. {d.doctor_name}</b>,</p>
  <p style="margin:12px 0 0;font-size:15px;color:#555;">A new appointment has been scheduled via <b>Smart Health Assistant</b>.</p>
</td></tr>
<tr><td style="padding:20px 40px 28px;">
  <table width="100%" cellpadding="10" cellspacing="0" style="border-collapse:collapse;font-size:14px;">
    <tr style="background:#ecfdf5;"><td colspan="2" style="color:#065f46;font-weight:700;border-bottom:1px solid #d1fae5;">Patient Information</td></tr>
    <tr><td style="color:#888;font-weight:600;border-bottom:1px solid #eee;width:40%;">👤 Name</td><td style="color:#333;font-weight:600;border-bottom:1px solid #eee;">{d.patient_name}</td></tr>
    <tr style="background:#f8f9fa;"><td style="color:#888;font-weight:600;border-bottom:1px solid #eee;">📧 Email</td><td style="color:#333;border-bottom:1px solid #eee;">{d.patient_email}</td></tr>
    <tr><td style="color:#888;font-weight:600;border-bottom:1px solid #eee;">💬 Reason</td><td style="color:#333;border-bottom:1px solid #eee;">{d.reason_for_visit}</td></tr>
    {notes_row}
    <tr style="background:#ecfdf5;"><td colspan="2" style="color:#065f46;font-weight:700;border-bottom:1px solid #d1fae5;padding-top:16px;">Appointment Details</td></tr>
    <tr><td style="color:#888;font-weight:600;border-bottom:1px solid #eee;">📅 Date</td><td style="color:#333;font-weight:600;border-bottom:1px solid #eee;">{d.appointment_date}</td></tr>
    <tr style="background:#f8f9fa;"><td style="color:#888;font-weight:600;border-bottom:1px solid #eee;">🕐 Time</td><td style="color:#333;border-bottom:1px solid #eee;">{d.appointment_time}</td></tr>
    <tr><td style="color:#888;font-weight:600;border-bottom:1px solid #eee;">📋 Mode</td><td style="color:#333;border-bottom:1px solid #eee;">{_mode_label(d.consultation_mode)}</td></tr>
    <tr style="background:#f8f9fa;"><td style="color:#888;font-weight:600;">🔑 Code</td><td style="color:#059669;font-weight:700;font-size:16px;">{d.confirmation_code}</td></tr>
  </table>
</td></tr>
<tr><td style="background:#f8f9fa;padding:24px 40px;text-align:center;border-top:1px solid #eee;">
  <p style="margin:0;font-size:13px;color:#999;">Sent by <b>Smart Health Assistant</b>. Do not reply.</p>
</td></tr>
</table></td></tr></table></body></html>"""


def _doctor_text(d: AppointmentEmailData) -> str:
    return f"""Smart Health Assistant — New Appointment Notification
Patient : {d.patient_name} | {d.patient_email}
Reason  : {d.reason_for_visit}
{f'Notes   : {d.notes}' if d.notes else ''}
Date    : {d.appointment_date}  Time: {d.appointment_time}
Mode    : {_mode_label(d.consultation_mode)}
Code    : {d.confirmation_code}""".strip()


# ── Public API ────────────────────────────────────────────────────────────────
async def send_appointment_emails(data: AppointmentEmailData) -> dict:
    """
    Send patient confirmation + doctor notification emails.
    Never raises — email failure must not crash the booking response.
    """
    # NOTE: No recursive call here (that was the bug in the previous version)

    if not EMAIL_ENABLED:
        logger.warning(
            "EMAIL_ENABLED=False — set EMAIL_USER + EMAIL_PASSWORD in .env\n"
            "  Would have emailed: patient=%s  doctor=%s",
            data.patient_email, data.doctor_email or "none"
        )
        return {"patient": False, "doctor": False}

    loop   = asyncio.get_event_loop()
    result = {"patient": False, "doctor": False}

    # Patient
    try:
        await loop.run_in_executor(
            None, _send_smtp,
            data.patient_email,
            f"✅ Appointment Confirmed — {data.confirmation_code}",
            _patient_html(data),
            _patient_text(data),
        )
        result["patient"] = True
        logger.info("📧 Patient email sent → %s", data.patient_email)
    except Exception as exc:
        logger.error("❌ Patient email FAILED → %s : %s", data.patient_email, exc)

    # Doctor
    if data.doctor_email:
        try:
            await loop.run_in_executor(
                None, _send_smtp,
                data.doctor_email,
                f"📋 New Appointment: {data.patient_name} on {data.appointment_date}",
                _doctor_html(data),
                _doctor_text(data),
            )
            result["doctor"] = True
            logger.info("📧 Doctor email sent → %s", data.doctor_email)
        except Exception as exc:
            logger.error("❌ Doctor email FAILED → %s : %s", data.doctor_email, exc)
    else:
        logger.info("ℹ️  No doctor email on record — skipped")
    print("EMAIL_ENABLED:", EMAIL_ENABLED)
    print("EMAIL_USER:", EMAIL_USER)

    return result