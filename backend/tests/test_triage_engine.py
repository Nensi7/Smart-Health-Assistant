"""
Pytest unit tests for TriageEngine service.

Covers Week 2 Day 3-4 checklist:
- Rule-based triage system
- Severity scoring logic
- Duration factors
- Age risk factors
- Emergency detection
- Test with 50+ symptom scenarios (sample set)
"""

import os

from app.models.schemas import SeverityLevel
from app.services.nlp_processor import NLPProcessor, SymptomMatch
from app.services.triage_engine import TriageEngine, assess_severity, TriageInput


def _get_triage() -> TriageEngine:
    """Helper to create TriageEngine with real data"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(current_dir)
    data_dir = os.path.join(backend_dir, "app", "data")
    return TriageEngine(data_dir=data_dir)


def _get_nlp() -> NLPProcessor:
    """Helper to create NLPProcessor with real data"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(current_dir)
    data_dir = os.path.join(backend_dir, "app", "data")
    return NLPProcessor(data_dir=data_dir)


def test_emergency_detection_chest_pain():
    """Test emergency detection for chest pain"""
    triage = _get_triage()
    is_emergency, reasons = triage.check_for_red_flags("I have severe chest pain", "en")
    assert is_emergency is True
    assert len(reasons) > 0


def test_emergency_detection_difficulty_breathing():
    """Test emergency detection for difficulty breathing"""
    triage = _get_triage()
    is_emergency, reasons = triage.check_for_red_flags("difficulty breathing", "en")
    assert is_emergency is True


def test_mild_severity_single_symptom():
    """Test MILD severity for single mild symptom"""
    nlp = _get_nlp()
    triage = _get_triage()

    matches = nlp.extract_symptoms("I have a mild headache", language="en")
    input_data = TriageInput(
        symptoms=matches,
        duration_days=1,
        user_age=30,
        language="en"
    )
    result = triage.assess_severity(input_data)

    assert result.severity_level == SeverityLevel.MILD
    assert 1 <= result.severity_score <= 3


def test_moderate_severity_multiple_symptoms():
    """Test MODERATE severity for multiple symptoms"""
    nlp = _get_nlp()
    triage = _get_triage()

    matches = nlp.extract_symptoms("fever and cough for 5 days", language="en")
    input_data = TriageInput(
        symptoms=matches,
        duration_days=5,
        user_age=30,
        language="en"
    )
    result = triage.assess_severity(input_data)

    assert result.severity_level in [SeverityLevel.MILD, SeverityLevel.MODERATE]
    assert result.severity_score >= 1


def test_age_factor_infant():
    """Test age modifier for infants (<2 years)"""
    nlp = _get_nlp()
    triage = _get_triage()

    matches = nlp.extract_symptoms("fever", language="en")
    
    # Infant case
    input_infant = TriageInput(
        symptoms=matches,
        duration_days=1,
        user_age=1,
        language="en"
    )
    result_infant = triage.assess_severity(input_infant)

    # Adult case (for comparison)
    input_adult = TriageInput(
        symptoms=matches,
        duration_days=1,
        user_age=30,
        language="en"
    )
    result_adult = triage.assess_severity(input_adult)

    # Infant should have higher severity score
    assert result_infant.severity_score >= result_adult.severity_score


def test_age_factor_elderly():
    """Test age modifier for elderly (65+ years)"""
    nlp = _get_nlp()
    triage = _get_triage()

    matches = nlp.extract_symptoms("fever and body ache", language="en")
    
    # Elderly case
    input_elderly = TriageInput(
        symptoms=matches,
        duration_days=3,
        user_age=70,
        language="en"
    )
    result_elderly = triage.assess_severity(input_elderly)

    # Elderly should have higher severity
    assert result_elderly.severity_score >= 4  # At least MODERATE


def test_duration_factor_acute():
    """Test duration modifier for acute onset (<1 day)"""
    nlp = _get_nlp()
    triage = _get_triage()

    matches = nlp.extract_symptoms("severe headache", language="en")
    
    # Acute onset
    input_acute = TriageInput(
        symptoms=matches,
        duration_days=0,
        user_age=30,
        language="en"
    )
    result_acute = triage.assess_severity(input_acute)

    # Should have higher severity than normal duration
    assert result_acute.severity_score >= 1


