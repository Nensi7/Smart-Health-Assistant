"""
Database Configuration and Management with SQLAlchemy ORM
File: backend/app/database.py

This module handles:
1. Database engine and session setup
2. SQLAlchemy ORM configuration
3. Database initialization
4. Helper functions for common operations
"""

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import logging
import os
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.models import User, ChatSession, ChatMessage, Feedback, TriageAssessment

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

# Get database URL from environment or use default SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./smart_health.db")

logger.info(f"📊 Database URL: {DATABASE_URL}")

# ============================================================================
# CREATE DATABASE ENGINE
# ============================================================================

# SQLite Configuration
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Use StaticPool for SQLite
        echo=os.getenv("DATABASE_ECHO", "False").lower() == "true"  # Log SQL queries if DEBUG
    )
    logger.info("✅ SQLite database engine created")

# PostgreSQL Configuration (if used in production)
elif DATABASE_URL.startswith("postgresql"):
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Test connections before using them
        pool_recycle=3600,  # Recycle connections every hour
        echo=os.getenv("DATABASE_ECHO", "False").lower() == "true"
    )
    logger.info("✅ PostgreSQL database engine created")

else:
    raise ValueError(f"Unsupported database URL: {DATABASE_URL}")

# ============================================================================
# CREATE SESSION FACTORY
# ============================================================================

"""
SessionLocal is a session factory that creates new database sessions
Each request gets its own session which is closed after the request finishes
"""

SessionLocal = sessionmaker(
    autocommit=False,  # Don't auto-commit (we control commits)
    autoflush=False,   # Don't auto-flush (we control flushing)
    bind=engine
)

logger.info("✅ SessionLocal factory created")

# ============================================================================
# DEPENDENCY INJECTION FUNCTION
# ============================================================================

