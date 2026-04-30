"""
Triage Engine Service for Smart Health Assistant

Week 2 Day 3-4: Rule-Based Triage System

Responsibilities:
- Assess symptom severity WITHOUT diagnosis
- Calculate severity score (0-10) based on rules
- Apply duration factors (how long symptoms persist)
- Apply age risk factors (infants/children/elderly = higher risk)
- Detect emergency conditions (red flags)
- Provide care recommendations (home/clinic/hospital/emergency)
- Generate home care suggestions
- Explain reasoning in human-readable way

CRITICAL: This is EDUCATIONAL only - NO diagnosis, NO prescriptions
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.models.schemas import SeverityLevel, TriageResponse
from app.services.nlp_processor import SymptomMatch

logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class TriageInput:
    """Input for triage assessment"""
    symptoms: List[SymptomMatch]  # From NLPProcessor
    duration_days: Optional[int] = None
    user_age: Optional[int] = None
    severity_self_reported: Optional[int] = None  # 1-10
    language: str = "en"
    raw_text: Optional[str] = None


@dataclass
class TriageResult:
    """Internal triage calculation result"""
    severity_level: SeverityLevel
    severity_score: int  # 0-10
    base_score: float
    duration_modifier: float
    age_modifier: float
    combination_modifier: float
    emergency_detected: bool
    emergency_reasons: List[str]
    reasoning: str


# ============================================================================
# TRIAGE ENGINE CLASS
# ============================================================================

class TriageEngine:
    """
    Rule-based triage system for symptom severity assessment.
    
    Severity Levels:
    - MILD (1-3): Manageable at home, low risk
    - MODERATE (4-6): Should see doctor soon, not emergency
    - SEVERE (7-9): Should see doctor today
    - EMERGENCY (10): Life-threatening, call 108 NOW
    
    Key Rules:
    1. Emergency detection (red flags) = immediate EMERGENCY (10)
    2. Base severity from symptoms.json
    3. Duration factors: Very short (<1 day) or very long (>30 days) may adjust
    4. Age factors: Infants (<2), Children (<12), Elderly (>65) = higher risk
    5. Combination: Multiple symptoms = additive risk
    """

    def __init__(self, data_dir: Optional[str] = None) -> None:
        """Initialize triage engine with data files"""
        if data_dir is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            app_dir = os.path.dirname(current_dir)  # .../backend/app
            alt_data_dir = os.path.join(app_dir, "data")

            if os.path.exists(alt_data_dir):
                data_dir = alt_data_dir
            else:
                backend_dir = os.path.dirname(app_dir)  # .../backend
                data_dir = os.path.join(backend_dir, "data")

        self.data_dir = data_dir
        self.symptoms_data = self._load_json("symptoms.json").get("symptoms", [])
        self.red_flags_data = self._load_json("red_flags.json").get("emergency_symptoms", [])

        # Build lookup dictionaries
        self._symptom_by_id: Dict[str, Dict] = {}
        self._red_flag_keywords_en: List[str] = []
        self._red_flag_keywords_hi: List[str] = []
        self._build_lookups()

        logger.info(
            "✅ TriageEngine initialized | %d symptoms, %d red flags",
            len(self.symptoms_data),
            len(self.red_flags_data)
        )

    # ------------------------------------------------------------------------ #
    # DATA LOADING & INDEXING
    # ------------------------------------------------------------------------ #

    def _load_json(self, filename: str) -> Dict:
        """Load JSON data file"""
        path = os.path.join(self.data_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required data file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_lookups(self) -> None:
        """Build fast lookup dictionaries"""
        # Symptom by ID
        for symptom in self.symptoms_data:
            self._symptom_by_id[symptom.get("id", "")] = symptom

        # Red flag keywords (English & Hindi)
        for red_flag in self.red_flags_data:
            keyword_en = red_flag.get("keyword", "").lower()
            keyword_hi = red_flag.get("hindi_keyword", "").lower()
            if keyword_en:
                self._red_flag_keywords_en.append(keyword_en)
            if keyword_hi:
                self._red_flag_keywords_hi.append(keyword_hi)

    # ------------------------------------------------------------------------ #
    # EMERGENCY DETECTION
    # ------------------------------------------------------------------------ #

    def check_for_red_flags(
        self,
        text: str,
        language: str = "en"
    ) -> Tuple[bool, List[str]]:
        """
        Check if user input contains emergency red flag keywords.
        
        Returns:
            (is_emergency: bool, reasons: List[str])
        """
        text_lower = text.lower()
        keywords = self._red_flag_keywords_hi if language == "hi" else self._red_flag_keywords_en
        reasons: List[str] = []

        for red_flag in self.red_flags_data:
            keyword = (red_flag.get("hindi_keyword", "") if language == "hi"
                      else red_flag.get("keyword", "")).lower()
            
            if keyword and keyword in text_lower:
                reasons.append(red_flag.get("description", keyword))
                logger.warning(f"🚨 EMERGENCY DETECTED: {keyword}")

        return len(reasons) > 0, reasons

    # ------------------------------------------------------------------------ #
    # SEVERITY CALCULATION
    # ------------------------------------------------------------------------ #

    def assess_severity(
        self,
        input_data: TriageInput
    ) -> TriageResponse:
        """
        Main triage assessment function.
        
        Args:
            input_data: TriageInput with symptoms, duration, age, etc.
        
        Returns:
            TriageResponse with severity level, score, recommendations, etc.
        """
        # Step 1: Check for emergency red flags FIRST
        user_text = input_data.raw_text or " ".join([m.matched_text for m in input_data.symptoms])
        is_emergency, emergency_reasons = self.check_for_red_flags(
            user_text, input_data.language
        )

        if is_emergency:
            return self._create_emergency_response(emergency_reasons, input_data.language)

        # Step 2: Calculate base severity from symptoms
        base_score = self._calculate_base_severity(input_data.symptoms)

        # Step 3: Apply duration modifier
        duration_modifier = self._calculate_duration_modifier(
            input_data.duration_days,
            base_score
        )

        # Step 4: Apply age modifier
        age_modifier = self._calculate_age_modifier(
            input_data.user_age,
            base_score
        )

        # Step 5: Apply combination modifier (multiple symptoms = worse)
        combination_modifier = self._calculate_combination_modifier(
            len(input_data.symptoms)
        )

        # Step 6: Apply self-reported severity (if provided)
        self_reported_modifier = 0.0
        if input_data.severity_self_reported:
            # Normalize self-reported (1-10) to modifier (-0.5 to +0.5)
            self_reported_modifier = (input_data.severity_self_reported - 5) * 0.1

        # Step 7: Calculate final score
        final_score = (
            base_score +
            duration_modifier +
            age_modifier +
            combination_modifier +
            self_reported_modifier
        )

        # Clamp to 1-10 range
        final_score = max(1, min(10, int(round(final_score))))

        # Step 8: Map score to severity level
        severity_level = self._score_to_severity_level(final_score)

        # Step 9: Build response
        return self._build_triage_response(
            severity_level=severity_level,
            severity_score=final_score,
            symptoms=input_data.symptoms,
            duration_days=input_data.duration_days,
            user_age=input_data.user_age,
            language=input_data.language,
            emergency_reasons=[],
            base_score=base_score,
            duration_modifier=duration_modifier,
            age_modifier=age_modifier,
            combination_modifier=combination_modifier
        )

    def _calculate_base_severity(self, symptoms: List[SymptomMatch]) -> float:
        """
        Calculate base severity from symptom list.
        
        Strategy:
        - Average base_severity from symptoms.json
        - Weight by confidence scores
        """
        if not symptoms:
            return 2.0  # Default mild if no symptoms detected

        total_weighted_score = 0.0
        total_weight = 0.0

        for symptom_match in symptoms:
            symptom_data = self._symptom_by_id.get(symptom_match.id)
            if not symptom_data:
                continue

            base_severity = float(symptom_data.get("base_severity", 2))
            confidence = symptom_match.confidence

            total_weighted_score += base_severity * confidence
            total_weight += confidence

        if total_weight == 0:
            return 2.0

        return total_weighted_score / total_weight

    def _calculate_duration_modifier(
        self,
        duration_days: Optional[int],
        base_score: float
    ) -> float:
        """
        Apply duration factor to severity.
        
        Rules:
        - < 1 day: +0.5 (acute onset = potentially serious)
        - 1-3 days: +0.0 (normal)
        - 4-7 days: +0.5 (persistent = concerning)
        - 8-14 days: +1.0 (very persistent = more serious)
        - 15-30 days: +0.5 (chronic but stable)
        - > 30 days: -0.5 (chronic, less acute risk)
        """
        if duration_days is None:
            return 0.0

        if duration_days < 1:
            return 0.5  # Acute onset
        elif duration_days <= 2:
            return 0.0  # Normal duration
        elif duration_days <= 5:
            return 0.5  # Persistent
        elif duration_days <= 7:
            return 1.0  # Very persistent
        elif duration_days <= 9:
            return 0.5  # Chronic but stable
        else:
            return -0.5  # Long-term chronic (less acute)

    def _calculate_age_modifier(
        self,
        user_age: Optional[int],
        base_score: float
    ) -> float:
        """
        Apply age risk factor.
        
        Rules:
        - Infants (< 2 years): +2.0 (high risk)
        - Children (2-11 years): +1.0 (moderate risk)
        - Adults (12-64 years): +0.0 (normal risk)
        - Elderly (65+ years): +1.5 (higher risk)
        """
        if user_age is None:
            return 0.0

        if user_age < 2:
            return 2.0  # Infants: very high risk
        elif user_age < 12:
            return 1.0  # Children: moderate risk
        elif user_age < 65:
            return 0.0  # Adults: normal risk
        else:
            return 1.5  # Elderly: higher risk

    def _calculate_combination_modifier(self, symptom_count: int) -> float:
        """
        Apply combination factor (multiple symptoms = worse).
        
        Rules:
        - 1 symptom: +0.0
        - 2 symptoms: +1.0
        - 3 symptoms: +1.5
        - 4+ symptoms: +2.0
        """
        if symptom_count <= 1:
            return 0.0
        elif symptom_count == 2:
            return 1.0
        elif symptom_count == 3:
            return 1.5
        else:
            return 2.0

    def _score_to_severity_level(self, score: int) -> SeverityLevel:
        """Map numerical score (1-10) to severity level"""
        if score >= 6:
            return SeverityLevel.EMERGENCY
        elif score >= 5:
            return SeverityLevel.SEVERE
        elif score >= 3:
            return SeverityLevel.MODERATE
        else:
            return SeverityLevel.MILD

    # ------------------------------------------------------------------------ #
    # RESPONSE BUILDING
    # ------------------------------------------------------------------------ #

    def _create_emergency_response(
        self,
        emergency_reasons: List[str],
        language: str
    ) -> TriageResponse:
        """Create emergency response (severity = 10)"""
        if language == "hi":
            recommendation = "तुरंत 108 पर कॉल करें। यह एक आपातकालीन स्थिति है।"
            when_to_see_doctor = "तुरंत आपातकालीन चिकित्सा सहायता लें।"
        else:
            recommendation = "CALL 108 IMMEDIATELY. This is a medical emergency."
            when_to_see_doctor = "Seek emergency medical help immediately."

        return TriageResponse(
            severity_level=SeverityLevel.EMERGENCY,
            severity_score=10,
            recommendation=recommendation,
            emergency_indicators=emergency_reasons,
            home_care_suggestions=[],
            when_to_see_doctor=when_to_see_doctor,
            next_questions=[],
            confidence_score=0.95
        )

    def _build_triage_response(
        self,
        severity_level: SeverityLevel,
        severity_score: int,
        symptoms: List[SymptomMatch],
        duration_days: Optional[int],
        user_age: Optional[int],
        language: str,
        emergency_reasons: List[str],
        base_score: float,
        duration_modifier: float,
        age_modifier: float,
        combination_modifier: float
    ) -> TriageResponse:
        """Build complete TriageResponse with all details"""

        # Get recommendations based on severity
        recommendation, when_to_see_doctor = self._get_recommendations(
            severity_level, language
        )

        # Get home care suggestions (only for MILD/MODERATE)
        home_care = []
        if severity_level in [SeverityLevel.MILD, SeverityLevel.MODERATE]:
            home_care = self._get_home_care_suggestions(symptoms, language)

        # Get follow-up questions
        next_questions = self._get_follow_up_questions(symptoms, language)

        # Calculate confidence (based on symptom detection confidence)
        confidence = self._calculate_confidence(symptoms)

        return TriageResponse(
            severity_level=severity_level,
            severity_score=severity_score,
            recommendation=recommendation,
            emergency_indicators=emergency_reasons,
            home_care_suggestions=home_care,
            when_to_see_doctor=when_to_see_doctor,
            next_questions=next_questions,
            confidence_score=confidence
        )

    def _get_recommendations(
        self,
        severity_level: SeverityLevel,
        language: str
    ) -> Tuple[str, str]:
        """Get care recommendations based on severity level"""
        if language == "hi":
            recommendations = {
                SeverityLevel.MILD: (
                    "घर पर देखभाल करें। लक्षणों पर नजर रखें।",
                    "यदि लक्षण 3 दिनों से अधिक समय तक बने रहें या बिगड़ें तो डॉक्टर को दिखाएं।"
                ),
                SeverityLevel.MODERATE: (
                    "24 घंटे के भीतर क्लिनिक या अस्पताल जाएं यदि लक्षण बने रहें।",
                    "यदि लक्षण बिगड़ते हैं या नए लक्षण दिखाई देते हैं तो तुरंत डॉक्टर को दिखाएं।"
                ),
                SeverityLevel.SEVERE: (
                    "आज ही आपातकालीन कक्ष या अस्पताल जाएं। प्रतीक्षा न करें।",
                    "यह गंभीर स्थिति है। तुरंत चिकित्सा सहायता लें।"
                ),
            }
        else:
            recommendations = {
                SeverityLevel.MILD: (
                    "Self-care at home. Monitor symptoms.",
                    "See a doctor if symptoms persist for more than 3 days or worsen."
                ),
                SeverityLevel.MODERATE: (
                    "Visit a clinic or hospital within 24 hours if symptoms persist.",
                    "See a doctor immediately if symptoms worsen or new symptoms appear."
                ),
                SeverityLevel.SEVERE: (
                    "Visit emergency room or hospital TODAY. Do not wait.",
                    "This is a serious condition. Seek medical help immediately."
                ),
            }

        return recommendations.get(severity_level, ("See a doctor", "Seek medical help"))

    def _get_home_care_suggestions(
        self,
        symptoms: List[SymptomMatch],
        language: str
    ) -> List[str]:
        """Get home care suggestions from symptoms.json"""
        suggestions_set = set()

        for symptom_match in symptoms:
            symptom_data = self._symptom_by_id.get(symptom_match.id)
            if not symptom_data:
                continue

            remedies = symptom_data.get("home_remedies", [])
            for remedy in remedies[:3]:  # Limit to top 3 per symptom
                suggestions_set.add(remedy)

        return list(suggestions_set)[:5]  # Return max 5 suggestions

    def _get_follow_up_questions(
        self,
        symptoms: List[SymptomMatch],
        language: str
    ) -> List[str]:
        """Generate follow-up questions based on detected symptoms"""
        if language == "hi":
            questions = [
                "क्या आपको खांसी है?",
                "क्या आपको सांस लेने में कठिनाई है?",
                "क्या आपको बुखार है?",
                "क्या आपको कोई अन्य लक्षण हैं?",
            ]
        else:
            questions = [
                "Do you have a cough?",
                "Do you have difficulty breathing?",
                "Do you have a fever?",
                "Are there any other symptoms?",
            ]

        return questions[:3]  # Return top 3

    def _calculate_confidence(self, symptoms: List[SymptomMatch]) -> float:
        """Calculate confidence score based on symptom detection confidence"""
        if not symptoms:
            return 0.5

        avg_confidence = sum(s.confidence for s in symptoms) / len(symptoms)
        # Boost confidence if multiple symptoms agree
        if len(symptoms) >= 2:
            avg_confidence = min(1.0, avg_confidence * 1.1)

        return round(avg_confidence, 2)

    # ------------------------------------------------------------------------ #
    # HELPER: GET RECOMMENDATIONS
    # ------------------------------------------------------------------------ #

    def get_recommendations(self, severity_level: SeverityLevel) -> List[str]:
        """
        Get care recommendations for a severity level.
        
        This is a public helper method for other services.
        """
        # This is already implemented in _get_recommendations
        # But we expose a simpler version here
        rec, _ = self._get_recommendations(severity_level, "en")
        return [rec]


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_triage_instance: Optional[TriageEngine] = None


def get_triage_engine() -> TriageEngine:
    """Get singleton TriageEngine instance"""
    global _triage_instance
    if _triage_instance is None:
        _triage_instance = TriageEngine()
    return _triage_instance


def assess_severity(
    symptoms: List[SymptomMatch],
    duration_days: Optional[int] = None,
    user_age: Optional[int] = None,
    severity_self_reported: Optional[int] = None,
    language: str = "en",
    raw_text: Optional[str] = None,
) -> TriageResponse:
    """
    Convenience function to assess severity.
    
    Usage:
        from app.services.triage_engine import assess_severity
        from app.services.nlp_processor import extract_symptoms
        
        matches = extract_symptoms("I have fever and headache")
        result = assess_severity(matches, duration_days=3, user_age=30)
    """
    engine = get_triage_engine()
    input_data = TriageInput(
        symptoms=symptoms,
        duration_days=duration_days,
        user_age=user_age,
        severity_self_reported=severity_self_reported,
        language=language,
        raw_text=raw_text,
    )
    return engine.assess_severity(input_data)


# ============================================================================
# MANUAL TESTING
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from app.services.nlp_processor import get_nlp_processor

    nlp = get_nlp_processor()
    triage = get_triage_engine()

    test_cases = [
        {
            "text": "I have a mild headache",
            "duration_days": 1,
            "age": 30,
            "language": "en"
        },
        {
            "text": "मुझे बुखार और खांसी है",
            "duration_days": 5,
            "age": 8,
            "language": "hi"
        },
        {
            "text": "severe chest pain and difficulty breathing",
            "duration_days": 0,
            "age": 45,
            "language": "en"
        },
        {
            "text": "fever and body ache for 3 days",
            "duration_days": 3,
            "age": 70,
            "language": "en"
        },
    ]

    print("=" * 80)
    print("TRIAGE ENGINE TEST CASES")
    print("=" * 80)

    for i, case in enumerate(test_cases, 1):
        print(f"\n📋 Test Case {i}:")
        print(f"Input: {case['text']}")
        print(f"Duration: {case['duration_days']} days | Age: {case['age']}")

        # Extract symptoms
        matches = nlp.extract_symptoms(case["text"], language=case["language"])

        # Assess severity
        result = assess_severity(
            symptoms=matches,
            duration_days=case["duration_days"],
            user_age=case["age"],
            language=case["language"]
        )

        print(f"\n✅ Result:")
        print(f"  Severity: {result.severity_level.value.upper()} (Score: {result.severity_score}/10)")
        print(f"  Recommendation: {result.recommendation}")
        print(f"  When to see doctor: {result.when_to_see_doctor}")
        if result.home_care_suggestions:
            print(f"  Home care: {', '.join(result.home_care_suggestions[:2])}")
        if result.emergency_indicators:
            print(f"  ⚠️ EMERGENCY: {', '.join(result.emergency_indicators)}")
        print("-" * 80)
