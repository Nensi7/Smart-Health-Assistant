"""
NLP Processor Service for Smart Health Assistant

Responsibilities:
- Detect language (English / Hindi) from user text
- Extract symptom mentions from free-text input
- Normalize symptom names to canonical forms from symptoms.json
- Handle aliases, Hindi names, and common spelling variations
- Provide simple fuzzy matching for noisy input

NOTE:
- This service ONLY parses text and identifies symptoms.
- It does NOT diagnose, score severity, or make medical decisions.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass
class SymptomMatch:
    """
    Result of a symptom match inside user text.

    Attributes:
        id: Symptom ID from symptoms.json
        canonical_name: Canonical English name
        hindi_name: Hindi name (if available)
        matched_text: Exact text/alias that was matched in the input
        confidence: 0-1 confidence score (heuristic)
        language_detected: "en" or "hi"
    """

    id: str
    canonical_name: str
    hindi_name: Optional[str]
    matched_text: str
    confidence: float
    language_detected: str


# ============================================================================
# NLP PROCESSOR CLASS
# ============================================================================


class NLPProcessor:
    """
    NLP Processor for extracting symptoms from user free-text.

    Uses:
    - backend/data/symptoms.json
    - backend/data/translations.json
    - backend/data/red_flags.json (optional, for later services)

    Key public methods:
        detect_language(text) -> "en" | "hi"
        normalize_symptom_name(raw_text) -> str
        extract_symptoms(text, language=None) -> List[SymptomMatch]
        find_similar_symptoms(input_text, top_k=5) -> List[SymptomMatch]
    """

    HINDI_UNICODE_RANGE = (0x0900, 0x097F)  # Basic Devanagari range

    def __init__(self, data_dir: Optional[str] = None) -> None:
        # Resolve data directory (…/backend/data)
        if data_dir is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Data is stored under backend/app/data
            app_dir = os.path.dirname(current_dir)
            alt_data_dir = os.path.join(app_dir, "data")
            if os.path.exists(alt_data_dir):
                data_dir = alt_data_dir
            else:
                backend_dir = os.path.dirname(app_dir)
                data_dir = os.path.join(backend_dir, "data")

        self.data_dir = data_dir
        self.symptoms_data = self._load_json("symptoms.json").get("symptoms", [])
        self.red_flags_data = self._safe_load_json("red_flags.json").get(
            "emergency_symptoms", []
        )

        # Precompute lookup tables
        self._symptom_index_en: Dict[str, Dict] = {}
        self._symptom_index_hi: Dict[str, Dict] = {}
        self._build_indexes()

        logger.info(
            "✅ NLPProcessor initialized with %d symptoms and %d emergency entries",
            len(self.symptoms_data),
            len(self.red_flags_data),
        )

    # ------------------------------------------------------------------ #
    # JSON LOADING HELPERS
    # ------------------------------------------------------------------ #

    def _load_json(self, filename: str) -> Dict:
        path = os.path.join(self.data_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required data file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _safe_load_json(self, filename: str) -> Dict:
        path = os.path.join(self.data_dir, filename)
        if not os.path.exists(path):
            logger.warning("Optional data file not found: %s", path)
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("Error reading optional JSON file %s: %s", path, exc)
            return {}

    # ------------------------------------------------------------------ #
    # INDEX BUILDING
    # ------------------------------------------------------------------ #

    def _build_indexes(self) -> None:
        """
        Build English and Hindi lookup dictionaries:

        _symptom_index_en:
            key: normalized English alias / name
        _symptom_index_hi:
            key: normalized Hindi name / keyword
        """
        for item in self.symptoms_data:
            sid = item.get("id")
            _ = sid  # unused but kept for clarity
            name_en = item.get("name", "").strip()
            name_hi = item.get("hindi_name", "").strip()
            aliases = item.get("aliases", []) or []

            # English entries
            candidates_en = [name_en] + aliases
            for alias in candidates_en:
                key = self._normalize_for_index(alias, lang="en")
                if key:
                    self._symptom_index_en[key] = item

            # Hindi entries
            if name_hi:
                key_hi = self._normalize_for_index(name_hi, lang="hi")
                if key_hi:
                    self._symptom_index_hi[key_hi] = item

        logger.info(
            "🔎 Built symptom indexes | EN: %d entries, HI: %d entries",
            len(self._symptom_index_en),
            len(self._symptom_index_hi),
        )

    @staticmethod
    def _normalize_for_index(text: str, lang: str) -> str:
        """
        Normalize text for dictionary keys (lowercase, stripped, basic cleanup).
        Language parameter reserved for future, if we need language-specific rules.
        """
        if not text:
            return ""
        text = text.strip().lower()
        # Remove extra spaces and basic punctuation around words
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^\w\s\u0900-\u097F]", "", text)
        return text

    # ------------------------------------------------------------------ #
    # LANGUAGE DETECTION
    # ------------------------------------------------------------------ #

    def detect_language(self, text: str) -> str:
        """
        Very lightweight language detector: returns "hi" if Devanagari characters
        are detected, otherwise "en".

        This is heuristic but fast and works well for mixed Hindi/English input.
        """
        if not text:
            return "en"

        for ch in text:
            code = ord(ch)
            if self.HINDI_UNICODE_RANGE[0] <= code <= self.HINDI_UNICODE_RANGE[1]:
                return "hi"

        return "en"

    # ------------------------------------------------------------------ #
    # NORMALIZATION
    # ------------------------------------------------------------------ #

    def normalize_symptom_name(self, raw_text: str) -> str:
        """
        Normalize a raw symptom phrase to a canonical key used in symptoms.json.

        Strategy:
        - Normalize text
        - If exact key exists in EN/HI index, return that
        - Otherwise, return normalized text itself (to be used with fuzzy search)
        """
        if not raw_text:
            return ""

        # Try both English and Hindi normalization, since we only return key
        norm_en = self._normalize_for_index(raw_text, lang="en")
        if norm_en in self._symptom_index_en:
            return norm_en

        norm_hi = self._normalize_for_index(raw_text, lang="hi")
        if norm_hi in self._symptom_index_hi:
            return norm_hi

        # Fallback: return normalized English variant
        return norm_en or norm_hi

    # ------------------------------------------------------------------ #
    # TOKENIZATION / BASIC TEXT CLEAN-UP
    # ------------------------------------------------------------------ #

    def _tokenize(self, text: str) -> List[str]:
        """
        Very simple tokenizer: lowercases, strips, splits on non-word boundaries.
        Designed to work for both English and Hindi.
        """
        text = text.lower()
        # Replace punctuation with spaces, keep Devanagari chars
        text = re.sub(r"[^\w\s\u0900-\u097F]", " ", text)
        tokens = re.split(r"\s+", text)
        return [t for t in tokens if t]

    # ------------------------------------------------------------------ #
    # SYMPTOM EXTRACTION
    # ------------------------------------------------------------------ #

    def extract_symptoms(
        self,
        text: str,
        language: Optional[str] = None,
        min_confidence: float = 0.5,
    ) -> List[SymptomMatch]:
        """
        Extract symptom mentions from user input.

        Strategy:
        - Detect language if not provided
        - Search for exact phrase matches (canonical name + aliases)
        - Apply simple fuzzy matching for noisy inputs
        - Return list of SymptomMatch sorted by confidence

        NOTE: This function does NOT diagnose or assess severity; it only identifies
        which canonical symptoms are mentioned.
        """
        if not text or not text.strip():
            return []

        lang = language or self.detect_language(text)
        normalized_text = text.lower()
        tokens = self._tokenize(text)

        matches: List[SymptomMatch] = []

        # 1. Exact phrase / alias matches
        index = self._symptom_index_hi if lang == "hi" else self._symptom_index_en

        for key, item in index.items():
            # Key is normalized alias/name, so search normalized_text
            if key and key in normalized_text:
                confidence = 0.9  # high confidence for substring match
                matches.append(
                    SymptomMatch(
                        id=item.get("id", ""),
                        canonical_name=item.get("name", ""),
                        hindi_name=item.get("hindi_name"),
                        matched_text=key,
                        confidence=confidence,
                        language_detected=lang,
                    )
                )

        # 2. Fuzzy matching over tokens for near-miss spellings
        #    Only do this if we don't have strong exact matches
        if not matches:
            candidates = self._symptom_index_en if lang == "en" else self._symptom_index_hi
            for token in set(tokens):
                best_item, _, best_score = self._best_fuzzy_match(token, candidates)
                if best_item and best_score >= min_confidence:
                    matches.append(
                        SymptomMatch(
                            id=best_item.get("id", ""),
                            canonical_name=best_item.get("name", ""),
                            hindi_name=best_item.get("hindi_name"),
                            matched_text=token,
                            confidence=float(best_score),
                            language_detected=lang,
                        )
                    )

        # Deduplicate by symptom id (keep highest confidence)
        dedup: Dict[str, SymptomMatch] = {}
        for m in matches:
            if m.id not in dedup or m.confidence > dedup[m.id].confidence:
                dedup[m.id] = m

        result = sorted(dedup.values(), key=lambda m: m.confidence, reverse=True)
        return result

    def _best_fuzzy_match(
        self,
        token: str,
        index: Dict[str, Dict],
    ) -> Tuple[Optional[Dict], Optional[str], float]:
        """
        Return the best fuzzy match in index for a single token.

        Uses difflib.SequenceMatcher ratio as a simple similarity score.
        """
        best_item: Optional[Dict] = None
        best_key: Optional[str] = None
        best_score: float = 0.0

        for key, item in index.items():
            if not key:
                continue
            score = SequenceMatcher(None, token, key).ratio()
            if score > best_score:
                best_score = score
                best_item = item
                best_key = key

        return best_item, best_key, best_score

    # ------------------------------------------------------------------ #
    # HIGH-LEVEL API: FIND SIMILAR SYMPTOMS
    # ------------------------------------------------------------------ #

    def find_similar_symptoms(
        self,
        input_text: str,
        top_k: int = 5,
        language: Optional[str] = None,
    ) -> List[SymptomMatch]:
        """
        Given an input phrase like "high temprature" or "सीने मे दर्द",
        return the most similar known symptoms from the database.

        This is useful for:
        - building UI suggestions
        - debugging symptom coverage
        - powering auto-complete features

        Returns top_k SymptomMatch objects with confidence scores.
        """
        if not input_text:
            return []

        lang = language or self.detect_language(input_text)
        normalized = self._normalize_for_index(input_text, lang=lang)

        index = self._symptom_index_en if lang == "en" else self._symptom_index_hi

        candidates: List[SymptomMatch] = []
        for key, item in index.items():
            score = SequenceMatcher(None, normalized, key).ratio()
            candidates.append(
                SymptomMatch(
                    id=item.get("id", ""),
                    canonical_name=item.get("name", ""),
                    hindi_name=item.get("hindi_name"),
                    matched_text=key,
                    confidence=float(score),
                    language_detected=lang,
                )
            )

        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates[:top_k]


# ============================================================================
# CONVENIENCE FUNCTIONS (MODULE-LEVEL)
# ============================================================================

# You can either use the class directly, or use these helpers
# which reuse a single global instance.

_nlp_instance: Optional[NLPProcessor] = None


def get_nlp_processor() -> NLPProcessor:
    global _nlp_instance
    if _nlp_instance is None:
        _nlp_instance = NLPProcessor()
    return _nlp_instance


def detect_language(text: str) -> str:
    return get_nlp_processor().detect_language(text)


def extract_symptoms(text: str, language: Optional[str] = None) -> List[SymptomMatch]:
    return get_nlp_processor().extract_symptoms(text, language=language)


def normalize_symptom_name(raw_text: str) -> str:
    return get_nlp_processor().normalize_symptom_name(raw_text)


def find_similar_symptoms(
    input_text: str,
    top_k: int = 5,
    language: Optional[str] = None,
) -> List[SymptomMatch]:
    return get_nlp_processor().find_similar_symptoms(
        input_text=input_text,
        top_k=top_k,
        language=language,
    )


# ============================================================================
# MANUAL TESTING (run: python -m backend.app.services.nlp_processor)
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    nlp = get_nlp_processor()

    examples = [
        "I have fever and headache since 3 days",
        "मुझे बुखार और सिरदर्द है",
        "खांसी और गले में दर्द हो रहा है",
        "high temprature and body ache",
        "severe chest pain and difficulty breathing",
    ]

    for text in examples:
        lang = nlp.detect_language(text)
        print("=" * 80)
        print(f"Input: {text}")
        print(f"Detected language: {lang}")
        matches = nlp.extract_symptoms(text, language=lang)
        if not matches:
            print("No symptoms detected.")
        else:
            print("Detected symptoms:")
            for m in matches:
                print(
                    f" - {m.canonical_name} ({m.hindi_name or '—'}) "
                    f"[id={m.id}, matched='{m.matched_text}', confidence={m.confidence:.2f}]"
                )

