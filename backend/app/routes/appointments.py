"""
Appointment Booking API Routes
File: backend/app/routes/appointments.py
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import logging

from app.services.email_service import send_appointment_emails, AppointmentEmailData
from app.database import get_db, create_or_get_user
from app.models.models import Appointment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/appointments", tags=["Appointments"])

# ============================================================================
# REQUEST MODELS
# ============================================================================

class BookAppointmentRequest(BaseModel):
    user_id: str
    patient_name: str               # ← NEW
    patient_email: str              # ← NEW
    doctor_id: int
    slot_id: int
    appointment_date: str
    appointment_time: str
    reason_for_visit: str
    consultation_mode: str = "in_person"
    notes: Optional[str] = None

class CancelAppointmentRequest(BaseModel):
    user_id: str
    reason: str

class RescheduleAppointmentRequest(BaseModel):
    user_id: str
    new_slot_id: int = None
    new_date: str
    new_time: str
    reason: Optional[str] = None

# ============================================================================
# SAMPLE DATA
# ============================================================================

SAMPLE_DOCTORS = [
    {
        "id": 1,
        "name": "Dr. Rajesh Patel",
        "specialization": "General Practitioner",
        "experience_years": 12,
        "phone": "+91-9173784072",
        "email": "nensichavda7@gmail.com",
        "clinic_id": 1,
        "rating": 4.8,
        "total_reviews": 245,
        "bio": "Experienced GP with 12 years of practice",
        "is_available": True
    },
    {
        "id": 2,
        "name": "Dr. Priya Sharma",
        "specialization": "Pediatrics",
        "experience_years": 8,
        "phone": "+91-9876543211",
        "email": "priya@clinic.com",
        "clinic_id": 2,
        "rating": 4.9,
        "total_reviews": 189,
        "bio": "Child health specialist",
        "is_available": True
    },
    {
        "id": 3,
        "name": "Dr. Amit Verma",
        "specialization": "Cardiology",
        "experience_years": 15,
        "phone": "+91-9876543212",
        "email": "amit@clinic.com",
        "clinic_id": 3,
        "rating": 4.7,
        "total_reviews": 312,
        "bio": "Senior cardiologist",
        "is_available": True
    },
]

SAMPLE_CLINICS = [
    {
        "id": 1,
        "name": "City Medical Clinic",
        "address": "123 Medical Street, Ahmedabad",
        "city": "Ahmedabad",
        "phone": "+91-7654321098",
        "opening_time": "09:00",
        "closing_time": "21:00",
        "rating": 4.6,
        "distance_km": 2.3
    },
    {
        "id": 2,
        "name": "Apollo Healthcare Center",
        "address": "456 Hospital Road, Ahmedabad",
        "city": "Ahmedabad",
        "phone": "+91-7654321099",
        "opening_time": "08:00",
        "closing_time": "22:00",
        "rating": 4.8,
        "distance_km": 5.1
    },
]

APPOINTMENT_COUNTER = 500

# ============================================================================
# HELPERS
# ============================================================================

def generate_confirmation_code(appointment_id: int) -> str:
    date_part = datetime.now().strftime("%Y%m%d")
    return f"APT-{date_part}-{appointment_id}"

def get_clinic_by_doctor(doctor: dict) -> dict:
    clinic_id = doctor.get("clinic_id", 1)
    return next((c for c in SAMPLE_CLINICS if c["id"] == clinic_id), SAMPLE_CLINICS[0])

def generate_appointment_slots(doctor_id: int, days_ahead: int = 30):
    slots = []
    slot_id = 1000 + doctor_id * 100

    for day in range(1, days_ahead + 1):
        slot_date = datetime.now() + timedelta(days=day)
        if slot_date.weekday() >= 5:
            continue

        for hour in range(9, 12):
            slots.append({
                "id": slot_id,
                "date": slot_date.strftime("%Y-%m-%d"),
                "start_time": f"{hour:02d}:00",
                "end_time": f"{hour:02d}:30",
                "duration_minutes": 30,
                "is_available": True,
                "booked_count": 0,
                "max_patients": 1
            })
            slot_id += 1

        for hour in range(14, 17):
            slots.append({
                "id": slot_id,
                "date": slot_date.strftime("%Y-%m-%d"),
                "start_time": f"{hour:02d}:00",
                "end_time": f"{hour:02d}:30",
                "duration_minutes": 30,
                "is_available": True,
                "booked_count": 0,
                "max_patients": 1
            })
            slot_id += 1

    return slots

# ============================================================================
# ROUTES
# ============================================================================

@router.get("/doctors")
async def get_doctors(
    specialization: str = None,
    rating_min: float = None,
    limit: int = 20,
    offset: int = 0
):
    doctors = SAMPLE_DOCTORS.copy()
    if specialization:
        doctors = [d for d in doctors if specialization.lower() in d["specialization"].lower()]
    if rating_min:
        doctors = [d for d in doctors if d["rating"] >= rating_min]
    doctors = doctors[offset:offset + limit]
    return {"success": True, "data": {"total": len(SAMPLE_DOCTORS), "doctors": doctors}}


@router.get("/clinics")
async def get_clinics(city: str = None, limit: int = 20):
    clinics = SAMPLE_CLINICS.copy()
    if city:
        clinics = [c for c in clinics if city.lower() in c["city"].lower()]
    return {"success": True, "data": {"clinics": clinics[:limit]}}


@router.get("/slots")
async def get_slots(
    doctor_id: int,
    date_from: str = None,
    date_to: str = None,
    time_preference: str = None
):
    slots = generate_appointment_slots(doctor_id)
    if date_from:
        slots = [s for s in slots if s["date"] >= date_from]
    if date_to:
        slots = [s for s in slots if s["date"] <= date_to]
    if time_preference == "morning":
        slots = [s for s in slots if int(s["start_time"].split(":")[0]) < 12]
    elif time_preference == "afternoon":
        slots = [s for s in slots if 12 <= int(s["start_time"].split(":")[0]) < 17]
    return {"success": True, "data": {"doctor_id": doctor_id, "total_slots": len(slots), "slots": slots}}


@router.post("/book")
async def book_appointment(request: BookAppointmentRequest, db: Session = Depends(get_db)):
    """Book appointment — saves to DB then sends email to patient + doctor."""
    try:
        global APPOINTMENT_COUNTER
        APPOINTMENT_COUNTER += 1

        # ── Find doctor ──────────────────────────────────────────────
        doctor = next((d for d in SAMPLE_DOCTORS if d["id"] == request.doctor_id), None)
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")

        clinic = get_clinic_by_doctor(doctor)

        # ── Get / create user in DB ──────────────────────────────────
        user = create_or_get_user(db, request.user_id)

        # ── Save appointment ─────────────────────────────────────────
        scheduled_datetime = datetime.fromisoformat(
            f"{request.appointment_date}T{request.appointment_time}"
        )

        appointment = Appointment(
            user_id=user.id,
            doctor_id=request.doctor_id,
            clinic_id=doctor["clinic_id"],
            scheduled_at=scheduled_datetime,
            status="confirmed",          # ← was "booked", now "confirmed" so history filter works
            notes=request.notes or "",
        )
        db.add(appointment)
        db.commit()
        db.refresh(appointment)

        confirmation_code = generate_confirmation_code(appointment.id)

        logger.info("✅ Appointment saved — id=%s code=%s", appointment.id, confirmation_code)

        # ── Send emails BEFORE returning ─────────────────────────────
        # (this was after `return` before — unreachable!)
        email_result = await send_appointment_emails(
            AppointmentEmailData(
                patient_name          = request.patient_name,
                patient_email         = request.patient_email,
                doctor_name           = doctor["name"],
                doctor_email          = doctor.get("email"),       # can be None
                doctor_phone          = doctor["phone"],
                doctor_specialization = doctor["specialization"],
                clinic_name           = clinic["name"],
                clinic_address        = clinic.get("address"),
                clinic_phone          = clinic.get("phone"),
                appointment_date      = request.appointment_date,
                appointment_time      = request.appointment_time,
                confirmation_code     = confirmation_code,
                consultation_mode     = request.consultation_mode,
                reason_for_visit      = request.reason_for_visit,
                notes                 = request.notes,
            )
        )
        logger.info("📧 Email result: %s", email_result)

        # ── Return response ──────────────────────────────────────────
        return {
            "success": True,
            "data": {
                "appointment_id":    appointment.id,
                "user_id": user.user_id,
                "confirmation_code": confirmation_code,
                "status":            "confirmed",
                "appointment_date":  request.appointment_date,
                "appointment_time":  request.appointment_time,
                "patient_name":      request.patient_name,
                "patient_email":     request.patient_email,
                "email_sent":        email_result,
                "doctor": {
                    "id":    doctor["id"],
                    "name":  doctor["name"],
                    "phone": doctor["phone"],
                    "email": doctor.get("email", ""),
                },
                "clinic": {
                    "id":      clinic["id"],
                    "name":    clinic["name"],
                    "address": clinic.get("address", ""),
                    "phone":   clinic.get("phone", ""),
                },
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Error booking appointment: %s", str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to book appointment: {str(e)}")


@router.get("/history")
async def get_appointment_history(
    user_id: str,
    status: str = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Return all appointments for this user_id."""
    try:
        user = create_or_get_user(db, user_id)

        query = db.query(Appointment).filter(Appointment.user_id == user.id)

        if status and status != "all":
            query = query.filter(Appointment.status == status)

        appointments = query.order_by(Appointment.scheduled_at.desc()).limit(limit).all()

        formatted = []
        for apt in appointments:
            doctor = next((d for d in SAMPLE_DOCTORS if d["id"] == apt.doctor_id), {})
            clinic = get_clinic_by_doctor(doctor) if doctor else {}

            # scheduled_at is a datetime object from SQLAlchemy
            if isinstance(apt.scheduled_at, datetime):
                apt_date = apt.scheduled_at.strftime("%Y-%m-%d")
                apt_time = apt.scheduled_at.strftime("%H:%M")
            elif isinstance(apt.scheduled_at, str):
                # fallback if stored as string
                parts = apt.scheduled_at.replace("T", " ").split(" ")
                apt_date = parts[0] if len(parts) > 0 else ""
                apt_time = parts[1][:5] if len(parts) > 1 else ""
            else:
                apt_date = ""
                apt_time = ""

            formatted.append({
                "id":                apt.id,
                "doctor_name":       doctor.get("name", "Unknown Doctor"),
                "clinic_name":       clinic.get("name", "City Medical Clinic"),
                "appointment_date":  apt_date,
                "appointment_time":  apt_time,
                "status":            apt.status or "confirmed",
                "confirmation_code": generate_confirmation_code(apt.id),
                "reason_for_visit":  apt.notes or "",
                "consultation_mode": "in_person",
            })

        logger.info("✅ History: %d appointments for user %s", len(formatted), user_id)

        return {
            "success": True,
            "data": {
                "total":        len(formatted),
                "appointments": formatted,
            },
        }

    except Exception as e:
        logger.error("❌ Error getting history: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch history")


