"""
Chat Service - Handle all chat-related operations
Works with SQLAlchemy ORM models (ChatMessage, ChatSession, User)

File: backend/app/services/chat_service.py
"""

import logging
import uuid
import httpx
from datetime import datetime
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.models import ChatSession, ChatMessage, User
from config import settings

logger = logging.getLogger(__name__)


class ChatService:
    """
    Chat service for managing chat sessions and messages
    Works with SQLAlchemy ORM models
    
    Features:
    - Browser session creation (user + session per tab)
    - Session restoration on page reload
    - Session closure on tab close
    - Message persistence with AI responses
    - Session analytics
    """

    def __init__(self, db: Session):
        """Initialize chat service with database session"""
        self.db = db
        self.session_expiry = getattr(settings, 'SESSION_EXPIRY_MINUTES', 30)

    # ========================================================================
    # BROWSER SESSION MANAGEMENT
    # ========================================================================

    def create_browser_session(self, user_id: int = None, language: str = "en") -> Optional[Dict]:
        """
        Create new browser session (when user opens Chrome tab)
        
        Creates:
        - User (if needed)
        - Session (linked to user)
        
        Args:
            user_id: Optional user ID, creates new if not provided
            language: Language preference (en, hi, etc.)
            
        Returns:
            {
                "user_id": int,
                "session_id": "uuid-xxx",
                "language": "en",
                "created_at": "2026-02-25T...",
                "status": "active"
            }
        """
        try:
            logger.info("🌐 Creating new browser session...")
            
            # Create or get user
            if not user_id:
                # Create new user
                user = User(
                    email=f"user_{uuid.uuid4()}@example.com",
                    password_hash="not_set",  # No password for guest
                    name=f"User {str(uuid.uuid4())[:8]}",
                    age=30,  # Default age
                )
                self.db.add(user)
                self.db.commit()
                self.db.refresh(user)
                user_id = user.id
                logger.info(f"✅ New user created: {user_id}")
            else:
                # Verify user exists
                user = self.db.query(User).filter(User.id == user_id).first()
                if not user:
                    logger.warning(f"⚠️ User not found: {user_id}")
                    return None
            
            # Create session
            session_id = str(uuid.uuid4())
            session = ChatSession(
                user_id=user_id,
                session_id=session_id,
                is_active=True
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            
            logger.info(f"✅ Session created: {session_id}")
            
            return {
                "user_id": user_id,
                "session_id": session_id,
                "language": language,
                "created_at": session.created_at.isoformat() if session.created_at else datetime.utcnow().isoformat(),
                "status": "active"
            }
            
        except Exception as e:
            logger.error(f"❌ Error creating browser session: {e}", exc_info=True)
            self.db.rollback()
            return None

    def restore_browser_session(self, user_id: int, session_id: str) -> Optional[Dict]:
        """
        Restore existing session on page reload
        
        Checks if:
        - User exists
        - Session exists and is_active = True
        
        Args:
            user_id: User ID
            session_id: Session UUID
            
        Returns:
            Session dict if active, None otherwise
        """
        try:
            logger.info(f"🔄 Restoring session: {session_id[:8]}...")
            
            # Check user exists
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning(f"⚠️ User not found: {user_id}")
                return None
            
            # Check session exists and is active
            session = self.db.query(ChatSession).filter(
                ChatSession.session_id == session_id,
                ChatSession.is_active == True
            ).first()
            
            if not session:
                logger.warning(f"⚠️ Session not found or inactive: {session_id}")
                return None
            
            logger.info(f"✅ Session restored: {session_id[:8]}...")
            
            return {
                "user_id": user_id,
                "session_id": session_id,
                "language": "en",
                "status": "active"
            }
            
        except Exception as e:
            logger.error(f"❌ Error restoring session: {e}", exc_info=True)
            return None

    def close_browser_session(self, session_id: str) -> bool:
        """
        Close browser session (when user closes Chrome tab)
        
        Actions:
        - Add final "session closed" message
        - Deactivate session
        
        Args:
            session_id: Session UUID
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"❌ Closing session: {session_id[:8]}...")
            
            session = self.db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()
            
            if not session:
                logger.warning(f"⚠️ Session not found: {session_id}")
                return False
            
            # Add system message
            closing_message = ChatMessage(
                session_id=session.id,
                user_id=session.user_id,
                message_type="system",
                content="Session closed"
            )
            self.db.add(closing_message)
            
            # Deactivate session
            session.is_active = False
            self.db.add(session)
            self.db.commit()
            
            logger.info(f"✅ Session closed: {session_id[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error closing session: {e}", exc_info=True)
            self.db.rollback()
            return False

    # ========================================================================
    # MESSAGE PROCESSING & AI
    # ========================================================================

    async def process_message(self, user_id: int, content: str) -> dict:
        """
        Process a user message and generate AI response
        
        Args:
            user_id: User ID
            content: User message content
            
        Returns:
            dict with session_id, message, and timestamp
        """
        try:
            logger.info(f"💬 Processing message for user {user_id}...")
            
            # Get or create session
            session = self.db.query(ChatSession).filter(
                ChatSession.user_id == user_id,
                ChatSession.is_active == True
            ).order_by(desc(ChatSession.created_at)).first()
            
            if not session:
                logger.warning(f"⚠️ No active session for user {user_id}, creating new one")
                # Create new session
                session_id = str(uuid.uuid4())
                session = ChatSession(
                    user_id=user_id,
                    session_id=session_id,
                    is_active=True
                )
                self.db.add(session)
                self.db.commit()
                self.db.refresh(session)
            
            # Save user message
            user_message = ChatMessage(
                session_id=session.id,
                user_id=user_id,
                message_type="user",
                content=content
            )
            self.db.add(user_message)
            self.db.flush()
            
            logger.info(f"💬 User message saved: {user_message.id}")
            
            # Generate AI response
            ai_response_text = await self._query_llm(content)
            
            # Save AI response
            ai_message = ChatMessage(
                session_id=session.id,
                user_id=user_id,
                message_type="assistant",
                content=ai_response_text
            )
            self.db.add(ai_message)
            self.db.flush()
            
            # Update session timestamp
            session.updated_at = datetime.utcnow()
            self.db.add(session)
            
            # Commit all
            self.db.commit()
            self.db.refresh(ai_message)
            
            logger.info(f"✅ Message processed successfully")
            
            return {
                "session_id": session.session_id,
                "message": ai_response_text,
                "timestamp": ai_message.created_at.isoformat() if ai_message.created_at else datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def _query_llm(self, prompt: str) -> str:
        """
        Query LLM with fallback chain:
        1. Mock Service (for testing)
        2. Hugging Face (if configured)
        3. Gemini (if configured)
        4. Local LLM (Ollama-like)
        
        Args:
            prompt: User input prompt
            
        Returns:
            AI response text
        """
        try:
            # 1) Mock Service (for testing/development)
            if getattr(settings, 'USE_MOCK', False):
                try:
                    from app.services.mock_service import MockService
                    response = await MockService().generate_response(prompt)
                    logger.info("✅ Response from Mock Service")
                    return response
                except Exception as e:
                    logger.warning(f"⚠️ Mock service failed: {str(e)}")

            # 2) Hugging Face
            hf_enabled = getattr(settings, 'USE_HUGGINGFACE', False)
            hf_key = getattr(settings, 'HUGGINGFACE_API_KEY', None)
            if hf_enabled and hf_key:
                try:
                    from app.services.huggingface_service import HuggingFaceService
                    hf_model = getattr(settings, 'HUGGINGFACE_MODEL', 'gpt2')
                    hf = HuggingFaceService(api_key=hf_key, model=hf_model)
                    response = await hf.generate_response(prompt)
                    logger.info("✅ Response from Hugging Face")
                    return response
                except Exception as e:
                    logger.warning(f"⚠️ Hugging Face call failed: {str(e)}")

            # 3) Gemini
            gemini_enabled = getattr(settings, 'USE_GEMINI', False)
            gemini_key = getattr(settings, 'GEMINI_API_KEY', None)
            if gemini_enabled and gemini_key:
                try:
                    from app.services.gemini_service import GeminiService
                    gemini = GeminiService(api_key=gemini_key)
                    response = await gemini.generate_response(prompt)
                    logger.info("✅ Response from Gemini")
                    return response
                except Exception as e:
                    logger.warning(f"⚠️ Gemini call failed: {str(e)}")

            # 4) Local LLM (Ollama-like)
            local_llm_enabled = getattr(settings, 'USE_LOCAL_LLM', False)
            llm_url = getattr(settings, 'LLM_API_URL', None)
            if local_llm_enabled or llm_url:
                try:
                    llm_url = llm_url or 'http://localhost:11434/api/generate'
                    llm_model = getattr(settings, 'LLM_MODEL_NAME', 'llama2')
                    
                    payload = {
                        "model": llm_model,
                        "prompt": prompt,
                        "stream": False
                    }
                    
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        logger.info(f"🤖 Querying local LLM at {llm_url}")
                        response = await client.post(llm_url, json=payload)
                        
                        if response.status_code == 200:
                            data = response.json()
                            result = data.get("response", data.get("content", ""))
                            logger.info("✅ Response from Local LLM")
                            return result if result else "Local LLM returned empty response"
                        else:
                            logger.error(f"❌ Local LLM returned {response.status_code}")
                            return f"Local LLM error: {response.status_code}"
                except Exception as e:
                    logger.warning(f"⚠️ Local LLM query failed: {str(e)}")

            # Fallback: No provider available
            logger.error("❌ No AI provider configured")
            return "No AI provider configured. Please enable Hugging Face, Gemini, or a local LLM in settings."

        except Exception as e:
            logger.error(f"❌ Unexpected error in _query_llm: {str(e)}", exc_info=True)
            return f"Error querying AI provider: {str(e)}"

    # ========================================================================
    # CHAT HISTORY
    # ========================================================================

    def get_chat_history(self, user_id: int, limit: int = 50) -> List[ChatMessage]:
        """
        Get chat history for a user
        
        Args:
            user_id: User ID
            limit: Maximum number of messages to return
            
        Returns:
            List of ChatMessage objects
        """
        try:
            messages = self.db.query(ChatMessage).filter(
                ChatMessage.user_id == user_id
            ).order_by(desc(ChatMessage.created_at)).limit(limit).all()
            
            logger.info(f"✅ Retrieved {len(messages)} messages for user {user_id}")
            return messages[::-1]  # Reverse to show oldest first
            
        except Exception as e:
            logger.error(f"❌ Error getting chat history: {e}", exc_info=True)
            return []

    def get_session_history(self, session_id: str, limit: int = 50) -> Optional[Dict]:
        """
        Get full session history with messages
        
        Args:
            session_id: Session UUID
            limit: Maximum number of messages
            
        Returns:
            Dictionary with session info and messages
        """
        try:
            session = self.db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()
            
            if not session:
                logger.warning(f"⚠️ Session not found: {session_id}")
                return None
            
            messages = self.db.query(ChatMessage).filter(
                ChatMessage.session_id == session.id
            ).order_by(ChatMessage.created_at).limit(limit).all()
            
            logger.info(f"✅ Retrieved {len(messages)} messages for session {session_id[:8]}...")
            
            return {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "is_active": session.is_active,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "message_count": len(messages),
                "messages": [
                    {
                        "id": msg.id,
                        "message_type": msg.message_type,
                        "content": msg.content,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None
                    }
                    for msg in messages
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting session history: {e}", exc_info=True)
            return None

    def end_session(self, session_id: str) -> bool:
        """
        End/deactivate a session
        
        Args:
            session_id: Session UUID
            
        Returns:
            True if successful
        """
        try:
            session = self.db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()
            
            if not session:
                logger.warning(f"⚠️ Session not found: {session_id}")
                return False
            
            session.is_active = False
            self.db.add(session)
            self.db.commit()
            
            logger.info(f"✅ Session ended: {session_id[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error ending session: {e}", exc_info=True)
            self.db.rollback()
            return False

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_session_stats(self, session_id: str) -> Dict:
        """
        Get statistics for a session
        
        Args:
            session_id: Session UUID
            
        Returns:
            Dictionary with session statistics
        """
        try:
            session = self.db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()
            
            if not session:
                return {"error": "Session not found"}
            
            messages = self.db.query(ChatMessage).filter(
                ChatMessage.session_id == session.id
            ).all()
            
            user_msgs = len([m for m in messages if m.message_type == "user"])
            assistant_msgs = len([m for m in messages if m.message_type == "assistant"])
            
            return {
                "session_id": session_id,
                "user_id": session.user_id,
                "is_active": session.is_active,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "total_messages": len(messages),
                "user_messages": user_msgs,
                "assistant_messages": assistant_msgs
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting session stats: {e}", exc_info=True)
            return {"error": str(e)}