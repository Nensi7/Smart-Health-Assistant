"""
Database Setup and Connection
SQLite database for Smart Health Assistant
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional
import os

logger = logging.getLogger(__name__)

# Database file path
DB_PATH = os.path.join(os.path.dirname(__file__), "smart_health.db")


def get_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database with all tables"""
    logger.info(f"📦 Initializing database at: {DB_PATH}")
    
    # Delete old database to start fresh
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        logger.info("🗑️ Removed old database")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create tables (without foreign keys to avoid issues)
    cursor.executescript("""
        -- Users table
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            language TEXT DEFAULT 'en',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        );
        
        -- Sessions table (NO foreign key to avoid mismatch)
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            user_id TEXT,
            language TEXT DEFAULT 'en',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        );
        
        -- Chat messages table
        CREATE TABLE chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            severity_level TEXT DEFAULT '',
            severity_score REAL DEFAULT 0.0,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Feedback table
        CREATE TABLE feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            helpful INTEGER,
            rating INTEGER,
            comments TEXT,
            language TEXT DEFAULT 'en',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create indexes for faster queries
        CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_messages_session_id ON chat_messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity);
    """)
    
    conn.commit()
    conn.close()
    
    logger.info("✅ Database initialized successfully")


def get_db():
    """Get database connection (for FastAPI dependency injection)"""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


class DatabaseManager:
    """Database manager for all operations"""
    
    @staticmethod
    def create_user(user_id: str, language: str = "en") -> Dict:
        """Create a new user"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, language)
                VALUES (?, ?)
            """, (user_id, language))
            
            conn.commit()
            
            # Get the created/updated user
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"❌ Error creating user: {e}")
            return None
        finally:
            conn.close()
    
    @staticmethod
    def create_session(user_id: str = "", language: str = "en") -> Dict:
        """Create a new session"""
        import uuid
        
        conn = get_connection()
        cursor = conn.cursor()
        
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        try:
            cursor.execute("""
                INSERT INTO sessions (session_id, user_id, language, created_at, last_activity)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, user_id, language, now, now))
            
            conn.commit()
            
            return {
                "session_id": session_id,
                "user_id": user_id,
                "language": language,
                "created_at": now,
                "last_activity": now
            }
        except Exception as e:
            logger.error(f"❌ Error creating session: {e}")
            return None
        finally:
            conn.close()
    
    @staticmethod
    def get_session(session_id: str) -> Optional[Dict]:
        """Get session by ID"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        return dict(row) if row else None
    
    @staticmethod
    def add_message(session_id: str, role: str, content: str, 
                   severity_level: str = "", severity_score: float = 0.0) -> bool:
        """Add message to session"""
        conn = get_connection()
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        try:
            cursor.execute("""
                INSERT INTO chat_messages (session_id, role, content, severity_level, severity_score, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, role, content, severity_level, severity_score, now))
            
            # Update session last_activity
            cursor.execute("""
                UPDATE sessions SET last_activity = ? WHERE session_id = ?
            """, (now, session_id))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Error adding message: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_session_history(session_id: str) -> Optional[Dict]:
        """Get full session history with messages"""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get session info
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        session_row = cursor.fetchone()
        
        if not session_row:
            conn.close()
            return None
        
        session = dict(session_row)
        
        # Get messages
        cursor.execute("""
            SELECT * FROM chat_messages 
            WHERE session_id = ? 
            ORDER BY timestamp ASC
        """, (session_id,))
        
        messages = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "session_id": session["session_id"],
            "user_id": session.get("user_id", ""),
            "language": session.get("language", "en"),
            "created_at": session["created_at"],
            "last_activity": session["last_activity"],
            "message_count": len(messages),
            "messages": messages
        }
    
    @staticmethod
    def get_all_sessions() -> List[Dict]:
        """Get all active sessions"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM sessions WHERE is_active = 1 ORDER BY last_activity DESC")
        sessions = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return sessions
    
    @staticmethod
    def submit_feedback(session_id: str, helpful: int, rating: int, 
                       comments: str = "", language: str = "en") -> bool:
        """Submit user feedback"""
        conn = get_connection()
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        try:
            cursor.execute("""
                INSERT INTO feedback (session_id, helpful, rating, comments, language, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, helpful, rating, comments, language, now))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Error submitting feedback: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def delete_session(session_id: str) -> bool:
        """Delete a session and all its messages"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Delete messages first
            cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            # Then delete session
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Error deleting session: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def cleanup_expired_sessions(hours: int = 24) -> int:
        """Delete sessions older than specified hours"""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Delete messages first
        cursor.execute("""
            DELETE FROM chat_messages 
            WHERE session_id IN (
                SELECT session_id FROM sessions 
                WHERE last_activity < datetime('now', ?)
            )
        """, (f"-{hours} hours",))
        
        # Delete sessions
        cursor.execute("""
            DELETE FROM sessions 
            WHERE last_activity < datetime('now', ?)
        """, (f"-{hours} hours",))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            logger.info(f"🧹 Cleaned up {deleted_count} expired sessions")
        
        return deleted_count


# ============================================================================
# TEST DATABASE
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("🧪 Testing Database")
    print("=" * 70)
    
    # Initialize database
    init_db()
    
    # Test create session
    print("\n📝 Creating test session...")
    session = DatabaseManager.create_session(language="en")
    print(f"✅ Session created: {session['session_id']}")
    
    # Test add messages
    print("\n💬 Adding test messages...")
    DatabaseManager.add_message(
        session['session_id'], 
        "user", 
        "I have a headache",
        severity_level="MILD",
        severity_score=3.0
    )
    DatabaseManager.add_message(
        session['session_id'],
        "assistant",
        "You said: I have a headache. Severity: MILD.",
        severity_level="MILD",
        severity_score=3.0
    )
    print("✅ Messages added")
    
    # Test get history
    print("\n📜 Getting session history...")
    history = DatabaseManager.get_session_history(session['session_id'])
    print(f"✅ Found {history['message_count']} messages")
    for msg in history['messages']:
        print(f"   - [{msg['role']}]: {msg['content'][:50]}...")
    
    # Test get all sessions
    print("\n📊 Getting all sessions...")
    all_sessions = DatabaseManager.get_all_sessions()
    print(f"✅ Total active sessions: {len(all_sessions)}")
    
    print("\n" + "=" * 70)
    print("✅ Database working correctly!")
    print(f"📁 Database file: {DB_PATH}")
    print("=" * 70)