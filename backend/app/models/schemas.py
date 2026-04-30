"""
Pydantic Models and Schemas for Smart Health Assistant
Defines request/response data structures with validation
✅ Migrated to Pydantic v2 ConfigDict (no deprecation warnings)
"""

from pydantic import BaseModel, Field, ConfigDict, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# ============================================================================
# ENUMS - Define fixed choices
# ============================================================================

class SeverityLevel(str, Enum):
    """Severity levels for medical assessment"""
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    EMERGENCY = "emergency"


class Language(str, Enum):
    """Supported languages"""
    ENGLISH = "en"
    HINDI = "hi"


class Gender(str, Enum):
    """User gender"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


# ============================================================================
# USER MODELS
# ============================================================================

class UserRegisterRequest(BaseModel):
    """User registration request"""
    email: str = Field(..., description="User email")
    password: str = Field(..., min_length=8, description="User password (min 8 chars)")
    name: str = Field(..., min_length=2, description="User full name")
    age: int = Field(..., ge=1, le=150, description="User age (1-150)")
    language: Language = Field(default=Language.ENGLISH, description="Preferred language")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123",
                "name": "John Doe",
                "age": 30,
                "language": "en"
            }
        }
    )


class UserLoginRequest(BaseModel):
    """User login request"""
    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123"
            }
        }
    )


class UserProfile(BaseModel):
    """User profile response"""
    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    name: str = Field(..., description="User name")
    age: int = Field(..., description="User age")
    language: Language = Field(..., description="Preferred language")
    gender: Optional[Gender] = Field(None, description="User gender")
    created_at: datetime = Field(..., description="Account creation timestamp")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "email": "user@example.com",
                "name": "John Doe",
                "age": 30,
                "language": "en",
                "gender": "male",
                "created_at": "2024-01-30T12:00:00"
            }
        }
    )


# ============================================================================
# SYMPTOM & TRIAGE MODELS
# ============================================================================

class SymptomInput(BaseModel):
    """User symptom input"""
    text: str = Field(..., min_length=5, max_length=1000, description="User description of symptoms")
    duration_days: Optional[int] = Field(None, ge=1, le=365, description="Symptom duration in days")
    severity_self_reported: Optional[int] = Field(None, ge=1, le=10, description="User's self-reported severity (1-10)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "I have fever, headache, and body ache for 3 days",
                "duration_days": 3,
                "severity_self_reported": 5
            }
        }
    )


class SymptomExtraction(BaseModel):
    """Extracted symptoms from user input"""
    symptoms: List[str] = Field(..., description="Extracted symptom names")
    confidence_scores: Dict[str, float] = Field(..., description="Confidence score for each symptom (0-1)")
    language_detected: Language = Field(..., description="Detected language")
    duration_days: Optional[int] = Field(None, description="Symptom duration")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symptoms": ["fever", "headache", "body_ache"],
                "confidence_scores": {
                    "fever": 0.95,
                    "headache": 0.87,
                    "body_ache": 0.82
                },
                "language_detected": "en",
                "duration_days": 3
            }
        }
    )


class TriageResponse(BaseModel):
    """Triage assessment response"""
    severity_level: SeverityLevel = Field(..., description="Severity assessment (mild/moderate/severe/emergency)")
    severity_score: int = Field(..., ge=1, le=10, description="Numerical severity score (1-10)")
    recommendation: str = Field(..., description="Care recommendation")
    emergency_indicators: List[str] = Field(default_factory=list, description="Critical warning signs if any")
    home_care_suggestions: List[str] = Field(default_factory=list, description="Home care tips")
    when_to_see_doctor: str = Field(..., description="Guidance on when to seek medical help")
    next_questions: List[str] = Field(default_factory=list, description="Follow-up questions to ask")
    confidence_score: float = Field(..., ge=0, le=1, description="Confidence in assessment (0-1)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "severity_level": "moderate",
                "severity_score": 5,
                "recommendation": "Visit a clinic within 24 hours if symptoms persist",
                "emergency_indicators": [],
                "home_care_suggestions": ["Rest", "Stay hydrated", "Take paracetamol if fever"],
                "when_to_see_doctor": "If symptoms persist for more than 3 days or fever exceeds 103°F",
                "next_questions": ["Do you have a cough?", "Any difficulty breathing?"],
                "confidence_score": 0.85
            }
        }
    )


# ============================================================================
# CHAT MODELS
# ============================================================================

class ChatMessage(BaseModel):
    """Single chat message"""
    id: Optional[int] = Field(None, description="Message ID")
    user_id: int = Field(..., description="User who sent message")
    message_type: str = Field(..., description="Type: 'user' or 'assistant'")
    content: str = Field(..., min_length=1, description="Message content")
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "user_id": 1,
                "message_type": "user",
                "content": "I have fever and headache",
                "timestamp": "2024-01-30T12:00:00"
            }
        }
    )


class ChatSession(BaseModel):
    """Chat session with history"""
    session_id: str = Field(..., description="Unique session identifier")
    user_id: int = Field(..., description="User ID")
    messages: List[ChatMessage] = Field(default_factory=list, description="Chat messages")
    created_at: datetime = Field(..., description="Session creation time")
    updated_at: Optional[datetime] = Field(None, description="Last update time")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_123abc",
                "user_id": 1,
                "messages": [],
                "created_at": "2024-01-30T12:00:00",
                "updated_at": "2024-01-30T12:05:00"
            }
        }
    )


class ChatRequest(BaseModel):
    """User chat request"""
    message: str = Field(..., min_length=1, max_length=1000, description="User message")
    language: Language = Field(default=Language.ENGLISH, description="Language of message")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "I have been feeling unwell",
                "language": "en",
                "context": {}
            }
        }
    )


class ChatResponse(BaseModel):
    """Chat response with assessment"""
    message_id: int = Field(..., description="Message ID")
    response: str = Field(..., description="Assistant response")
    triage: Optional[TriageResponse] = Field(None, description="Medical assessment")
    follow_up_questions: List[str] = Field(default_factory=list, description="Suggested follow-ups")
    resources: Optional[List[Dict[str, str]]] = Field(None, description="Helpful resources")
    timestamp: datetime = Field(..., description="Response timestamp")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message_id": 1,
                "response": "Thank you for providing that information...",
                "triage": {},
                "follow_up_questions": ["Do you have other symptoms?"],
                "resources": [],
                "timestamp": "2024-01-30T12:01:00"
            }
        }
    )


# ============================================================================
# HEALTHCARE MODELS
# ============================================================================

class Hospital(BaseModel):
    """Hospital/clinic information"""
    id: int = Field(..., description="Hospital ID")
    name: str = Field(..., description="Hospital name")
    type: str = Field(..., description="Type: hospital, clinic, etc")
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    distance_km: float = Field(..., description="Distance from user location")
    address: str = Field(..., description="Full address")
    phone: str = Field(..., description="Contact number")
    website: Optional[str] = Field(None, description="Hospital website")
    opening_hours: str = Field(..., description="Operating hours")
    emergency: bool = Field(..., description="Has emergency services")
    rating: Optional[float] = Field(None, ge=0, le=5, description="Rating (0-5 stars)")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Apollo Hospital",
                "type": "hospital",
                "latitude": 19.1136,
                "longitude": 72.8697,
                "distance_km": 0.5,
                "address": "216, Vileparle East, Mumbai",
                "phone": "022-2840-3000",
                "website": "https://www.apollohospitals.com",
                "opening_hours": "24/7",
                "emergency": True,
                "rating": 4.5
            }
        }
    )


class HospitalSearchRequest(BaseModel):
    """Request to search hospitals"""
    latitude: float = Field(..., ge=-90, le=90, description="User latitude")
    longitude: float = Field(..., ge=-180, le=180, description="User longitude")
    radius_km: float = Field(default=5.0, ge=1, le=50, description="Search radius in km")
    limit: int = Field(default=10, ge=1, le=50, description="Max results")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "latitude": 19.0760,
                "longitude": 72.8777,
                "radius_km": 5,
                "limit": 10
            }
        }
    )


class HospitalSearchResponse(BaseModel):
    """Hospital search results"""
    success: bool = Field(..., description="Search success status")
    count: int = Field(..., description="Number of hospitals found")
    hospitals: List[Hospital] = Field(..., description="Hospital list")
    user_location: Dict[str, float] = Field(..., description="User coordinates")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "count": 3,
                "hospitals": [],
                "user_location": {"latitude": 19.0760, "longitude": 72.8777}
            }
        }
    )


# ============================================================================
# FEEDBACK MODELS
# ============================================================================

class FeedbackRequest(BaseModel):
    """User feedback on assessment"""
    session_id: str = Field(..., description="Chat session ID")
    rating: int = Field(..., ge=1, le=5, description="Rating (1-5 stars)")
    was_helpful: bool = Field(..., description="Was the assessment helpful?")
    comments: Optional[str] = Field(None, max_length=500, description="Additional comments")
    actual_diagnosis: Optional[str] = Field(None, description="What was the actual diagnosis?")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sess_123abc",
                "rating": 4,
                "was_helpful": True,
                "comments": "The suggestions were very helpful",
                "actual_diagnosis": "Common flu"
            }
        }
    )


class FeedbackResponse(BaseModel):
    """Feedback submission response"""
    success: bool = Field(..., description="Submission success")
    feedback_id: int = Field(..., description="Feedback ID")
    message: str = Field(..., description="Confirmation message")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "feedback_id": 1,
                "message": "Thank you for your feedback!"
            }
        }
    )


# ============================================================================
# HEALTH TIPS & EDUCATION MODELS
# ============================================================================

class HealthTip(BaseModel):
    """Health education tip"""
    id: int = Field(..., description="Tip ID")
    title: str = Field(..., description="Tip title")
    content: str = Field(..., description="Tip content")
    category: str = Field(..., description="Category (prevention, symptom, etc)")
    languages: List[Language] = Field(..., description="Available languages")
    read_time_minutes: int = Field(..., description="Estimated reading time")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "title": "How to Prevent Common Cold",
                "content": "Wash your hands frequently...",
                "category": "prevention",
                "languages": ["en", "hi"],
                "read_time_minutes": 3
            }
        }
    )


# ============================================================================
# EMERGENCY MODELS
# ============================================================================

class EmergencyIndicator(BaseModel):
    """Emergency warning sign"""
    symptom: str = Field(..., description="Emergency symptom")
    action: str = Field(..., description="Recommended action")
    hotline: str = Field(..., description="Emergency hotline")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symptom": "Chest pain",
                "action": "CALL 108 IMMEDIATELY",
                "hotline": "108"
            }
        }
    )


class EmergencyResponse(BaseModel):
    """Emergency contact information"""
    country: str = Field(..., description="Country name")
    emergency_number: str = Field(..., description="Emergency number")
    name: str = Field(..., description="Service name")
    description: str = Field(..., description="Service description")
    available_24_7: bool = Field(..., description="24/7 availability")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "country": "India",
                "emergency_number": "108",
                "name": "Emergency Response Service",
                "description": "Call 108 for ambulance, medical emergency",
                "available_24_7": True
            }
        }
    )


# ============================================================================
# ERROR RESPONSE MODELS
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")
    timestamp: datetime = Field(..., description="Error timestamp")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "Validation Error",
                "message": "Invalid input provided",
                "status_code": 422,
                "timestamp": "2024-01-30T12:00:00"
            }
        }
    )


# ============================================================================
# SUCCESS RESPONSE MODELS
# ============================================================================

class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = Field(default=True, description="Success indicator")
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    timestamp: datetime = Field(..., description="Response timestamp")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {},
                "timestamp": "2024-01-30T12:00:00"
            }
        }
    )


# ============================================================================
# VALIDATION: Ensure NO PAID SERVICES USED
# ============================================================================
# ✅ All services are FREE:
# - OpenStreetMap (Nominatim/Overpass) for healthcare search
# - SQLite for database (local, no cloud)
# - Ollama/LocalAI for LLM (open source, run locally)
# - No Google/Gemini/Claude API keys required
# ============================================================================
