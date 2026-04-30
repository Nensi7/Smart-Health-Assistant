"""
SQLAlchemy Database Models for Smart Health Assistant
Defines database schema and ORM models
"""

from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

# Create base class for all models
Base = declarative_base()

# ============================================================================
# ENUMS FOR DATABASE
# ============================================================================

class SeverityEnum(str, enum.Enum):
    """Severity levels"""
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    EMERGENCY = "emergency"


class LanguageEnum(str, enum.Enum):
    """Supported languages"""
    ENGLISH = "en"
    HINDI = "hi"


class GenderEnum(str, enum.Enum):
    """Gender"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


# ============================================================================
# USER MODEL
# ============================================================================

class User(Base):
    """
    User model - stores user account information
    
    Attributes:
        id: Primary key
        email: User email (unique)
        password_hash: Hashed password
        name: User full name
        age: User age
        gender: User gender
        language: Preferred language
        created_at: Account creation timestamp
        updated_at: Last update timestamp
        is_active: Account status
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    legacy_user_id = Column("user_id", String(100), unique=True, index=True, nullable=True)
    external_id = Column(String(100), unique=True, index=True, nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    name = Column(String(255), nullable=False, default="Anonymous")
    age = Column(Integer, nullable=False, default=0)
    gender = Column(SQLEnum(GenderEnum), nullable=True, default=GenderEnum.PREFER_NOT_TO_SAY)
    language = Column(SQLEnum(LanguageEnum), nullable=False, default=LanguageEnum.ENGLISH)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True, nullable=False)
    terms_accepted_at = Column(DateTime, nullable=True)
    
    # Relationships
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, name={self.name})>"


# ============================================================================
# CHAT SESSION MODEL
# ============================================================================

class ChatSession(Base):
    """
    Chat session model - stores user chat sessions
    
    Attributes:
        id: Primary key
        user_id: Foreign key to user
        session_id: Unique session identifier
        created_at: Session creation time
        updated_at: Last update time
        is_active: Session active status
    """
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="session", cascade="all, delete-orphan")
    health_tips = relationship("HealthTipDB", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ChatSession(id={self.id}, user_id={self.user_id}, session_id={self.session_id})>"


# ============================================================================
# CHAT MESSAGE MODEL
# ============================================================================

class ChatMessage(Base):
    """
    Chat message model - stores individual messages
    
    Attributes:
        id: Primary key
        session_id: Foreign key to chat session
        user_id: Foreign key to user
        message_type: 'user' or 'assistant'
        content: Message content
        created_at: Message timestamp
    """
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message_type = Column(String(50), nullable=False)  # 'user' or 'assistant'
    # Backward-compatibility column for legacy schema where `role` is required.
    role = Column(String(50), nullable=False, default="user")
    content = Column(Text, nullable=False)
    # Legacy schema compatibility: some DB versions require `timestamp` NOT NULL.
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    user = relationship("User", back_populates="messages")
    
    def __repr__(self):
        return f"<ChatMessage(id={self.id}, session_id={self.session_id}, type={self.message_type})>"


# ============================================================================
# TRIAGE ASSESSMENT MODEL
# ============================================================================

class TriageAssessment(Base):
    """
    Triage assessment model - stores medical assessments
    
    Attributes:
        id: Primary key
        session_id: Foreign key to chat session
        user_id: Foreign key to user
        symptoms: Extracted symptoms (JSON)
        severity_level: Assessment severity
        severity_score: Numerical score (1-10)
        recommendation: Care recommendation
        confidence_score: Assessment confidence
        created_at: Assessment timestamp
    """
    __tablename__ = "triage_assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symptoms = Column(Text, nullable=False)  # JSON string of symptoms
    severity_level = Column(SQLEnum(SeverityEnum), nullable=False)
    severity_score = Column(Integer, nullable=False)  # 1-10
    recommendation = Column(Text, nullable=False)
    emergency_indicators = Column(Text, nullable=True)  # JSON string
    home_care_suggestions = Column(Text, nullable=True)  # JSON string
    confidence_score = Column(Float, nullable=False)  # 0-1
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<TriageAssessment(id={self.id}, user_id={self.user_id}, severity={self.severity_level})>"


# ============================================================================
# FEEDBACK MODEL
# ============================================================================

class Feedback(Base):
    """
    User feedback model - stores user feedback on assessments
    
    Attributes:
        id: Primary key
        session_id: Foreign key to chat session
        user_id: Foreign key to user
        rating: Rating (1-5 stars)
        was_helpful: Was assessment helpful
        comments: User comments
        actual_diagnosis: Actual diagnosis if known
        created_at: Feedback timestamp
    """
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1-5
    was_helpful = Column(Boolean, nullable=False)
    comments = Column(Text, nullable=True)
    actual_diagnosis = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="feedback")
    
    def __repr__(self):
        return f"<Feedback(id={self.id}, user_id={self.user_id}, rating={self.rating})>"


# ============================================================================
# SEARCH HISTORY MODEL
# ============================================================================

class SearchHistory(Base):
    """
    Search history model - stores user searches
    
    Attributes:
        id: Primary key
        user_id: Foreign key to user
        query: Search query
        results_count: Number of results
        created_at: Search timestamp
    """
    __tablename__ = "search_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    query = Column(String(500), nullable=False)
    results_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<SearchHistory(id={self.id}, user_id={self.user_id}, query={self.query})>"


# ============================================================================
# HEALTH TIPS MODEL (optional - for storing custom tips in DB)
# ============================================================================

class HealthTipDB(Base):
    """
    Health tips model - stores health education tips
    
    Attributes:
        id: Primary key
        title: Tip title
        content: Tip content
        category: Category (prevention, symptom, etc)
        language: Language
        created_at: Creation timestamp
    """
    __tablename__ = "health_tips"
    
    id = Column(Integer, primary_key=True, index=True)
    tip_id = Column(String(100), unique=True, nullable=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True)
    language = Column(SQLEnum(LanguageEnum), nullable=False, default=LanguageEnum.ENGLISH)
    read_time_minutes = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    session = relationship("ChatSession", back_populates="health_tips")
    
    def __repr__(self):
        return f"<HealthTipDB(id={self.id}, title={self.title}, category={self.category})>"


# ============================================================================
# DOCTOR MODEL
# ============================================================================

class Doctor(Base):
    """
    Doctor profile model
    """
    __tablename__ = "doctors"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    specialization = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    rating = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    clinic = relationship("Clinic", back_populates="doctors")
    appointments = relationship("Appointment", back_populates="doctor", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Doctor(id={self.id}, name={self.name}, specialization={self.specialization})>"


# ============================================================================
# CLINIC MODEL
# ============================================================================

class Clinic(Base):
    """
    Clinic information model
    """
    __tablename__ = "clinics"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True, index=True)
    state = Column(String(100), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    is_open = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    doctors = relationship("Doctor", back_populates="clinic", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="clinic", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Clinic(id={self.id}, name={self.name}, city={self.city})>"


# ============================================================================
# APPOINTMENT MODEL
# ============================================================================

class Appointment(Base):
    """Booked appointment model"""
    __tablename__ = "appointments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id", ondelete="SET NULL"), nullable=True, index=True)
    scheduled_at = Column(DateTime, nullable=False)
    status = Column(String(100), default="booked", nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    session = relationship("ChatSession", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    clinic = relationship("Clinic", back_populates="appointments")
        
    def __repr__(self):
        return f"<Appointment(id={self.id}, user_id={self.user_id}, scheduled_at={self.scheduled_at})>"
