"""
Triage Routes - FIXED DISEASE DETECTION & RESPONSE FORMAT
File: backend/app/routes/triage.py

Features:
1. Improved disease detection (matches even 1 symptom now)
2. Better accuracy with age and duration
3. Proper API response format
4. Disease confidence scoring
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import logging
import json
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/triage", tags=["Triage Assessment"])

# ============================================================================
# DISEASE DATABASE (20+ Common Diseases)
# ============================================================================

DISEASE_DATABASE = {
    "common_cold": {
        "name": "Common Cold",
        "symptoms": ["cough", "cold", "runny nose", "sore throat", "sneezing", "stuffy nose"],
        "confidence_threshold": 1,
        "severity_range": (1, 3),
        "age_risk": "all",
        "duration_risk": "1-7 days",
        "keywords": ["cough", "cold", "runny nose", "sore throat", "sneezing", "stuffy nose"],
        "min_symptoms": 2
    },
    "body_ache": {
        "name": "General Body Ache",
        "symptoms": ["body ache", "muscle pain", "ache", "pain"],
        "severity_range": (1, 2),
        "keywords": ["body ache", "muscle pain", "ache", "pain"],
        "min_symptoms": 2
    },
    "headache": {
        "name": "Headache",
        "symptoms": ["headache", "head pain", "migraine"],
        "severity_range": (1, 2),
        "keywords": ["headache", "head pain", "migraine"],
        "min_symptoms": 2
    },
    "stomach_ache": {
        "name": "Stomach Ache",
        "symptoms": ["stomach ache", "stomach pain", "abdominal pain", "belly pain"],
        "severity_range": (1, 2),
        "keywords": ["stomach ache", "stomach pain", "abdominal pain", "belly pain"],
        "min_symptoms": 2
    },
    "back_pain": {
        "name": "Back Pain",
        "symptoms": ["back pain", "backache", "lower back"],
        "severity_range": (1, 2),
        "keywords": ["back pain", "backache", "lower back"],
        "min_symptoms": 2
    },
    "neck_pain": {
        "name": "Neck Pain",
        "symptoms": ["neck pain", "neck stiffness", "stiff neck"],
        "severity_range": (1, 2),
        "keywords": ["neck pain", "neck stiffness", "stiff neck"],
        "min_symptoms": 2
    },
    "fatigue": {
        "name": "Fatigue/Tiredness",
        "symptoms": ["fatigue", "tired", "tiredness", "weakness"],
        "severity_range": (1, 2),
        "keywords": ["fatigue", "tired", "tiredness", "weakness"],
        "min_symptoms": 2
    },
    "allergy": {
        "name": "Allergic Rhinitis",
        "symptoms": ["allergy", "allergic", "itchy eyes", "watery eyes"],
        "severity_range": (1, 2),
        "keywords": ["allergy", "allergic", "itchy eyes", "watery eyes"],
        "min_symptoms": 2
    },
    
    # Moderate Conditions
    "flu": {
        "name": "Influenza (Flu)",
        "symptoms": ["fever", "cough", "body ache", "fatigue", "chills", "ache"],
        "confidence_threshold": 2,
        "severity_range": (2, 6),
        "age_risk": "children, elderly",
        "duration_risk": "3-10 days",
        "keywords": ["fever", "cough", "body ache", "fatigue", "chills", "ache"],
        "min_symptoms": 2
    },
    "covid": {
        "name": "COVID-19",
        "symptoms": ["fever", "cough", "shortness of breath", "loss of taste"],
        "confidence_threshold": 2,
        "severity_range": (3, 9),
        "age_risk": "elderly, immunocompromised, children, adults",
        "duration_risk": "5-14 days",
        "keywords": ["covid", "coronavirus", "shortness of breath", "loss of taste"],
        "min_symptoms": 1
    },
    "typhoid": {
        "name": "Typhoid Fever",
        "symptoms": ["fever", "headache", "weakness", "abdominal pain", "diarrhea", "typhoid"],
        "confidence_threshold": 2,
        "severity_range": (4, 8),
        "age_risk": "children, young adults",
        "duration_risk": "1-6 days",
        "keywords": ["fever", "headache", "weakness", "abdominal pain", "diarrhea", "typhoid"],
        "min_symptoms": 2
    },
    "dengue": {
        "name": "Dengue Fever",
        "symptoms": ["fever", "headache", "body ache", "joint pain", "rash", "dengue"],
        "confidence_threshold": 2,
        "severity_range": (3, 8),
        "age_risk": "all",
        "duration_risk": "3-10 days",
        "keywords": ["fever", "headache", "body ache", "joint pain", "rash", "dengue"],
        "min_symptoms": 2
    },
    "malaria": {
        "name": "Malaria",
        "symptoms": ["fever", "chills", "sweating", "fatigue", "headache", "malaria"],
        "confidence_threshold": 2,
        "severity_range": (4, 9),
        "age_risk": "children, adults",
        "duration_risk": "varies",
        "keywords": ["fever", "chills", "sweating", "fatigue", "headache", "malaria"],
        "min_symptoms": 2
    },
    "pneumonia": {
        "name": "Pneumonia",
        "symptoms": ["cough", "chest pain", "fever", "shortness of breath", "phlegm"],
        "confidence_threshold": 2,
        "severity_range": (5, 9),
        "age_risk": "0-100",
        "duration_risk": "2-30 days",
        "keywords": ["cough", "chest pain", "fever", "shortness of breath", "phlegm"],
        "min_symptoms": 2
    },
    "bronchitis": {
        "name": "Acute Bronchitis",
        "symptoms": ["cough", "phlegm", "fatigue", "shortness of breath", "chest discomfort"],
        "confidence_threshold": 2,
        "severity_range": (3, 6),
        "age_risk": "0-100",
        "duration_risk": "2-10 days",
        "keywords": ["cough", "phlegm", "fatigue", "shortness of breath", "chest discomfort"],
        "min_symptoms": 2
    },
    "asthma": {
        "name": "Asthma",
        "symptoms": ["shortness of breath", "chest tightness", "cough", "wheezing"],
        "confidence_threshold": 2,
        "severity_range": (4, 8),
        "age_risk": "0-100",
        "duration_risk": "2-10 days",
        "keywords": ["shortness of breath", "chest tightness", "cough", "wheezing"],
        "min_symptoms": 2
    },
    "gastroenteritis": {
        "name": "Gastroenteritis (Food Poisoning)",
        "symptoms": ["diarrhea", "vomiting", "nausea", "abdominal pain", "stomach"],
        "confidence_threshold": 2,
        "severity_range": (4, 6),
        "age_risk": "0-100",
        "duration_risk": "1-7 days",
        "keywords": ["diarrhea", "vomiting", "nausea", "abdominal pain", "stomach"],
        "min_symptoms": 2
    },
    "hepatitis": {
        "name": "Hepatitis",
        "symptoms": ["fever", "fatigue", "jaundice", "nausea", "abdominal pain", "hepatitis"],
        "confidence_threshold": 2,
        "severity_range": (4, 8),
        "age_risk": "all",
        "duration_risk": "weeks to months",
        "keywords": ["fever", "fatigue", "jaundice", "nausea", "abdominal pain", "hepatitis"],
        "min_symptoms": 2
    },
    "urinary_tract_infection": {
        "name": "Urinary Tract Infection (UTI)",
        "symptoms": ["painful urination", "frequent urination", "fever", "abdominal pain", "uti"],
        "confidence_threshold": 2,
        "severity_range": (4, 6),
        "age_risk": "0-100",
        "duration_risk": "1-10 days",
        "keywords": ["painful urination", "frequent urination", "fever", "abdominal pain", "uti"],
        "min_symptoms": 2
    },
    "kidney_stones": {
        "name": "Kidney Stones",
        "symptoms": ["severe back pain", "painful urination", "nausea", "frequent urination"],
        "confidence_threshold": 2,
        "severity_range": (5, 8),
        "age_risk": "0-100",
        "duration_risk": "1-14 days",
        "keywords": ["severe back pain", "painful urination", "nausea", "frequent urination"],
        "min_symptoms": 2
    },
    "migraine": {
        "name": "Migraine Headache",
        "symptoms": ["severe headache", "nausea", "vomiting", "light sensitivity", "migraine"],
        "confidence_threshold": 1,
        "severity_range": (4, 6),
        "age_risk": "0-100",
        "duration_risk": "4-72 hours",
        "keywords": ["severe headache", "nausea", "vomiting", "light sensitivity", "migraine"],
        "min_symptoms": 2
    },
    "sinusitis": {
        "name": "Sinusitis",
        "symptoms": ["headache", "runny nose", "cough", "facial pain", "sinus"],
        "confidence_threshold": 1,
        "severity_range": (2, 4),
        "age_risk": "all",
        "duration_risk": "2-10 days",
        "keywords": ["headache", "runny nose", "cough", "facial pain", "sinus"],
        "min_symptoms": 2
    },
    "chickenpox": {
        "name": "Chickenpox",
        "symptoms": ["rash", "fever", "itching", "fatigue", "headache", "chicken pox"],
        "confidence_threshold": 2,
        "severity_range": (3, 5),
        "age_risk": "0-40",
        "duration_risk": "2-10 days",
        "keywords": ["rash", "fever", "itching", "fatigue", "headache", "chicken pox"],
        "min_symptoms": 2
    },
    "measles": {
        "name": "Measles",
        "symptoms": ["fever", "cough", "runny nose", "rash", "red eyes", "measles"],
        "confidence_threshold": 2,
        "severity_range": (4, 8),
        "age_risk": "children, unvaccinated",
        "duration_risk": "7-21 days",
        "keywords": ["fever", "cough", "runny nose", "rash", "red eyes", "measles"],
        "min_symptoms": 2
    },
    "allergic_rhinitis": {
        "name": "Allergic Rhinitis",
        "symptoms": ["runny nose", "sneezing", "itchy eyes", "watery eyes", "allergy"],
        "confidence_threshold": 1,
        "severity_range": (3, 5),
        "age_risk": "0-100",
        "duration_risk": "2-14 days",
        "keywords": ["runny nose", "sneezing", "itchy eyes", "watery eyes", "allergy"],
        "min_symptoms": 2
    },
    "anemia": {
        "name": "Anemia",
        "symptoms": ["fatigue", "weakness", "shortness of breath", "dizziness", "pale skin"],
        "confidence_threshold": 2,
        "severity_range": (2, 6),
        "age_risk": "0-100",
        "duration_risk": "chronic",
        "keywords": ["fatigue", "weakness", "shortness of breath", "dizziness", "pale skin"],
        "min_symptoms": 2
    },
    "diabetes": {
        "name": "Diabetes",
        "symptoms": ["excessive thirst", "frequent urination", "fatigue", "weight loss"],
        "confidence_threshold": 2,
        "severity_range": (3, 7),
        "age_risk": "adults, elderly",
        "duration_risk": "chronic",
        "keywords": ["excessive thirst", "frequent urination", "fatigue", "weight loss"],
        "min_symptoms": 2
    },
    "hypertension": {
        "name": "High Blood Pressure",
        "symptoms": ["headache", "dizziness", "shortness of breath", "chest pain", "high blood pressure"],
        "confidence_threshold": 3,
        "severity_range": (3, 7),
        "age_risk": "0-100",
        "duration_risk": "3-10 days",
        "keywords": ["headache", "dizziness", "shortness of breath", "chest pain", "high blood pressure"],
        "min_symptoms": 2
    }
}

# ============================================================================
# LOAD YOUR ACTUAL JSON DATA FILES
# ============================================================================

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

def load_json_file(filename: str) -> Dict:
    """Load JSON data file from your data folder"""
    try:
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.info(f"✅ Loaded {filename}")
            return data
    except FileNotFoundError:
        logger.warning(f"⚠️ File not found: {filename}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode error in {filename}: {e}")
        return {}

# Load your actual data
SYMPTOMS_DATA = load_json_file('symptoms.json')
EMERGENCY_DATA = load_json_file('red_flags.json')
REMEDIES_DATA = load_json_file('home_remedies.json')

logger.info(f"🔍 Loaded {len(SYMPTOMS_DATA.get('symptoms', []))} symptoms")
logger.info(f"🚨 Loaded {len(EMERGENCY_DATA.get('emergency_symptoms', []))} emergency flags")
logger.info(f"💊 Loaded {len(REMEDIES_DATA.get('remedies', []))} home remedies")
logger.info(f"🏥 Loaded {len(DISEASE_DATABASE)} disease profiles")

# ============================================================================
# REQUEST MODELS
# ============================================================================

class TriageRequest(BaseModel):
    """Symptom assessment request"""
    user_input: str
    duration_days: Optional[int] = 1
    user_age: Optional[int] = 30
    severity_self_reported: Optional[int] = 1
    language: str = "en"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def find_symptoms_in_text(text: str, language: str = "en") -> List[Dict]:
    """Find symptoms in user input"""
    found_symptoms = []
    text_lower = text.lower()
    
    for symptom in SYMPTOMS_DATA.get('symptoms', []):
        symptom_name = symptom.get('name', '').lower()
        aliases = [a.lower() for a in symptom.get('aliases', [])]
        
        if symptom_name in text_lower or any(alias in text_lower for alias in aliases):
            found_symptoms.append(symptom)
            logger.info(f"✅ Found symptom: {symptom.get('name')}")
    
    return found_symptoms

def check_emergency_symptoms(text: str) -> List[Dict]:
    """Check if user input contains emergency keywords"""
    emergency_found = []
    text_lower = text.lower()
    
    for emergency in EMERGENCY_DATA.get('emergency_symptoms', []):
        keyword = emergency.get('keyword', '').lower()
        
        if keyword in text_lower:
            emergency_found.append(emergency)
            logger.warning(f"🚨 EMERGENCY DETECTED: {emergency.get('keyword')}")
    
    return emergency_found

def calculate_severity_improved(symptoms: List[Dict], duration_days: int, user_age: int) -> Dict:
    """IMPROVED: Only show MILD for simple pains"""
    
    if not symptoms:
        return {
            "severity_level": "MILD",
            "severity_score": 1,
            "is_emergency": False
        }
    
    # Base severity from symptom types
    base_severity = 1  # Start low
    
    # Check if symptoms are SIMPLE PAIN (body ache, headache, stomach ache)
    simple_pain_keywords = ["ache", "pain", "sore", "tired", "fatigue"]
    is_simple_pain = any(
        any(keyword in symptom.get('name', '').lower() for keyword in simple_pain_keywords)
        for symptom in symptoms
    )
    
    if is_simple_pain and len(symptoms) == 1 and duration_days <= 3:
        # Single simple pain = MILD
        return {
            "severity_level": "MILD",
            "severity_score": 1,
            "is_emergency": False
        }
    
    # For other conditions
    base_severity = max([s.get('base_severity', 1) for s in symptoms])
    severity_score = base_severity
    
    # Age factor
    if user_age < 5 or user_age > 75:
        severity_score += 1
    elif user_age > 65 or user_age < 12:
        severity_score += 0.5
    
    # Duration factor (only matters for 7+ days)
    if duration_days > 7:
        severity_score += 1
    if duration_days > 14:
        severity_score += 1
    
    severity_score = min(severity_score, 10)
    
    # Determine level
    if severity_score <= 2:
        severity_level = "MILD"
    elif severity_score <= 4:
        severity_level = "MODERATE"
    elif severity_score <= 7:
        severity_level = "SEVERE"
    else:
        severity_level = "EMERGENCY"
    
    return {
        "severity_level": severity_level,
        "severity_score": severity_score,
        "is_emergency": False
    }


def detect_diseases(user_input: str, symptoms: List[Dict], duration_days: int, user_age: int) -> Dict:
    """IMPROVED: Better disease matching"""
    
    detected_diseases = {}
    input_lower = user_input.lower()
    symptom_names = [s.get('name', '').lower() for s in symptoms]
    
    for disease_id, disease_info in DISEASE_DATABASE.items():
        disease_symptoms = [s.lower() for s in disease_info.get('symptoms', [])]
        matching_count = 0
        
        # Count symptom matches
        for symptom in symptom_names:
            if symptom in disease_symptoms:
                matching_count += 1
        
        # Check keywords
        for keyword in disease_info.get('keywords', []):
            if keyword.lower() in input_lower:
                matching_count += 1
        
        # Check minimum symptoms required for this disease
        min_required = disease_info.get('min_symptoms', 2)
        if matching_count >= min_required:
            # Calculate confidence
            symptom_confidence = (matching_count / len(disease_info.get('symptoms', [1]))) * 50
            
            # Age factor
            age_confidence = 0
            if disease_id in ["pneumonia", "measles"]:
                if user_age < 12 or user_age > 65:
                    age_confidence = 15
            else:
                age_confidence = 10
            
            # Duration matters for chronic conditions
            duration_confidence = 5
            if duration_days > 7 and disease_id in ["typhoid", "dengue", "malaria"]:
                duration_confidence = 15
            
            total_confidence = min(symptom_confidence + age_confidence + duration_confidence, 100)
            
            # Only include if confidence > 35%
            if total_confidence > 35:
                detected_diseases[disease_id] = {
                    "name": disease_info['name'],
                    "confidence": round(total_confidence),
                    "matching_symptoms": matching_count,
                    "severity_range": disease_info.get('severity_range', (1, 10))
                }
    
    # Sort and limit to 5
    top_diseases = dict(sorted(
        detected_diseases.items(),
        key=lambda x: x[1]['confidence'],
        reverse=True
    )[:5])
        
    return top_diseases

def get_home_care_from_json(symptoms: List[Dict]) -> List[str]:
    """Get home remedies from symptoms.json"""
    all_remedies = []
    
    for symptom in symptoms:
        remedies = symptom.get('home_remedies', [])
        all_remedies.extend(remedies)
    
    for symptom in symptoms:
        symptom_name = symptom.get('name', '').lower()
        for remedy in REMEDIES_DATA.get('remedies', []):
            good_for = remedy.get('good_for', [])
            if any(symptom_name in gf.lower() for gf in good_for):
                remedy_suggestion = f"{remedy.get('name')}: " + " → ".join(remedy.get('instructions', [])[:2])
                all_remedies.append(remedy_suggestion)
    
    return list(set(all_remedies))

def get_serious_signs(symptoms: List[Dict]) -> List[str]:
    """Get serious signs from symptoms.json"""
    serious_signs = []
    for symptom in symptoms:
        signs = symptom.get('serious_signs', [])
        serious_signs.extend(signs)
    return serious_signs

def get_when_to_see_doctor(symptoms: List[Dict]) -> str:
    """Get 'when_to_see_doctor' guidance"""
    if not symptoms:
        return "Monitor symptoms and consult doctor if they worsen"
    return symptoms[0].get('when_to_see_doctor', 'See doctor if symptoms persist')


def is_non_medical_or_greeting_input(user_input: str) -> bool:
    """
    Detect greeting/small-talk input that should not be triaged.
    """
    text = user_input.strip().lower()
    if not text:
        return True

    greeting_phrases = {
        "hi", "hello", "hey", "hello assistant", "hi assistant", "good morning",
        "good evening", "good afternoon", "namaste", "नमस्ते", "thanks", "thank you"
    }
    if text in greeting_phrases:
        return True

    # If it's short and has no known symptom keywords, treat as non-medical.
    symptom_keywords = []
    for symptom in SYMPTOMS_DATA.get("symptoms", []):
        name = symptom.get("name", "").lower()
        if name:
            symptom_keywords.append(name)
        symptom_keywords.extend([a.lower() for a in symptom.get("aliases", []) if a])

    has_symptom_keyword = any(keyword in text for keyword in symptom_keywords)
    return (len(text.split()) <= 3) and (not has_symptom_keyword)

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/assess", summary="Assess Symptom Severity with Disease Detection")
async def assess_symptoms(request: TriageRequest):
    """Improved assessment endpoint"""
    logger.info(f"🔍 New assessment request: {request.user_input[:50]}...")
    logger.info(f"   Age: {request.user_age}, Duration: {request.duration_days} days")
    
    # If this is greeting/small-talk input, do not produce a medical severity score.
    if is_non_medical_or_greeting_input(request.user_input):
        return {
            "success": True,
            "data": {
                "severity_level": "NO_ASSESSMENT",
                "severity_score": 0,
                "symptoms_identified": [],
                "detected_diseases": {},
                "home_remedies": [],
                "serious_signs": [],
                "when_to_see_doctor": (
                    "Please describe your health symptoms (for example: fever, headache, cough for 3 days)."
                    if request.language == "en" else
                    "कृपया अपने स्वास्थ्य लक्षण बताएं (उदाहरण: 3 दिनों से बुखार, सिरदर्द, खांसी)।"
                ),
                "is_emergency": False,
                "action": "ASK_FOR_SYMPTOMS"
            }
        }

    # Find symptoms
    symptoms = find_symptoms_in_text(request.user_input, request.language)
    emergency_symptoms = check_emergency_symptoms(request.user_input)
    
    # Calculate severity
    severity = calculate_severity_improved(
        symptoms,
        request.duration_days,
        request.user_age
    )
    
    # Detect diseases
    diseases = detect_diseases(
        request.user_input,
        symptoms,
        request.duration_days,
        request.user_age
    )
    
    # Get recommendations
    home_remedies = get_home_care_from_json(symptoms)[:5]
    serious_signs = get_serious_signs(symptoms)
    when_to_see_doctor = get_when_to_see_doctor(symptoms)
    
    # Check for emergency
    is_emergency = len(emergency_symptoms) > 0 or severity['severity_level'] == 'EMERGENCY'
    
    response = {
        "severity_level": severity['severity_level'],
        "severity_score": severity['severity_score'],
        "symptoms_identified": [s.get('name') for s in symptoms],
        "detected_diseases": diseases,
        "home_remedies": home_remedies,
        "serious_signs": serious_signs,
        "when_to_see_doctor": when_to_see_doctor,
        "is_emergency": is_emergency,
        "action": "IMMEDIATE_CARE" if is_emergency else "MONITOR_SYMPTOMS"
    }
    
    logger.info(f"✅ Assessment complete: {severity['severity_level']} ({severity['severity_score']}/10)")
    
    return {
        "success": True,
        "data": response
    }

@router.get("/diseases", summary="Get Disease Database")
async def get_diseases():
    """Get all available diseases"""
    return {
        "total_diseases": len(DISEASE_DATABASE),
        "diseases": [
            {
                "id": disease_id,
                "name": info['name'],
                "symptoms": info['symptoms'][:3],
                "severity_range": info['severity_range']
            }
            for disease_id, info in list(DISEASE_DATABASE.items())[:10]
        ]
    }