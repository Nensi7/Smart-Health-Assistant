"""
Chat Route - FIXED VERSION
File: backend/app/routes/chat.py

Complete chat implementation with proper database storage for all messages
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import logging
import uuid
from app.database import (
    get_db, store_chat_message, create_or_get_user, 
    create_chat_session, get_session_messages, close_chat_session, get_session_by_id
)
from sqlalchemy.orm import Session
from app.services.nlp_processor import extract_symptoms, detect_language
from app.services.triage_engine import assess_severity
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat"])

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class MessageRequest(BaseModel):
    user_id: str
    session_id: str
    message: str
    language: Optional[str] = "en"

class SessionRequest(BaseModel):
    user_id: Optional[str] = None
    language: Optional[str] = "en"

class ResponseRequest(BaseModel):
    session_id: str
    user_id: str
    response: str
    language: Optional[str] = "en"

class CloseSessionRequest(BaseModel):
    user_id: str
    session_id: str

class ChatMessage(BaseModel):
    id: int
    session_id: str
    user_id: str
    message_text: str
    sender_type: str
    timestamp: str


def _is_greeting_or_smalltalk(text: str) -> bool:
    text_lower = text.strip().lower()
    greeting_tokens = {
        "hi", "hello", "hey", "hii", "good morning", "good evening", "good afternoon",
        "namaste", "नमस्ते"
    }
    return any(token == text_lower or token in text_lower for token in greeting_tokens)


def _build_triage_assistant_reply(triage_result, language: str) -> str:
    disclaimer_en = "This is educational information only, not medical advice."
    disclaimer_hi = "यह केवल शैक्षणिक जानकारी है, चिकित्सा सलाह नहीं।"
    disclaimer = disclaimer_hi if language == "hi" else disclaimer_en

    level = triage_result.severity_level.value.upper()
    score = triage_result.severity_score
    suggestions = triage_result.home_care_suggestions[:3]
    suggestion_text = ", ".join(suggestions) if suggestions else "monitor your symptoms closely"

    if language == "hi":
        return (
            f"Severity: {level} ({score}/10)। {triage_result.recommendation} "
            f"घरेलू देखभाल: {suggestion_text}. {disclaimer}"
        )

    return (
        f"Severity: {level} ({score}/10). {triage_result.recommendation} "
        f"Home care: {suggestion_text}. {disclaimer}"
    )

# ============================================================================
# ROUTES
# ============================================================================

@router.post("/session/start", summary="Start a new chat session")
async def start_session(request: SessionRequest, db: Session = Depends(get_db)):
    """Start a new chat session"""
    try:
        # Generate a user ID automatically if not provided
        external_id = request.user_id or f"user_{uuid.uuid4().hex[:12]}"

        # ✅ Create or get user
        user = create_or_get_user(
            db=db,
            external_id=external_id,
            language=request.language
        )
        
        # ✅ Create session
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        session = create_chat_session(
            db=db,
            user_id=user.id,
            session_id=session_id
        )
        
        logger.info(f"✅ Session started: {session_id}")
        
        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "user_id": user.external_id,
                "status": "active",
                "created_at": session.created_at.isoformat()
            }
        }
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/init", summary="Initialize or restore a chat session")
async def init_session(request: SessionRequest, db: Session = Depends(get_db)):
    """Initialize a new chat session with optional user ID"""
    return await start_session(request, db)

@router.post("/send", summary="Send a chat message")
async def send_message_compat(request: MessageRequest, db: Session = Depends(get_db)):
    """Compatibility handler for legacy chat clients"""
    return await send_message(request, db)

@router.post("/close-session", summary="Close a chat session")
async def close_session_compat(request: CloseSessionRequest, db: Session = Depends(get_db)):
    """Compatibility handler to close a chat session"""
    return await end_session(request.session_id, request.user_id, db)

@router.get("/history/{session_id}", summary="Get chat history for compatibility")
async def get_session_history(session_id: str, user_id: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db)):
    """Get session history without requiring legacy client-specific query parameters"""
    try:
        session = get_session_by_id(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if user_id:
            user = create_or_get_user(db, user_id)
            if str(session.user_id) != str(user.id):
                raise HTTPException(status_code=403, detail="Unauthorized access")

        messages = get_session_messages(db, session.id, limit)
        message_list = [
            {
                "id": msg.id,
                "session_id": session_id,
                "user_id": msg.user_id,
                "message_text": msg.content,
                "sender_type": msg.message_type,
                "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                "language": session.user.language.value if session.user and session.user.language else "en"
            }
            for msg in messages
        ]

        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "total_messages": len(message_list),
                "messages": message_list
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting session history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch session history")

@router.post("/message/send", summary="Send a chat message")
async def send_message(request: MessageRequest, db: Session = Depends(get_db)):
    """Send a chat message"""
    try:
        # ✅ Get session
        session = get_session_by_id(db, request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # ✅ Store user message
        message = store_chat_message(
            db=db,
            session_id=session.id,
            user_id=session.user_id,
            content=request.message,
            message_type="user"
        )
        language = request.language or detect_language(request.message)

        # Run NLP + triage for symptom-aware response
        symptom_matches = extract_symptoms(request.message, language=language)
        triage_result = assess_severity(
            symptoms=symptom_matches,
            language=language,
            raw_text=request.message,
        )

        # Build assistant response:
        # - Greeting/smalltalk -> conversational response
        # - Symptom-like message -> triage educational summary
        if _is_greeting_or_smalltalk(request.message):
            if language == "hi":
                assistant_text = (
                    "नमस्ते! मैं आपकी मदद के लिए यहां हूं। "
                    "आप कैसा महसूस कर रहे हैं? अपने लक्षण सरल शब्दों में बताइए, "
                    "मैं आपकी स्थिति समझने में मदद करूंगा।"
                )
            else:
                assistant_text = (
                    "Hi! I am here to help. "
                    "How are you feeling today? Share your symptoms in simple words, "
                    "and I will guide you step by step."
                )
        elif symptom_matches:
            assistant_text = _build_triage_assistant_reply(triage_result, language)
        else:
            chat_service = ChatService(db)
            assistant_text = await chat_service._query_llm(request.message)

        assistant_message = store_chat_message(
            db=db,
            session_id=session.id,
            user_id=session.user_id,
            content=assistant_text,
            message_type="assistant",
        )

        return {
            "success": True,
            "data": {
                "message_id": message.id,
                "assistant_message_id": assistant_message.id,
                "assistant_response": assistant_text,
                "triage": triage_result.model_dump(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/response/send", summary="Send bot response")
async def send_response(request: ResponseRequest, db: Session = Depends(get_db)):
    """
    Store bot response message in database
    """
    try:
        # Validate inputs
        if not request.session_id or not request.user_id or not request.response.strip():
            raise HTTPException(
                status_code=400,
                detail="session_id, user_id, and response are required"
            )

        # Get user
        user = create_or_get_user(db, request.user_id)

        # Get session
        session = get_session_by_id(db, request.session_id)
        if not session or session.user_id != user.id:
            raise HTTPException(
                status_code=404,
                detail="Session not found"
            )

        # Store bot message
        message = store_chat_message(
            db=db,
            session_id=session.id,
            user_id=user.id,
            content=request.response.strip(),
            message_type="assistant"
        )

        logger.info(f"✅ Bot response stored for session {request.session_id}")

        return {
            "success": True,
            "data": {
                "session_id": request.session_id,
                "response_stored": True,
                "timestamp": datetime.now().isoformat()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error storing response: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store response: {str(e)}"
        )

@router.get("/session/{session_id}/messages", summary="Get session messages")
async def get_messages(session_id: str, user_id: str, limit: int = 100, db: Session = Depends(get_db)):
    """
    Get all messages in a session
    
    Path Parameters:
    - session_id: Session ID (required)
    
    Query Parameters:
    - user_id: User ID for verification (required)
    - limit: Maximum messages to return (default: 100)
    """
    try:
        # Get user
        user = create_or_get_user(db, user_id)
        
        # Verify session ownership
        session = get_session_by_id(db, session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if str(session.user_id) != str(user.id):
            raise HTTPException(status_code=403, detail="Unauthorized access")
        
        # Get messages
        messages = get_session_messages(db, session.id, limit)
        
        # Convert to dict format
        message_list = [
            {
                "id": msg.id,
                "session_id": session_id,
                "user_id": user_id,
                "message_text": msg.content,
                "sender_type": msg.message_type,
                "timestamp": msg.created_at.isoformat(),
                "language": user.language.value if user.language else "en"
            }
            for msg in messages
        ]
        
        logger.info(f"✅ Retrieved {len(message_list)} messages for session {session_id}")
        
        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "total_messages": len(message_list),
                "messages": message_list
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting messages: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch messages"
        )

@router.post("/session/{session_id}/end", summary="End a chat session")
async def end_session(session_id: str, user_id: str, db: Session = Depends(get_db)):
    """
    End a chat session
    
    Path Parameters:
    - session_id: Session ID to end (required)
    
    Query Parameters:
    - user_id: User ID for verification (required)
    """
    try:
        # Get user
        user = create_or_get_user(db, user_id)
        
        # Verify session ownership
        session = get_session_by_id(db, session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if str(session.user_id) != str(user.id):
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Close session
        close_chat_session(db, session_id)
        
        logger.info(f"✅ Chat session ended: {session_id}")
        
        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "status": "ended",
                "ended_at": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error ending session: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to end session"
        )

@router.get("/user/{user_id}/history", summary="Get user's chat history")
async def get_chat_history(user_id: str, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    """
    Get user's chat history (sessions and messages)
    
    Path Parameters:
    - user_id: User ID (required)
    
    Query Parameters:
    - limit: Number of sessions to return (default: 20)
    - offset: Pagination offset (default: 0)
    """
    try:
        # Get user
        user = create_or_get_user(db, user_id)
        
        # Get sessions with message counts
        from sqlalchemy import func
        from app.models.models import ChatSession, ChatMessage
        
        sessions_query = db.query(
            ChatSession,
            func.count(ChatMessage.id).label('message_count')
        ).outerjoin(ChatMessage, ChatSession.id == ChatMessage.session_id)\
         .filter(ChatSession.user_id == user.id)\
         .group_by(ChatSession.id)\
         .order_by(ChatSession.created_at.desc())\
         .limit(limit).offset(offset)
        
        results = sessions_query.all()
        
        session_data = [
            {
                "session_id": session.session_id,
                "user_id": user_id,
                "session_start": session.created_at.isoformat(),
                "session_end": None,  # Not tracking end time
                "status": "active" if session.is_active else "ended",
                "message_count": message_count
            }
            for session, message_count in results
        ]
        
        logger.info(f"✅ Retrieved chat history for user {user_id}")
        
        return {
            "success": True,
            "data": {
                "user_id": user_id,
                "total_sessions": len(session_data),
                "sessions": session_data
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting chat history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch chat history"
        )

@router.get("/health", summary="Health check")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        from app.models.models import ChatSession
        
        total_sessions = db.query(ChatSession).count()
        
        return {
            "success": True,
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "active_sessions": total_sessions
        }
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {str(e)}")
        return {
            "success": False,
            "status": "unhealthy",
            "error": str(e)
        }