"""
Session Service with Database Integration
Handles automatic session creation and chat history storage
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Import database
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.app.database import DatabaseManager

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ChatMessage:
    """Single chat message"""
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    severity_level: str = ""
    severity_score: float = 0.0

@dataclass
class ChatSession:
    """Chat session"""
    session_id: str
    user_id: str = ""
    language: str = "en"
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    messages: List[ChatMessage] = field(default_factory=list)
    
    def add_message(self, role: str, content: str, severity_level: str = "", severity_score: float = 0.0):
        """Add message to session"""
        self.messages.append(ChatMessage(
            role=role,
            content=content,
            severity_level=severity_level,
            severity_score=severity_score
        ))
        self.last_activity = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "language": self.language,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
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
# SESSION MIDDLEWARE
# ============================================================================

class SessionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Extracts session_id from cookie
    2. Creates new session in database if none exists
    3. Sets session cookie in response
    """
    
    COOKIE_NAME = "sha_session_id"
    
    async def dispatch(self, request: Request, call_next):
        # Get session_id from cookie
        session_id = request.cookies.get(self.COOKIE_NAME)
        
        # Verify session exists in database
        session_data = None
        if session_id:
            session_data = DatabaseManager.get_session(session_id)
        
        # Create new session if none exists or invalid
        if not session_data:
            session_data = DatabaseManager.create_session(language="en")
            if session_data:
                session_id = session_data["session_id"]
            else:
                # If database creation failed, create in-memory session
                session_id = str(uuid.uuid4())
                session_data = {
                    "session_id": session_id,
                    "user_id": "",
                    "language": "en"
                }
        
        # Store session_id in request state
        request.state.session_id = session_id
        request.state.session_data = session_data
        
        # Process request
        response = await call_next(request)
        
        # Set session cookie (expires when browser closes)
        response.set_cookie(
            key=self.COOKIE_NAME,
            value=session_id,
            httponly=True,
            samesite="lax"
        )
        
        return response


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_session_id(request: Request) -> str:
    """Get session ID from request"""
    return getattr(request.state, "session_id", "")

def get_session(request: Request) -> Optional[ChatSession]:
    """Get current session object"""
    session_id = get_session_id(request)
    if session_id:
        history = DatabaseManager.get_session_history(session_id)
        if history:
            session = ChatSession(
                session_id=history["session_id"],
                user_id=history.get("user_id", ""),
                language=history.get("language", "en"),
                created_at=datetime.fromisoformat(history["created_at"]),
                last_activity=datetime.fromisoformat(history["last_activity"])
            )
            # Add messages
            for msg in history.get("messages", []):
                session.messages.append(ChatMessage(
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=datetime.fromisoformat(msg["timestamp"]),
                    severity_level=msg.get("severity_level", ""),
                    severity_score=msg.get("severity_score", 0.0)
                ))
            return session
    return None

def add_message_to_session(request: Request, role: str, content: str,
                          severity_level: str = "", severity_score: float = 0.0) -> bool:
    """Add message to session (saves to database)"""
    session_id = get_session_id(request)
    if session_id:
        return DatabaseManager.add_message(session_id, role, content, severity_level, severity_score)
    return False

def get_session_history(request: Request) -> Optional[Dict]:
    """Get current session history from database"""
    session_id = get_session_id(request)
    if session_id:
        return DatabaseManager.get_session_history(session_id)
    return None

def clear_session(request: Request, response: Response) -> Response:
    """Clear session from database and cookie"""
    session_id = get_session_id(request)
    if session_id:
        DatabaseManager.delete_session(session_id)
    
    response = Response(content="Session cleared")
    response.set_cookie(
        key=SessionMiddleware.COOKIE_NAME,
        value="",
        httponly=True,
        samesite="lax",
        max_age=0,
    )
    return response


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("🧪 Testing Session Service with Database")
    print("=" * 70)
    
    # Test database operations
    print("\n📝 Creating session in database...")
    session = DatabaseManager.create_session(language="en")
    print(f"✅ Session created: {session['session_id']}")
    
    print("\n💬 Adding messages...")
    DatabaseManager.add_message(session['session_id'], "user", "I have a fever")
    DatabaseManager.add_message(session['session_id'], "assistant", 
                              "Severity: MODERATE. Rest and stay hydrated.",
                              severity_level="MODERATE", severity_score=5.0)
    
    print("\n📜 Getting history...")
    history = DatabaseManager.get_session_history(session['session_id'])
    print(f"✅ Found {history['message_count']} messages")
    for msg in history['messages']:
        print(f"   - [{msg['role']}]: {msg['content']}")
    
    print("\n📊 Getting all sessions...")
    all_sessions = DatabaseManager.get_all_sessions()
    print(f"✅ Total sessions: {len(all_sessions)}")
    
    print("\n" + "=" * 70)
    print("✅ Session service with database working!")
    print("=" * 70)