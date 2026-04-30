"""
Voice Service - Speech to Text and Text to Speech
"""

import os
import logging
import base64
import tempfile
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# SPEECH TO TEXT (STT)
# ============================================================================

def transcribe_audio(audio_data: bytes, language: str = "en") -> dict:
    """
    Transcribe audio to text using faster-whisper
    """
    try:
        # Try faster-whisper (best quality/speed balance)
        try:
            from faster_whisper import Whisper
            
            model = Whisper("base", device="cpu")
            segments, info = model.transcribe(
                audio_data, 
                language=language if language == "en" else "hi",
                beam_size=5
            )
            
            text = ""
            confidence_sum = 0
            count = 0
            
            for segment in segments:
                text += segment.text + " "
                confidence_sum += segment.avg_logprob
                count += 1
            
            confidence = confidence_sum / count if count > 0 else 0.85
            
            return {
                "text": text.strip(),
                "confidence": float(0.85 + confidence) if confidence > -1 else 0.85,
                "language": info.language,
                "duration": sum(s.end - s.start for s in segments) if segments else 0
            }
            
        except ImportError:
            logger.warning("faster-whisper not available")
        except Exception as e:
            logger.warning(f"faster-whisper error: {str(e)}")
        
        # Fallback: Basic transcription
        return {
            "text": "Could not transcribe audio. Please try again.",
            "confidence": 0.0,
            "language": language,
            "error": "No STT engine available"
        }
        
    except Exception as e:
        logger.error(f"❌ STT Error: {str(e)}")
        return {
            "text": "",
            "confidence": 0.0,
            "language": language,
            "error": str(e)
        }


# ============================================================================
# TEXT TO SPEECH (TTS)
# ============================================================================

def text_to_speech(text: str, language: str = "en") -> dict:
    """
    Convert text to speech
    """
    try:
        # Try edge-tts (best quality, free)
        try:
            import asyncio
            import edge_tts
            
            async def generate_speech():
                voice = "hi-IN-SwaraNeural" if language == "hi" else "en-US-JennyNeural"
                communicate = edge_tts.Communicate(text, voice)
                
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    temp_path = f.name
                
                await communicate.save(temp_path)
                return temp_path
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                temp_path = loop.run_until_complete(generate_speech())
            finally:
                loop.close()
            
            with open(temp_path, "rb") as f:
                audio_data = f.read()
            
            os.unlink(temp_path)
            
            return {
                "audio_base64": base64.b64encode(audio_data).decode("utf-8"),
                "format": "mp3",
                "sample_rate": 48000,
                "duration": len(audio_data) / 48000 / 4
            }
            
        except ImportError:
            logger.warning("edge-tts not available")
        except Exception as e:
            logger.warning(f"edge-tts error: {str(e)}")
        
        # Try gTTS (Google TTS)
        try:
            from gtts import gTTS
            import io
            
            tld = "com" if language == "en" else "co.in"
            tts = gTTS(text=text, lang=language[:2], tld=tld)
            
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_data = audio_buffer.getvalue()
            
            return {
                "audio_base64": base64.b64encode(audio_data).decode("utf-8"),
                "format": "mp3",
                "sample_rate": 24000,
                "duration": len(audio_data) / 24000 / 4
            }
            
        except ImportError:
            logger.warning("gtts not available")
        except Exception as e:
            logger.warning(f"gtts error: {str(e)}")
        
        return {
            "audio_base64": "",
            "format": "mp3",
            "error": "No TTS engine available"
        }
        
    except Exception as e:
        logger.error(f"❌ TTS Error: {str(e)}")
        return {
            "audio_base64": "",
            "format": "mp3",
            "error": str(e)
        }


# ============================================================================
# VOICE ANALYSIS
# ============================================================================

def analyze_voice_quality(audio_data: bytes) -> dict:
    """Analyze audio quality"""
    try:
        import struct
        import math
        import wave
        import io
        
        if len(audio_data) < 44:
            return {"quality": "unknown", "error": "Audio too short"}
        
        try:
            with io.BytesIO(audio_data) as bio:
                with wave.open(bio) as w:
                    channels = w.getnchannels()
                    sample_width = w.getsampwidth()
                    framerate = w.getframerate()
                    n_frames = w.getnframes()
                    duration = n_frames / framerate
                    frames = w.readframes(n_frames)
                    
                    if sample_width == 2:
                        fmt = f"{len(frames)//2}h"
                        samples = struct.unpack(fmt, frames)
                        rms = math.sqrt(sum(s*s for s in samples) / len(samples))
                        max_amp = max(abs(s) for s in samples)
                    else:
                        rms = 0
                        max_amp = 0
                    
                    quality_score = 0
                    issues = []
                    
                    if duration < 0.5:
                        issues.append("Audio too short")
                    else:
                        quality_score += 30
                    
                    if max_amp < 1000:
                        issues.append("Audio too quiet")
                    elif max_amp > 30000:
                        issues.append("Audio too loud")
                    else:
                        quality_score += 30
                    
                    if framerate < 16000:
                        issues.append("Low sample rate")
                    else:
                        quality_score += 20
                    
                    if channels == 1:
                        quality_score += 20
                    else:
                        issues.append("Expected mono audio")
                    
                    if quality_score >= 90:
                        quality = "excellent"
                    elif quality_score >= 70:
                        quality = "good"
                    elif quality_score >= 50:
                        quality = "fair"
                    else:
                        quality = "poor"
                    
                    return {
                        "quality": quality,
                        "score": quality_score,
                        "duration": round(duration, 2),
                        "sample_rate": framerate,
                        "channels": channels,
                        "issues": issues if issues else None
                    }
                    
        except Exception as e:
            logger.warning(f"Could not parse WAV: {str(e)}")
        
        return {
            "quality": "unknown",
            score: 50,
            "duration": len(audio_data) / 32000,
            "error": "Could not analyze"
        }
        
    except Exception as e:
        logger.error(f"❌ Voice analysis error: {str(e)}")
        return {"quality": "unknown", "error": str(e)}


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 Testing Voice Service")
    print("=" * 70)
    
    print("\n🔊 Testing TTS...")
    result = text_to_speech("Hello, I am your health assistant.", "en")
    if result.get("audio_base64"):
        print("✅ TTS working! Audio length:", len(result["audio_base64"]), "chars")
    else:
        print("❌ TTS failed:", result.get("error"))
    
    print("\n" + "=" * 70)