def get_db():
    """
    Dependency injection function for FastAPI
    
    Provides a database session for each request
    Automatically closes the session when done
    
    Usage in routes:
        ```python
        from fastapi import Depends
        from app.database import get_db
        from sqlalchemy.orm import Session
        
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            items = db.query(Item).all()
            return items
        ```
    
    Yields:
        Session: A new database session for this request
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"❌ Database error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================


def init_db():
    """
    Initialize the database by creating all tables
    
    This function:
    1. Imports all models (so SQLAlchemy knows about them)
    2. Creates all tables defined in Base.metadata
    3. Logs success or errors
    
    Call this once when the application starts
    
    Usage:
        ```python
        from app.database import init_db
        
        # In FastAPI lifespan or startup event
        init_db()
        ```
    """
    try:
        # Import models so SQLAlchemy knows about them
        # ✅ IMPORTANT: Import from your models file
        from app.models.models import Base
        
        logger.info("🔄 Creating database tables...")
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        logger.info("✅ Database tables created/verified successfully")
        
        # Verify connection and log table info
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"✅ Database has {len(tables)} tables: {', '.join(tables)}")
        
        # Verify connection
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            logger.info("✅ Database connection verified")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}", exc_info=True)
        raise

    # Upgrade any legacy database schema from older versions
    try:
        upgrade_legacy_schema()
    except Exception as e:
        logger.warning(f"⚠️ Legacy schema upgrade skipped or failed: {str(e)}")

# ============================================================================
# LEGACY SCHEMA UPGRADE
# ============================================================================

def add_column_if_missing(table_name: str, column_name: str, column_definition: str, populate_sql: str = None):
    inspector = inspect(engine)
    columns = [column['name'] for column in inspector.get_columns(table_name)]
    if column_name in columns:
        return

    logger.warning(f"⚠️ Adding missing column {table_name}.{column_name}")
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}"))
        if populate_sql:
            conn.execute(text(populate_sql))


def upgrade_legacy_schema():
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if 'users' in tables:
        user_columns = [column['name'] for column in inspector.get_columns('users')]

        if 'external_id' not in user_columns:
            add_column_if_missing('users', 'external_id', 'external_id VARCHAR(100)', "UPDATE users SET external_id = user_id WHERE external_id IS NULL")
            if engine.dialect.name == 'sqlite':
                with engine.begin() as conn:
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_external_id ON users (external_id)"))

        add_column_if_missing('users', 'password_hash', 'password_hash VARCHAR(255)')
        add_column_if_missing('users', 'age', 'age INTEGER')
        add_column_if_missing('users', 'gender', 'gender VARCHAR(50)')
        add_column_if_missing('users', 'updated_at', 'updated_at DATETIME')
        add_column_if_missing('users', 'terms_accepted_at', 'terms_accepted_at DATETIME')

    if 'sessions' in tables:
        session_columns = [column['name'] for column in inspector.get_columns('sessions')]
        add_column_if_missing('sessions', 'updated_at', 'updated_at DATETIME')
        add_column_if_missing('sessions', 'is_active', 'is_active BOOLEAN')

        if 'user_id' in session_columns:
            logger.warning("⚠️ Converting legacy session user IDs to numeric foreign keys")
            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE sessions SET user_id = (SELECT id FROM users WHERE users.external_id = sessions.user_id) "
                    "WHERE user_id IS NOT NULL AND user_id != '' "
                    "AND user_id GLOB '*[^0-9]*' "
                    "AND EXISTS (SELECT 1 FROM users WHERE users.external_id = sessions.user_id)"
                ))

    if 'feedback' in tables:
        feedback_columns = [column['name'] for column in inspector.get_columns('feedback')]
        add_column_if_missing('feedback', 'comments', 'comments TEXT', "UPDATE feedback SET comments = feedback_text WHERE comments IS NULL")
        add_column_if_missing('feedback', 'actual_diagnosis', 'actual_diagnosis VARCHAR(500)')
        add_column_if_missing('feedback', 'session_id', 'session_id INTEGER')
        add_column_if_missing('feedback', 'was_helpful', 'was_helpful BOOLEAN', "UPDATE feedback SET was_helpful = CASE WHEN rating >= 4 THEN 1 ELSE 0 END WHERE was_helpful IS NULL")

    if 'chat_messages' in tables:
        chat_columns = [column['name'] for column in inspector.get_columns('chat_messages')]
        if 'session_id' in chat_columns and 'sessions' in tables:
            logger.warning("⚠️ Migrating legacy chat message session identifiers to integer IDs")
            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE chat_messages SET session_id = (SELECT id FROM sessions WHERE sessions.session_id = chat_messages.session_id) "
                    "WHERE session_id IS NOT NULL AND session_id != '' "
                    "AND EXISTS (SELECT 1 FROM sessions WHERE sessions.session_id = chat_messages.session_id)"
                ))

        if 'user_id' in chat_columns:
            logger.warning("⚠️ Backfilling missing chat message user IDs")
            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE chat_messages SET user_id = (SELECT user_id FROM sessions WHERE sessions.id = chat_messages.session_id) "
                    "WHERE user_id IS NULL AND session_id IS NOT NULL"
                ))

        add_column_if_missing('chat_messages', 'user_id', 'user_id INTEGER', None)
        add_column_if_missing('chat_messages', 'message_type', 'message_type VARCHAR(50)', "UPDATE chat_messages SET message_type = role WHERE message_type IS NULL")
        add_column_if_missing('chat_messages', 'role', 'role VARCHAR(50)', "UPDATE chat_messages SET role = message_type WHERE role IS NULL")
        add_column_if_missing('chat_messages', 'created_at', 'created_at DATETIME', "UPDATE chat_messages SET created_at = timestamp WHERE created_at IS NULL")

    logger.info("✅ Legacy schema upgrade complete")

# ============================================================================
# DATABASE UTILITY FUNCTIONS
# ============================================================================

def drop_all_tables():
    """
    Drop all tables from the database
    
    ⚠️ WARNING: This deletes all data!
    Only use for development/testing
    
    Usage:
        ```python
        from app.database import drop_all_tables
        drop_all_tables()
        ```
    """
    try:
        from app.models.models import Base
        logger.warning("⚠️ Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        logger.warning("⚠️ All tables dropped")
    except Exception as e:
        logger.error(f"❌ Error dropping tables: {str(e)}")
        raise


def reset_db():
    """
    Reset the database (drop all tables and recreate them)
    
    ⚠️ WARNING: This deletes all data!
    Only use for development/testing
    
    Usage:
        ```python
        from app.database import reset_db
        reset_db()
        ```
    """
    try:
        confirmation = input("⚠️ WARNING: This will DELETE ALL DATA! Type 'yes' to confirm: ")
        if confirmation.lower() == "yes":
            drop_all_tables()
            init_db()
            logger.info("✅ Database reset complete")
        else:
            logger.info("❌ Database reset cancelled")
    except Exception as e:
        logger.error(f"❌ Error resetting database: {str(e)}")
        raise


def check_database_connection():
    """
    Check if database connection is working
    
    Returns:
        dict: Connection status information
    
    Usage:
        ```python
        from app.database import check_database_connection
        status = check_database_connection()
        print(status)
        ```
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            
            # Get table info
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            return {
                "status": "connected",
                "database": DATABASE_URL,
                "message": "Database connection successful",
                "tables_count": len(tables),
                "tables": tables
            }
    except Exception as e:
        return {
            "status": "disconnected",
            "database": DATABASE_URL,
            "error": str(e)
        }


