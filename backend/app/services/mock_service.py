# backend/app/services/mock_service.py
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "mock_responses.json"

class MockService:
    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) if path else DATA_PATH
        if not self.path.exists():
            logger.warning(f"Mock responses file not found: {self.path}")

    async def generate_response(self, user_message: str) -> str:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            # Exact-match then substring then fallback
            if user_message in data:
                return data[user_message]
            for key, val in data.items():
                if key.lower() in user_message.lower():
                    return val
            return data.get("_default", "Sorry — I don't have an answer right now.")
        except Exception as e:
            logger.exception("MockService failed")
            return "Mock service error."