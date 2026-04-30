"""
Pytest unit tests for NLPProcessor service.

Covers Week 2 Day 1–2 checklist:
- Symptom extraction from text
- English & Hindi handling
- Misspellings & synonyms via fuzzy matching / aliases
- Symptom matcher helper
"""

import os

from app.services.nlp_processor import (
    NLPProcessor,
    detect_language,
    extract_symptoms,
    find_similar_symptoms,
)


def _get_nlp() -> NLPProcessor:
    """
    Helper to create an NLPProcessor pointing to the real backend/data directory.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(current_dir)
    data_dir = os.path.join(backend_dir, "app", "data")
    return NLPProcessor(data_dir=data_dir)


def test_detect_language_english_and_hindi():
    assert detect_language("I have fever and headache") == "en"
    assert detect_language("मुझे बुखार और सिरदर्द है") == "hi"


def test_extract_symptoms_basic_english():
    nlp = _get_nlp()
    text = "I have fever and headache since 3 days"
    matches = nlp.extract_symptoms(text, language="en")

    names = {m.canonical_name.lower() for m in matches}
    assert "fever" in names
    assert "headache" in names


def test_extract_symptoms_basic_hindi():
    nlp = _get_nlp()
    text = "मुझे बुखार और सिरदर्द है"
    matches = nlp.extract_symptoms(text, language="hi")

    # We check that we at least detect two symptoms
    assert len(matches) >= 2


def test_extract_symptoms_misspelling():
    nlp = _get_nlp()
    # Intentionally misspelled "temperature"
    text = "I have high temprature and body ache"
    matches = nlp.extract_symptoms(text, language="en")

    names = {m.canonical_name.lower() for m in matches}
    # We expect at least "Fever" or "Body Ache" to be recognized
    assert "fever" in names or "body ache" in names


def test_find_similar_symptoms():
    # Directly tests the "symptom matcher" helper
    results = find_similar_symptoms("high temperature", top_k=3, language="en")
    assert len(results) > 0
    # The top result should be closely related to fever
    assert results[0].canonical_name.lower() in {"fever", "high fever"}

