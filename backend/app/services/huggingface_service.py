"""
Hugging Face Inference API Service (improved logging + error handling)
"""

import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

HEALTH_DISCLAIMER = """

---
⚠️ DISCLAIMER: This is educational information only, not medical advice. Consult a qualified healthcare professional for diagnosis and treatment.
"""

class HuggingFaceService:
    def __init__(self, api_key: Optional[str] = None, model: str = "mistralai/Mistral-7B-Instruct-v0.1"):
        self.api_key = api_key
        self.model = model
        self.api_url = f"https://router.huggingface.co/models/{self.model}"
        if not api_key:
            logger.warning("⚠️ Hugging Face API key not provided")

    async def generate_response(self, user_message: str) -> str:
        if not self.api_key:
            return "Hugging Face API not configured. Set HUGGINGFACE_API_KEY in .env."

        system_prompt = (
            "You are a helpful Smart Health Assistant. Provide accurate, evidence-based, and "
            "concise health information. Never diagnose or prescribe. Always recommend consulting healthcare professionals."
        )
        prompt = f"{system_prompt}\n\nUser: {user_message}\n\nAssistant:"

        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 300,
                "temperature": 0.7,
                "top_p": 0.95,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info("🤖 HuggingFace: sending request")
                resp = await client.post(self.api_url, json=payload, headers=headers)
                text = resp.text
                status = resp.status_code

                if status == 200:
                    data = resp.json()
                    # HF often returns list or dict depending on model
                    if isinstance(data, list) and data and "generated_text" in data[0]:
                        generated_text = data[0]["generated_text"]
                    elif isinstance(data, dict) and "generated_text" in data:
                        generated_text = data["generated_text"]
                    else:
                        # Fallback: try first value or 'generated_text' keys
                        generated_text = str(data)
                    # Remove repeated prompt if present
                    if "Assistant:" in generated_text:
                        generated_text = generated_text.split("Assistant:")[-1].strip()
                    return generated_text + HEALTH_DISCLAIMER
                else:
                    logger.error(f"❌ HuggingFace API Error {status}: {text}")
                    return f"HuggingFace API error ({status}). See server logs."
        except httpx.HTTPStatusError as e:
            logger.error(f"HuggingFace HTTP error: {e}")
            return f"HuggingFace HTTP error: {e}"
        except Exception as e:
            logger.exception("❌ HuggingFace request failed")
            return f"HuggingFace error: {e}"