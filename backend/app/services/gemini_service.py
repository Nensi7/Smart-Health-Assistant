"""
Gemini AI Service - Google Generative AI Integration
Handles Gemini API communication for health-related queries
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# System prompt for the health assistant
HEALTH_ASSISTANT_SYSTEM_PROMPT = """
You are a knowledgeable and empathetic Smart Health Assistant. Your role is to provide:
- General health information and educational content
- Symptom explanations (non-diagnostic)
- Lifestyle and preventive health tips
- First aid guidance (non-emergency)
- Information about when to see a healthcare professional
- Support and encouragement for healthy living

IMPORTANT GUIDELINES:
1. NEVER diagnose or prescribe medications
2. ALWAYS recommend consulting healthcare professionals for serious concerns
3. Provide evidence-based health information
4. Be supportive and non-judgmental
5. Use simple, clear language
6. Include cultural sensitivity for diverse audiences

DISCLAIMER - Include this or similar in EVERY response:
"⚠️ DISCLAIMER: I'm an educational assistant, not a medical professional. For serious symptoms, chest pain, difficulty breathing, or emergencies, contact emergency services immediately. Always consult a qualified healthcare provider for diagnosis and treatment."
"""

# Disclaimer to append to every response
HEALTH_DISCLAIMER = """

---
⚠️ **DISCLAIMER**: This is educational information only, not medical advice. I am not a doctor. 
For serious symptoms, emergencies, or any health concerns, please consult a qualified healthcare professional or call emergency services.
"""


class GeminiService:
    """
    Service to interact with Google Gemini API for health-related conversations
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini service with API key
        
        Args:
            api_key: Google Gemini API key (can be set via environment variable)
        """
        self.api_key = api_key
        self.model_name = "gemini-1.5-flash"  # or gemini-pro, gemini-1.5-pro
        
        if not self.api_key:
            logger.warning("⚠️ Gemini API key not provided. Gemini queries will fail.")
        
        try:
            # Import here to avoid requiring google-generativeai if Gemini is not used
            import google.generativeai as genai
            self.genai = genai
            
            if self.api_key:
                genai.configure(api_key=self.api_key)
                logger.info("✅ Gemini API configured successfully")
        except ImportError:
            logger.warning("⚠️ google-generativeai not installed. Install with: pip install google-generativeai")
            self.genai = None
    
    async def generate_response(self, user_message: str) -> str:
        """
        Generate a response using Gemini API
        
        Args:
            user_message: User's health-related question or message
        
        Returns:
            str: Generated response with disclaimer appended
        """
        if not self.genai or not self.api_key:
            return "Gemini AI is not configured. Please set GEMINI_API_KEY in your environment."
        
        try:
            logger.info(f"🤖 Querying Gemini: {self.model_name}")
            
            # Create the model
            model = self.genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=HEALTH_ASSISTANT_SYSTEM_PROMPT
            )
            
            # Generate response
            response = model.generate_content(
                user_message,
                safety_settings=[
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_NONE",
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_NONE",
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_NONE",
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_NONE",
                    },
                ],
            )
            
            # Extract text
            generated_text = response.text if response.text else "I could not generate a response."
            
            # Append disclaimer
            response_with_disclaimer = generated_text + HEALTH_DISCLAIMER
            
            logger.info("✅ Gemini response generated successfully")
            return response_with_disclaimer
            
        except Exception as e:
            logger.error(f"❌ Error querying Gemini: {str(e)}")
            return f"I encountered an error: {str(e)}. Please try again later."
    
    async def generate_response_with_context(
        self, 
        user_message: str, 
        conversation_history: list = None
    ) -> str:
        """
        Generate response with conversation history for multi-turn chat
        
        Args:
            user_message: Current user message
            conversation_history: List of previous messages in format [{"role": "user"|"assistant", "content": "..."}]
        
        Returns:
            str: Generated response with disclaimer
        """
        if not self.genai or not self.api_key:
            return "Gemini AI is not configured."
        
        try:
            logger.info("🤖 Starting Gemini chat session with history")
            
            model = self.genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=HEALTH_ASSISTANT_SYSTEM_PROMPT
            )
            
            chat = model.start_chat(history=conversation_history or [])
            response = chat.send_message(user_message)
            
            generated_text = response.text if response.text else "I could not generate a response."
            response_with_disclaimer = generated_text + HEALTH_DISCLAIMER
            
            logger.info("✅ Gemini chat response generated")
            return response_with_disclaimer
            
        except Exception as e:
            logger.error(f"❌ Error in Gemini chat: {str(e)}")
            return f"I encountered an error: {str(e)}. Please try again later."