@router.put("/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: int,
    request: CancelAppointmentRequest,
    db: Session = Depends(get_db),
):
    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")

        appointment.status = "cancelled"
        db.commit()

        logger.info("✅ Appointment %d cancelled", appointment_id)
        return {
            "success": True,
            "data": {
                "appointment_id":      appointment_id,
                "status":              "cancelled",
                "cancellation_reason": request.reason,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to cancel")


@router.put("/{appointment_id}/reschedule")
async def reschedule_appointment(
    appointment_id: int,
    request: RescheduleAppointmentRequest,
    db: Session = Depends(get_db),
):
    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")

        old_date = appointment.scheduled_at
        appointment.scheduled_at = datetime.fromisoformat(f"{request.new_date}T{request.new_time}")
        appointment.status = "rescheduled"
        db.commit()

        logger.info("✅ Appointment %d rescheduled", appointment_id)
        return {
            "success": True,
            "data": {
                "appointment_id": appointment_id,
                "old_date":       str(old_date),
                "new_date":       request.new_date,
                "new_time":       request.new_time,
                "status":         "rescheduled",
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to reschedule")


@router.get("/confirm/{confirmation_code}")
async def confirm_appointment(confirmation_code: str):
    return {"success": True, "data": {"confirmation_code": confirmation_code, "status": "confirmed"}}


@router.post("/send-reminder")
async def send_reminder(appointment_id: int):
    logger.info("✅ Reminder sent for appointment %d", appointment_id)
    return {"success": True, "data": {"appointment_id": appointment_id, "reminder_sent": True}}