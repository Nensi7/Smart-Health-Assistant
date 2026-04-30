"""
Smart Health Assistant - Main Application
FastAPI backend server with proper initialization
File: backend/main.py
"""

# ============================================================================
# STEP 1: CONFIGURE LOGGING (MUST BE FIRST!)
# ============================================================================

import logging

# Create logger for this module
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger.info("🚀 Initializing Smart Health Assistant...")

# ============================================================================
# STEP 2: IMPORT FASTAPI AND CREATE APP (MUST BE BEFORE USING IT!)
# ============================================================================

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import socket

# ============================================================================
# STEP 3: IMPORT DATABASE & ROUTES
# ============================================================================

from app.routes import appointments

logger.info("📦 Importing database module...")
from app.database import init_db, engine

logger.info("📦 Importing route modules...")
from app.routes.chat import router as chat_router

# Add other route imports as they're created:
try:
    from app.routes.triage import router as triage_router
    logger.info("✅ Triage routes available")
except ImportError:
    logger.warning("⚠️ Triage routes not found (optional)")
    triage_router = None

try:
    from app.routes.health_tips import router as health_tips_router
    logger.info("✅ Health tips routes available")
except ImportError:
    logger.warning("⚠️ Health tips routes not found (optional)")
    health_tips_router = None

try:
    from app.routes.healthcare import router as healthcare_router
    logger.info("✅ Healthcare routes available")
except ImportError:
    logger.warning("⚠️ Healthcare routes not found (optional)")
    healthcare_router = None

try:
    from app.routes.voice import router as voice_router
    logger.info("✅ Voice routes available")
except ImportError:
    logger.warning("⚠️ Voice routes not found (optional)")
    voice_router = None

try:
    from app.routes.feedback import router as feedback_router
    logger.info("✅ Feedback routes available")
except ImportError:
    logger.warning("⚠️ Feedback routes not found (optional)")
    feedback_router = None

# ============================================================================
# STEP 4: DEFINE STARTUP/SHUTDOWN EVENTS
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle startup and shutdown events
    """
    # ======================== STARTUP ========================
    logger.info("🚀 Application startup event triggered...")
    
    try:
        # Initialize database on startup
        init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
    
    logger.info("✅ Application startup complete!")
    
    yield
    
    # ======================== SHUTDOWN ========================
    logger.info("🛑 Application shutdown event triggered...")
    logger.info("🔌 Closing database connections...")
    engine.dispose()
    logger.info("✅ Database connections closed")
    logger.info("✅ Application shutdown complete!")

# ============================================================================
# STEP 5: CREATE FASTAPI APP (NOW WE CAN USE IT!)
# ============================================================================

logger.info("⚙️ Creating FastAPI application...")

app = FastAPI(
    title="Smart Health Assistant API",
    description="AI-Powered Bilingual Health Education Platform",
    version="1.0.0",
    lifespan=lifespan
)

logger.info("✅ FastAPI application created successfully")

# ============================================================================
# STEP 6: ADD CORS MIDDLEWARE (ALLOWS FRONTEND ACCESS)
# ============================================================================

"""
CORS (Cross-Origin Resource Sharing) is CRITICAL for frontend-backend communication.