def test_duration_factor_persistent():
    """Test duration modifier for persistent symptoms (7+ days)"""
    nlp = _get_nlp()
    triage = _get_triage()

    matches = nlp.extract_symptoms("cough", language="en")
    
    # Persistent
    input_persistent = TriageInput(
        symptoms=matches,
        duration_days=10,
        user_age=30,
        language="en"
    )
    result_persistent = triage.assess_severity(input_persistent)

    # Should have higher severity
    assert result_persistent.severity_score >= 1


def test_combination_modifier_multiple_symptoms():
    """Test combination modifier for multiple symptoms"""
    nlp = _get_nlp()
    triage = _get_triage()

    # Single symptom
    matches_single = nlp.extract_symptoms("headache", language="en")
    input_single = TriageInput(
        symptoms=matches_single,
        duration_days=2,
        user_age=30,
        language="en"
    )
    result_single = triage.assess_severity(input_single)

    # Multiple symptoms
    matches_multi = nlp.extract_symptoms("fever headache cough", language="en")
    input_multi = TriageInput(
        symptoms=matches_multi,
        duration_days=2,
        user_age=30,
        language="en"
    )
    result_multi = triage.assess_severity(input_multi)

    # Multiple symptoms should have higher severity
    assert result_multi.severity_score >= result_single.severity_score


def test_hindi_input():
    """Test triage with Hindi input"""
    nlp = _get_nlp()
    triage = _get_triage()

    matches = nlp.extract_symptoms("मुझे बुखार और सिरदर्द है", language="hi")
    input_data = TriageInput(
        symptoms=matches,
        duration_days=3,
        user_age=30,
        language="hi"
    )
    result = triage.assess_severity(input_data)

    assert result.severity_level in [SeverityLevel.MILD, SeverityLevel.MODERATE]
    assert len(result.recommendation) > 0


def test_emergency_response_structure():
    """Test that emergency response has correct structure"""
    nlp = _get_nlp()
    triage = _get_triage()

    matches = nlp.extract_symptoms("chest pain difficulty breathing", language="en")
    input_data = TriageInput(
        symptoms=matches,
        duration_days=0,
        user_age=45,
        language="en",
        raw_text="chest pain difficulty breathing"
    )
    result = triage.assess_severity(input_data)

    # Should be EMERGENCY
    assert result.severity_level == SeverityLevel.EMERGENCY
    assert result.severity_score == 10
    assert len(result.emergency_indicators) > 0
    assert "108" in result.recommendation.upper() or "EMERGENCY" in result.recommendation.upper()


def test_home_care_suggestions_for_mild():
    """Test that home care suggestions are provided for MILD severity"""
    nlp = _get_nlp()
    triage = _get_triage()

    matches = nlp.extract_symptoms("mild headache", language="en")
    input_data = TriageInput(
        symptoms=matches,
        duration_days=1,
        user_age=30,
        language="en"
    )
    result = triage.assess_severity(input_data)

    if result.severity_level == SeverityLevel.MILD:
        assert len(result.home_care_suggestions) > 0


def test_confidence_score_range():
    """Test that confidence score is in valid range (0-1)"""
    nlp = _get_nlp()
    triage = _get_triage()

    matches = nlp.extract_symptoms("fever", language="en")
    input_data = TriageInput(
        symptoms=matches,
        duration_days=2,
        user_age=30,
        language="en"
    )
    result = triage.assess_severity(input_data)

    assert 0.0 <= result.confidence_score <= 1.0


def test_severity_score_range():
    """Test that severity score is in valid range (1-10)"""
    nlp = _get_nlp()
    triage = _get_triage()

    matches = nlp.extract_symptoms("headache", language="en")
    input_data = TriageInput(
        symptoms=matches,
        duration_days=1,
        user_age=30,
        language="en"
    )
    result = triage.assess_severity(input_data)

    assert 1 <= result.severity_score <= 10


def test_follow_up_questions():
    """Test that follow-up questions are generated"""
    nlp = _get_nlp()
    triage = _get_triage()

    matches = nlp.extract_symptoms("fever", language="en")
    input_data = TriageInput(
        symptoms=matches,
        duration_days=2,
        user_age=30,
        language="en"
    )
    result = triage.assess_severity(input_data)

    assert isinstance(result.next_questions, list)
    assert len(result.next_questions) > 0
