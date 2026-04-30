"""
Voice Routes - Speech-to-Text and Text-to-Speech endpoints
File: backend/app/routes/voice.py

This module handles all voice-related API endpoints:
- POST /api/voice/speech-to-text - Convert audio to text
- POST /api/voice/text-to-speech - Convert text to audio
- GET /api/voice/test - Health check for voice service
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging
from typing import Optional
from app.services.voice_service import (
    transcribe_audio,
    text_to_speech,
    analyze_voice_quality
)

logger = logging.getLogger(__name__)

# Create router with prefix and tags
router = APIRouter(prefix="/api/voice", tags=["voice"])

# ============================================================================
# PYDANTIC MODELS (Request/Response Validation)
# ============================================================================

class TextToSpeechRequest(BaseModel):
    """
    Request model for text-to-speech conversion
    
    Attributes:
        text: The text to convert to speech
        language: Language code ("en" for English, "hi" for Hindi)
    
    Example:
        {
            "text": "I have a fever",
            "language": "en"
        }
    """
    text: str
    language: str = "en"  # Default to English
    
    class Config:
        # Swagger UI example
        json_schema_extra = {
            "example": {
                "text": "I have a mild fever for two days",
                "language": "en"
            }
        }


class SpeechToTextResponse(BaseModel):
    """Response model for speech-to-text"""
    success: bool
    text: str
    confidence: float
    language: str
    duration: Optional[float] = None
    error: Optional[str] = None


class TextToSpeechResponse(BaseModel):
    """Response model for text-to-speech"""
    success: bool
    audio_base64: Optional[str] = None
    format: str = "mp3"
    duration_estimate: Optional[float] = None
    size_bytes: Optional[int] = None
    error: Optional[str] = None


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post(
    "/speech-to-text",
    response_model=SpeechToTextResponse,
    summary="Convert Speech to Text",
    description="Upload an audio file and get the text transcription"
)
async def convert_speech_to_text(
    audio_file: UploadFile = File(..., description="Audio file (WAV, MP3, FLAC, OGG)"),
    language: str = "en"  # Query parameter
):
    """
    Convert uploaded audio file to text (Speech-to-Text)
    
    **Supported Audio Formats:**
    - WAV (Recommended)
    - MP3
    - FLAC
    - OGG
    
    **Supported Languages:**
    - en: English (en-US)
    - hi: Hindi (hi-IN)
    
    **Args:**
        audio_file: Audio file to transcribe (multipart/form-data)
        language: Language of the audio ("en" or "hi")
    
    **Returns:**
        SpeechToTextResponse with transcribed text
    
    **Example (curl):**
        ```bash
        curl -X POST http://localhost:8000/api/voice/speech-to-text \\
          -F "audio_file=@audio.wav" \\
          -F "language=en"
        ```
    
    **Example (Python):**
        ```python
        import requests
        
        with open("audio.wav", "rb") as f:
            files = {"audio_file": f}
            params = {"language": "en"}
            response = requests.post(
                "http://localhost:8000/api/voice/speech-to-text",
                files=files,
                params=params
            )
        result = response.json()
        print(result["text"])
        ```
    """
    try:
        # ===== VALIDATION =====
        
        # Check if file was provided
        if not audio_file:
            logger.warning("❌ No audio file provided")
            raise HTTPException(
                status_code=400,
                detail="No audio file provided"
            )
        
        # Check file size (max 25MB)
        MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
        file_content = await audio_file.read()
        if len(file_content) > MAX_FILE_SIZE:
            logger.warning(f"❌ File too large: {len(file_content)} bytes")
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is 25MB"
            )
        
        # Check file is not empty
        if len(file_content) == 0:
            logger.warning("❌ Audio file is empty")
            raise HTTPException(
                status_code=400,
                detail="Audio file is empty"
            )
        
        # Validate audio format
        supported_formats = [
            "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp3",
            "audio/flac", "audio/ogg", "audio/x-flac"
        ]
        if audio_file.content_type not in supported_formats:
            logger.warning(f"❌ Unsupported audio format: {audio_file.content_type}")
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio format: {audio_file.content_type}. Supported: WAV, MP3, FLAC, OGG"
            )
        
        # Validate language
        if language not in ["en", "hi"]:
            logger.warning(f"❌ Invalid language: {language}")
            raise HTTPException(
                status_code=400,
                detail="Language must be 'en' (English) or 'hi' (Hindi)"
            )
        
        # ===== PROCESSING =====
        
        logger.info(f"📨 Transcribing audio ({audio_file.filename}) in {language}...")
        
        # Analyze audio quality first
        quality = analyze_voice_quality(file_content)
        logger.info(f"🎵 Audio quality: {quality.get('quality')} (score: {quality.get('score')})")
        
        # Warn if audio quality is poor but continue anyway
        if quality.get('score', 0) < 40:
            logger.warning(f"⚠️ Audio quality is poor: {quality.get('issues')}")
        
        # Transcribe audio
        result = transcribe_audio(file_content, language)
        
        # ===== RESPONSE =====
        
        if result.get("success"):
            logger.info(f"✅ Transcription successful: {result.get('text')}")
            return {
                "success": True,
                "text": result.get("text", ""),
                "confidence": result.get("confidence", 0.85),
                "language": language,
                "duration": result.get("duration"),
                "error": None
            }
        else:
            logger.warning(f"⚠️ Transcription failed: {result.get('error')}")
            return {
                "success": False,
                "text": "",
                "confidence": 0.0,
                "language": language,
                "error": result.get("error", "Could not transcribe audio")
            }
    
    except HTTPException as e:
        logger.error(f"❌ HTTPException: {e.detail}")
        return {
            "success": False,
            "text": "",
            "confidence": 0.0,
            "language": language,
            "error": e.detail
        }
    
    except Exception as e:
        logger.error(f"❌ Unexpected error in STT: {str(e)}", exc_info=True)
        return {
            "success": False,
            "text": "",
            "confidence": 0.0,
            "language": language,
            "error": f"Server error: {str(e)}"
        }


@router.post(
    "/text-to-speech",
    response_model=TextToSpeechResponse,
    summary="Convert Text to Speech",
    description="Convert text to audio speech"
)
async def convert_text_to_speech(request: TextToSpeechRequest):
    """
    Convert text to speech (Text-to-Speech)
    
    **Supported Languages:**
    - en: English
    - hi: Hindi
    
    **Args:**
        request: TextToSpeechRequest with text and language
    
    **Returns:**
        TextToSpeechResponse with base64 encoded MP3 audio
    
    **Example (curl):**
        ```bash
        curl -X POST http://localhost:8000/api/voice/text-to-speech \\
          -H "Content-Type: application/json" \\
          -d '{"text": "I have a fever", "language": "en"}'
        ```
    
    **Example (Python):**
        ```python
        import requests
        import base64
        
        data = {
            "text": "I have a fever and headache",
            "language": "en"
        }
        response = requests.post(
            "http://localhost:8000/api/voice/text-to-speech",
            json=data
        )
        result = response.json()
        
        if result["success"]:
            # Save audio file
            audio_data = base64.b64decode(result["audio_base64"])
            with open("output.mp3", "wb") as f:
                f.write(audio_data)
        else:
            print(f"Error: {result['error']}")
        ```
    """
    try:
        # ===== VALIDATION =====
        
        # Check text is provided
        if not request.text or len(request.text.strip()) == 0:
            logger.warning("❌ Text is empty")
            raise HTTPException(
                status_code=400,
                detail="Text cannot be empty"
            )
        
        # Check text length (max 5000 characters)
        if len(request.text) > 5000:
            logger.warning(f"❌ Text too long: {len(request.text)} chars")
            raise HTTPException(
                status_code=400,
                detail="Text too long. Maximum 5000 characters."
            )
        
        # Validate language
        if request.language not in ["en", "hi"]:
            logger.warning(f"❌ Invalid language: {request.language}")
            raise HTTPException(
                status_code=400,
                detail="Language must be 'en' (English) or 'hi' (Hindi)"
            )
        
        # ===== PROCESSING =====
        
        logger.info(f"🎤 Converting text to speech ({request.language})...")
        logger.info(f"📝 Text: {request.text[:100]}...")  # Log first 100 chars
        
        # Generate speech
        result = text_to_speech(request.text, request.language)
        
        # ===== RESPONSE =====
        
        if result.get("success"):
            logger.info(f"✅ TTS successful: {result.get('size_bytes')} bytes")
            return {
                "success": True,
                "audio_base64": result.get("audio_base64", ""),
                "format": result.get("format", "mp3"),
                "duration_estimate": result.get("duration_estimate"),
                "size_bytes": result.get("size_bytes"),
                "error": None
            }
        else:
            logger.warning(f"⚠️ TTS failed: {result.get('error')}")
            return {
                "success": False,
                "audio_base64": None,
                "format": "mp3",
                "error": result.get("error", "Could not generate speech")
            }
    
    except HTTPException as e:
        logger.error(f"❌ HTTPException: {e.detail}")
        return {
            "success": False,
            "audio_base64": None,
            "format": "mp3",
            "error": e.detail
        }
    
    except Exception as e:
        logger.error(f"❌ Unexpected error in TTS: {str(e)}", exc_info=True)
        return {
            "success": False,
            "audio_base64": None,
            "format": "mp3",
            "error": f"Server error: {str(e)}"
        }


@router.get(
    "/test",
    summary="Test Voice Service",
    description="Check if voice service is operational"
)
async def test_voice_service():
    """
    Test voice service health and capabilities
    
    **Returns:**
        dict: Service status and available features
    
    **Example:**
        ```bash
        curl http://localhost:8000/api/voice/test
        ```
    
    **Response:**
        ```json
        {
            "service": "voice",
            "status": "operational",
            "version": "1.0.0",
            "endpoints": [...],
            "supported_languages": {"en": "English", "hi": "Hindi"},
            "audio_formats_supported": ["WAV", "MP3", "FLAC", "OGG"],
            "max_file_size_mb": 25,
            "max_text_length": 5000
        }
        ```
    """
    logger.info("🧪 Voice service health check")
    
    return {
        "service": "voice",
        "status": "operational",
        "version": "1.0.0",
        "message": "Voice service is running properly",
        "endpoints": [
            {
                "method": "POST",
                "path": "/api/voice/speech-to-text",
                "description": "Convert audio to text",
                "supported_formats": ["WAV", "MP3", "FLAC", "OGG"]
            },
            {
                "method": "POST",
                "path": "/api/voice/text-to-speech",
                "description": "Convert text to audio"
            },
            {
                "method": "GET",
                "path": "/api/voice/test",
                "description": "Test voice service (this endpoint)"
            }
        ],
        "supported_languages": {
            "en": "English (en-US)",
            "hi": "Hindi (hi-IN)"
        },
        "audio_formats_supported": ["WAV", "MP3", "FLAC", "OGG"],
        "constraints": {
            "max_file_size_mb": 25,
            "max_text_length": 5000,
            "supported_languages": ["en", "hi"]
        },
        "features": [
            "Speech-to-Text (STT)",
            "Text-to-Speech (TTS)",
            "Audio quality analysis",
            "Bilingual support",
            "Multiple audio formats"
        ]
    }


@router.get("/info", summary="Voice Service Information")
async def get_voice_info():
    """
    Get detailed voice service information
    
    Returns information about capabilities, limits, and usage
    """
    return {
        "service": "Voice Service",
        "description": "Speech-to-Text and Text-to-Speech service",
        "version": "1.0.0",
        "status": "operational",
        "documentation": {
            "speech_to_text": "POST /api/voice/speech-to-text - Convert audio files to text",
            "text_to_speech": "POST /api/voice/text-to-speech - Convert text to audio",
            "test": "GET /api/voice/test - Test service health",
            "info": "GET /api/voice/info - This endpoint"
        },
        "languages": {
            "en": {
                "name": "English",
                "locale": "en-US",
                "supported_for": ["STT", "TTS"]
            },
            "hi": {
                "name": "Hindi",
                "locale": "hi-IN",
                "supported_for": ["STT", "TTS"]
            }
        },
        "audio_specs": {
            "supported_formats": ["WAV", "MP3", "FLAC", "OGG"],
            "recommended_format": "WAV",
            "recommended_sample_rate": "16000 Hz",
            "recommended_channels": 1,
            "max_file_size": "25 MB",
            "max_duration": "Not specified"
        },
        "text_specs": {
            "max_length_for_tts": "5000 characters",
            "supported_characters": "Unicode (all languages)"
        },
        "error_handling": {
            "400": "Bad request - invalid input",
            "413": "File too large",
            "500": "Server error",
            "502": "Gateway error"
        }
    }


# ============================================================================
# ERROR HANDLERS (if needed)
# ============================================================================

@router.get("/health", tags=["voice"])
async def voice_health():
    """Quick health check for voice service"""
    return {
        "service": "voice",
        "status": "healthy",
        "endpoints": 3,
        "available": True
    }