def get_database_stats(db: Session) -> dict:
    """
    Get database statistics
    
    Returns count of records in each table
    """
    try:
        from app.models.models import (
            User, ChatSession, ChatMessage, TriageAssessment,
            Feedback, Doctor, Clinic, Appointment, HealthTipDB
        )
        
        stats = {
            "users": db.query(User).count(),
            "chat_sessions": db.query(ChatSession).count(),
            "chat_messages": db.query(ChatMessage).count(),
            "triage_assessments": db.query(TriageAssessment).count(),
            "feedback": db.query(Feedback).count(),
            "doctors": db.query(Doctor).count(),
            "clinics": db.query(Clinic).count(),
            "appointments": db.query(Appointment).count(),
            "health_tips": db.query(HealthTipDB).count(),
        }
        
        logger.info(f"📊 Database stats: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"❌ Error getting database stats: {str(e)}")
        return {}


# ============================================================================
# USER OPERATIONS
# ============================================================================

def create_or_get_user(db: Session, external_id: str, name: str = "Anonymous", 
                       email: str = None, language: str = "en") -> 'User':
    """
    Create a new user or get existing user by external_id
    
    Args:
        db: Database session
        external_id: Unique user identifier (can be UUID)
        name: User name
        email: User email
        language: Preferred language (en/hi)
    
    Returns:
        User: User object
    """
    try:
        from app.models.models import User, LanguageEnum
        from sqlalchemy import or_

        # Check if user exists by external_id or legacy user_id
        user = db.query(User).filter(
            or_(User.external_id == external_id, User.legacy_user_id == external_id)
        ).first()
        
        if user:
            logger.info(f"✅ User found: {external_id}")
            return user
        
        # Convert language string to LanguageEnum if needed
        if isinstance(language, str):
            try:
                language_enum = LanguageEnum(language)
            except ValueError:
                logger.warning(f"⚠️ Invalid language '{language}', defaulting to ENGLISH")
                language_enum = LanguageEnum.ENGLISH
        else:
            language_enum = language
        
        # Create new user
        user = User(
            external_id=external_id,
            legacy_user_id=external_id,
            name=name,
            email=email,
            language=language_enum,
            terms_accepted_at=datetime.utcnow()
        )

        lang_map = {
        "en": "ENGLISH",
        "hi": "HINDI"
    }

        language = lang_map.get(language, "ENGLISH")
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(f"✅ User created: {external_id}")
        return user
        
    except Exception as e:
        logger.error(f"❌ Error creating user: {str(e)}")
        db.rollback()
        raise


# ============================================================================
# SESSION OPERATIONS
# ============================================================================

def create_chat_session(db: Session, user_id: int, session_id: str) -> 'ChatSession':
    """
    Create a new chat session
    
    Args:
        db: Database session
        user_id: User ID from database
        session_id: Unique session identifier
    
    Returns:
        ChatSession: Chat session object
    """
    try:
        from app.models.models import ChatSession
        
        # Check if session exists
        existing_session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        
        if existing_session:
            logger.info(f"✅ Session already exists: {session_id}")
            return existing_session
        
        # Create new session
        session = ChatSession(
            user_id=user_id,
            session_id=session_id,
            is_active=True
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        logger.info(f"✅ Chat session created: {session_id}")
        return session
        
    except Exception as e:
        logger.error(f"❌ Error creating session: {str(e)}")
        db.rollback()
        raise


def get_session_by_id(db: Session, session_id: str) -> Optional['ChatSession']:
    """Get session by session_id"""
    try:
        from app.models.models import ChatSession
        
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        
        return session
        
    except Exception as e:
        logger.error(f"❌ Error getting session: {str(e)}")
        return None


# ============================================================================
# MESSAGE OPERATIONS
# ============================================================================

def store_chat_message(db: Session, session_id: int, user_id: int, 
                      content: str, message_type: str = "user") -> 'ChatMessage':
    """
    Store a chat message in database
    
    Args:
        db: Database session
        session_id: Session ID from database
        user_id: User ID from database
        content: Message content
        message_type: 'user' or 'assistant'
    
    Returns:
        ChatMessage: Message object
    """
    try:
        from app.models.models import ChatMessage
        
        message = ChatMessage(
            session_id=session_id,
            user_id=user_id,
            content=content,
            message_type=message_type,
            role=message_type,
            timestamp=datetime.utcnow(),
        )
        
        db.add(message)
        db.commit()
        db.refresh(message)
        
        logger.info(f"✅ Message stored: {message_type} message in session {session_id}")
        return message
        
    except Exception as e:
        logger.error(f"❌ Error storing message: {str(e)}")
        db.rollback()
        raise


def get_session_messages(db: Session, session_id: int, limit: int = 100) -> List['ChatMessage']:
    """
    Get all messages in a session
    
    Args:
        db: Database session
        session_id: Session ID from database
        limit: Maximum messages to return
    
    Returns:
        List of ChatMessage objects
    """
    try:
        from app.models.models import ChatMessage
        
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).limit(limit).all()
        
        logger.info(f"✅ Retrieved {len(messages)} messages from session {session_id}")
        return messages
        
    except Exception as e:
        logger.error(f"❌ Error getting messages: {str(e)}")
        return []


# ============================================================================
# FEEDBACK OPERATIONS
# ============================================================================

def store_feedback(db: Session, session_id: Optional[int], user_id: int, 
                  rating: int, comments: str = None, 
                  was_helpful: bool = None) -> 'Feedback':
    """
    Store user feedback in database
    
    Args:
        db: Database session
        session_id: Session ID from database
        user_id: User ID from database
        rating: Rating 1-5
        comments: Optional comments
        was_helpful: Whether assessment was helpful
    
    Returns:
        Feedback: Feedback object
    """
    try:
        from app.models.models import Feedback
        
        feedback = Feedback(
            session_id=session_id,
            user_id=user_id,
            rating=rating,
            was_helpful=was_helpful if was_helpful is not None else (rating >= 4),
            comments=comments
        )
        
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        
        logger.info(f"✅ Feedback stored: ID {feedback.id}, rating {rating}/5")
        return feedback
        
    except Exception as e:
        logger.error(f"❌ Error storing feedback: {str(e)}")
        db.rollback()
        raise


def get_feedback_stats(db: Session) -> dict:
    """Get feedback statistics"""
    try:
        from app.models.models import Feedback
        
        total = db.query(Feedback).count()
        
        if total == 0:
            return {
                "total_feedback": 0,
                "average_rating": 0,
                "helpful_count": 0
            }
        
        avg_rating = db.query(
            db.func.avg(Feedback.rating)
        ).scalar() or 0
        
        helpful_count = db.query(Feedback).filter(
            Feedback.was_helpful == True
        ).count()
        
        return {
            "total_feedback": total,
            "average_rating": round(avg_rating, 2),
            "helpful_count": helpful_count,
            "helpful_percentage": round((helpful_count / total) * 100, 2) if total > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting feedback stats: {str(e)}")
        return {}


def close_chat_session(db: Session, session_id: str):
    """
    Close a chat session by setting is_active to False
    
    Args:
        db: Database session
        session_id: Session ID string
    
    Returns:
        bool: True if closed, False if not found
    """
    try:
        session = get_session_by_id(db, session_id)
        
        if session:
            session.is_active = False
            db.commit()
            logger.info(f"✅ Chat session closed: {session_id}")
            return True
        else:
            logger.warning(f"⚠️ Session not found for closing: {session_id}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Error closing session: {str(e)}")
        db.rollback()
        raise


# ============================================================================
# COMPATIBILITY HELPER ALIASES (requested API)
# ============================================================================

def get_connection() -> Session:
    """
    Return a new database session.
    Caller must close it when done.
    """
    return SessionLocal()


def create_user(db: Session, external_id: str, name: str = "Anonymous",
                email: str = None, language: str = "en") -> 'User':
    """Compatibility alias for creating/fetching a user profile."""
    return create_or_get_user(
        db=db,
        external_id=external_id,
        name=name,
        email=email,
        language=language,
    )


def create_session(db: Session, user_id: int, session_id: str) -> 'ChatSession':
    """Compatibility alias for creating a chat session."""
    return create_chat_session(db=db, user_id=user_id, session_id=session_id)


def close_session(db: Session, session_id: str):
    """Compatibility alias for closing a chat session."""
    return close_chat_session(db=db, session_id=session_id)

def store_triage_assessment(db: Session, session_id: int, user_id: int,
                           symptoms: str, severity_level: str, severity_score: int,
                           recommendation: str, confidence_score: float = 0.0,
                           emergency_indicators: str = None,
                           home_care_suggestions: str = None) -> 'TriageAssessment':
    """
    Store triage assessment in database
    
    Args:
        db: Database session
        session_id: Session ID
        user_id: User ID
        symptoms: Symptoms (JSON string)
        severity_level: Severity level (mild, moderate, severe, emergency)
        severity_score: Score 1-10
        recommendation: Care recommendation
        confidence_score: Confidence 0-1
        emergency_indicators: Emergency indicators (JSON string)
        home_care_suggestions: Home care suggestions (JSON string)
    
    Returns:
        TriageAssessment: Assessment object
    """
    try:
        from app.models.models import TriageAssessment, SeverityEnum
        
        # Map string to enum
        severity_enum_map = {
            "mild": SeverityEnum.MILD,
            "moderate": SeverityEnum.MODERATE,
            "severe": SeverityEnum.SEVERE,
            "emergency": SeverityEnum.EMERGENCY
        }
        
        severity_enum = severity_enum_map.get(severity_level.lower(), SeverityEnum.MODERATE)
        
        assessment = TriageAssessment(
            session_id=session_id,
            user_id=user_id,
            symptoms=symptoms,
            severity_level=severity_enum,
            severity_score=severity_score,
            recommendation=recommendation,
            confidence_score=confidence_score,
            emergency_indicators=emergency_indicators,
            home_care_suggestions=home_care_suggestions
        )
        
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        
        logger.info(f"✅ Triage assessment stored: ID {assessment.id}, severity {severity_level}")
        return assessment
        
    except Exception as e:
        logger.error(f"❌ Error storing triage assessment: {str(e)}")
        db.rollback()
        raise


# ============================================================================
# CLI COMMANDS (when running directly)
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "init":
            print("🔄 Initializing database...")
            init_db()
            print("✅ Database initialized")
            
        elif command == "reset":
            print("⚠️ Resetting database...")
            reset_db()
            print("✅ Database reset complete")
            
        elif command == "check":
            print("🔍 Checking database connection...")
            status = check_database_connection()
            print(f"Status: {status['status']}")
            print(f"Database: {status['database']}")
            if "error" in status:
                print(f"Error: {status['error']}")
            else:
                print(status.get('message', 'Connected'))
                if "tables" in status:
                    print(f"Tables ({status['tables_count']}): {', '.join(status['tables'])}")
                    
        elif command == "stats":
            print("📊 Getting database statistics...")
            db = SessionLocal()
            try:
                stats = get_database_stats(db)
                for table, count in stats.items():
                    print(f"  {table}: {count} records")
            finally:
                db.close()
        else:
            print(f"Unknown command: {command}")
            print("Available commands: init, reset, check, stats")
    else:
        # Default: Initialize database
        print("🔄 Initializing database...")
        init_db()
        print("✅ Database initialized")