WITHOUT THIS:
- Browser blocks requests from React (http://localhost:3000)
- Frontend gets "CORS error" in console
- Backend works, but frontend can't reach it

WITH THIS:
- Frontend (http://localhost:3000) can make requests to backend (http://localhost:8000)
- All HTTP methods allowed
- All headers allowed
"""

logger.info("⚙️ Configuring CORS middleware...")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",       # React dev server
        "http://127.0.0.1:3000",       # Alternative localhost
        "http://localhost:5173",       # Vite dev server
        "http://127.0.0.1:5173",       # Alternative Vite
        "http://localhost:8000",       # Backend itself
        "*"                            # Allow all (for development)
    ],
    allow_credentials=True,             # Allow cookies/auth
    allow_methods=["*"],                # Allow GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],                # Allow all headers (Content-Type, etc.)
    expose_headers=["X-Process-Time"]   # Expose custom headers
)

logger.info("✅ CORS middleware configured")

# ============================================================================
# STEP 7: INCLUDE ROUTE MODULES
# ============================================================================

logger.info("⚙️ Registering route modules...")

# Appointments routes
app.include_router(appointments.router)
logger.info("✅ Appointments routes registered")

# Chat routes (REQUIRED)
app.include_router(chat_router)
logger.info("✅ Chat routes registered")

# Optional routes (only if available)
if triage_router:
    app.include_router(triage_router)
    logger.info("✅ Triage routes registered")

if health_tips_router:
    app.include_router(health_tips_router)
    logger.info("✅ Health tips routes registered")

if healthcare_router:
    app.include_router(healthcare_router)
    logger.info("✅ Healthcare routes registered")

if voice_router:
    app.include_router(voice_router)
    logger.info("✅ Voice routes registered")

if feedback_router:
    app.include_router(feedback_router)
    logger.info("✅ Feedback routes registered")

# ============================================================================
# STEP 8: HEALTH CHECK ENDPOINTS
# ============================================================================

@app.get("/", tags=["System"])
async def root(request: Request):
    """
    Root endpoint - Returns API information
    Uses the incoming request host and port to build active URLs.
    """
    base_url = str(request.base_url).rstrip("/")
    return {
        "name": "Smart Health Assistant API",
        "version": "1.0.0",
        "status": "active",
        "message": "🏥 AI-Powered Bilingual Health Education Platform",
        "backend_url": base_url,
        "endpoints": {
            "docs": f"{base_url}/docs",
            "redoc": f"{base_url}/redoc",
            "openapi": f"{base_url}/openapi.json",
            "health": f"{base_url}/health",
            "info": f"{base_url}/api/info"
        }
    }


@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint
    Returns server status
    Used by load balancers and monitoring
    Access: http://localhost:8000/health
    """
    return {
        "status": "ok",
        "service": "Smart Health Assistant",
        "version": "1.0.0",
        "database": "connected",
        "timestamp": "2026-02-28"
    }


@app.get("/api/info", tags=["System"])
async def api_info():
    """
    API information endpoint
    Returns available features and endpoints
    Access: http://localhost:8000/api/info
    """
    return {
        "api_name": "Smart Health Assistant",
        "version": "1.0.0",
        "status": "active",
        "description": "AI-Powered Bilingual Health Education Platform",
        "features": [
            "Chat with AI assistant",
            "Symptom severity assessment",
            "Emergency detection",
            "Voice input/output",
            "Healthcare facility search",
            "User feedback collection",
            "Bilingual support (English & Hindi)"
        ],
        "languages": ["en", "hi"],
        "endpoints_available": {
            "chat": "/api/chat",
            "triage": "/api/triage (if created)",
            "health_tips": "/api/health-tips (if created)",
            "healthcare": "/api/healthcare (if created)",
            "voice": "/api/voice (if created)",
            "feedback": "/api/feedback (if created)"
        },
        "documentation": "Visit http://localhost:8000/docs for interactive API documentation"
    }

# ============================================================================
# STEP 9: ERROR HANDLERS
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler - catches all unhandled exceptions
    """
    logger.error(f"❌ Unhandled exception: {str(exc)}", exc_info=True)
    return {
        "status": "error",
        "message": str(exc),
        "type": type(exc).__name__
    }

# ============================================================================
# STEP 10: REQUEST/RESPONSE LOGGING MIDDLEWARE
# ============================================================================

@app.middleware("http")
async def log_requests(request, call_next):
    """
    Log all HTTP requests and responses
    """
    # Log incoming request
    logger.info(f"📝 {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Log response
    logger.info(f"✅ {response.status_code} {request.method} {request.url.path}")
    
    # Add custom header
    response.headers["X-Process-Time"] = "1.0"
    
    return response

# ============================================================================
# STEP 11: RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    def find_available_port(start_port: int, max_port: int = 8100) -> int:
        """Find the first available port starting from start_port."""
        for port in range(start_port, max_port + 1):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(("0.0.0.0", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError(f"No available ports between {start_port} and {max_port}")

    logger.info("=" * 80)
    logger.info("🎬 STARTING UVICORN SERVER")
    logger.info("=" * 80)

    base_port = int(os.getenv("PORT", "8000"))
    port = find_available_port(base_port)
    backend_host = os.getenv("BACKEND_HOST", "localhost")
    backend_url = f"http://{backend_host}:{port}"
    docs_url = f"{backend_url}/docs"
    api_info_url = f"{backend_url}/api/info"

    if port != base_port:
        logger.warning(f"⚠️ Port {base_port} in use. Starting on fallback port {port}.")

    logger.info(f"📍 Backend active URL: {backend_url}")
    logger.info(f"📚 Interactive docs available at: {docs_url}")
    logger.info(f"🏥 API info available at: {api_info_url}")
    logger.info("=" * 80)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )