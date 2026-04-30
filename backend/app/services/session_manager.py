"""
Session Management Service
Handle user sessions for chat history and tracking

Features:
- In-memory session storage (for development)
- Session creation, retrieval, and expiration
- Chat history storage per session
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ChatMessage:
    """Single chat message"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    severity_level: str = ""
    severity_score: float = 0.0

@dataclass
class ChatSession:
    """Chat session with history"""
    session_id: str
    user_id: str = ""
    language: str = "en"
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    messages: List[ChatMessage] = field(default_factory=list)
    is_active: bool = True
    
    def add_message(self, role: str, content: str, severity_level: str = "", severity_score: float = 0.0):
        """Add message to session"""
        message = ChatMessage(
            role=role,
            content=content,
            severity_level=severity_level,
            severity_score=severity_score
        )
        self.messages.append(message)
        self.last_activity = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "language": self.language,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "is_active": self.is_active,
            "message_count": len(self.messages),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "severity_level": msg.severity_level,
                    "severity_score": msg.severity_score
                }
                for msg in self.messages
            ]
        }


# ============================================================================
# SESSION MANAGER
# ============================================================================

class SessionManager:
    """
    Manage user sessions for the Smart Health Assistant
    
    Usage:
        manager = SessionManager()
        session = manager.create_session(language="en")
        session.add_message("user", "I have a headache")
        history = manager.get_session_history(session.session_id)
    """
    
    def __init__(self, session_expiry_minutes: int = 30):
        """
        Initialize session manager
        
        Args:
            session_expiry_minutes: Time before session expires (default 30 minutes)
        """
        self.sessions: Dict[str, ChatSession] = {}
        self.session_expiry = timedelta(minutes=session_expiry_minutes)
        self._cleanup_expired_sessions()
    
    def create_session(self, user_id: str = "", language: str = "en") -> ChatSession:
        """
        Create a new session
        
        Args:
            user_id: Optional user identifier
            language: Default language for the session
        
        Returns:
            ChatSession object
        """
        session_id = str(uuid.uuid4())
        session = ChatSession(
            session_id=session_id,
            user_id=user_id,
            language=language
        )
        self.sessions[session_id] = session
        logger.info(f"✅ Session created: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Get session by ID
        
        Args:
            session_id: Session ID
        
        Returns:
            ChatSession or None if not found/expired
        """
        session = self.sessions.get(session_id)
        
        if session and self._is_session_valid(session):
            session.last_activity = datetime.utcnow()
            return session
        
        if session:
            # Session expired, remove it
            del self.sessions[session_id]
            logger.info(f"🗑️ Session expired and removed: {session_id}")
        
        return None
    
    def get_session_history(self, session_id: str) -> Optional[Dict]:
        """
        Get session with full chat history
        
        Args:
            session_id: Session ID
        
        Returns:
            Session dictionary or None
        """
        session = self.get_session(session_id)
        
        if session:
            return session.to_dict()
        
        return None
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        severity_level: str = "",
        severity_score: float = 0.0
    ) -> bool:
        """
        Add message to session
        
        Args:
            session_id: Session ID
            role: "user" or "assistant"
            content: Message content
            severity_level: Optional severity level
            severity_score: Optional severity score
        
        Returns:
            True if successful, False if session not found
        """
        session = self.get_session(session_id)
        
        if session:
            session.add_message(role, content, severity_level, severity_score)
            logger.info(f"📝 Message added to session {session_id}: [{role}] {content[:50]}...")
            return True
        
        logger.warning(f"⚠️ Session not found: {session_id}")
        return False
    
    def end_session(self, session_id: str) -> bool:
        """
        End a session (mark as inactive)
        
        Args:
            session_id: Session ID
        
        Returns:
            True if successful, False if not found
        """
        session = self.sessions.get(session_id)
        
        if session:
            session.is_active = False
            del self.sessions[session_id]
            logger.info(f"🛑 Session ended: {session_id}")
            return True
        
        return False
    
    def get_all_sessions(self) -> List[Dict]:
        """
        Get all active sessions (for admin/debugging)
        
        Returns:
            List of session dictionaries
        """
        return [s.to_dict() for s in self.sessions.values()]
    
    def cleanup_expired_sessions(self):
        """Remove all expired sessions"""
        expired_ids = []
        
        for session_id, session in self.sessions.items():
            if not self._is_session_valid(session):
                expired_ids.append(session_id)
        
        for session_id in expired_ids:
            del self.sessions[session_id]
            logger.info(f"🗑️ Expired session removed: {session_id}")
        
        if expired_ids:
            logger.info(f"🧹 Cleaned up {len(expired_ids)} expired sessions")
    
    def _is_session_valid(self, session: ChatSession) -> bool:
        """Check if session is still valid (not expired)"""
        if not session.is_active:
            return False
        
        now = datetime.utcnow()
        time_since_activity = now - session.last_activity
        
        return time_since_activity < self.session_expiry
    
    def _cleanup_expired_sessions(self):
        """Start background cleanup (for production, use scheduler)"""
        # In production, call cleanup_expired_sessions() periodically
        pass


# ============================================================================
# SESSION MANAGER INSTANCE
# ============================================================================

_session_manager: Optional[SessionManager] = None

def get_session_manager() -> SessionManager:
    """Get singleton SessionManager instance"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(session_expiry_minutes=30)
    return _session_manager


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_session(user_id: str = "", language: str = "en") -> ChatSession:
    """Create a new session"""
    manager = get_session_manager()
    return manager.create_session(user_id, language)


def get_session(session_id: str) -> Optional[ChatSession]:
    """Get session by ID"""
    manager = get_session_manager()
    return manager.get_session(session_id)


def add_message(
    session_id: str,
    role: str,
    content: str,
    severity_level: str = "",
    severity_score: float = 0.0
) -> bool:
    """Add message to session"""
    manager = get_session_manager()
    return manager.add_message(session_id, role, content, severity_level, severity_score)


def get_history(session_id: str) -> Optional[Dict]:
    """Get session history"""
    manager = get_session_manager()
    return manager.get_session_history(session_id)


# ============================================================================
# TEST THE SESSION MANAGER
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("🧪 Testing Session Manager")
    print("=" * 70)
    
    # Create session
    session = create_session(language="en")
    print(f"\n✅ Created session: {session.session_id}")
    
    # Add messages
    add_message(session.session_id, "user", "I have a headache")
    add_message(
        session.session_id, 
        "assistant", 
        "You said: I have a headache. Severity: MILD",
        severity_level="MILD",
        severity_score=3.0
    )
    add_message(session.session_id, "user", "What should I do?")
    
    # Get history
    history = get_history(session.session_id)
    print(f"\n📜 Session History:")
    print(f"   Messages: {history['message_count']}")
    for msg in history['messages']:
        print(f"   - [{msg['role']}]: {msg['content'][:50]}...")
    
    print("\n✅ Session manager working correctly!")
    print("=" * 70)