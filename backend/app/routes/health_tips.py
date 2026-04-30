"""
Health Tips Routes - FULLY INTEGRATED WITH YOUR JSON DATA
File: backend/app/routes/health_tips.py

Loads and uses your actual health_tips.json:
- 2 complete health tips with bilingual content
- Organized by category
- Auto-generates IDs
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import logging
import json
import os
from datetime import datetime

from backend.app.database import DatabaseManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/health-tips", tags=["Health Tips"])

# ============================================================================
# LOAD YOUR ACTUAL JSON DATA - FIXED PATH
# ============================================================================

# Get the correct path to data folder
# Routes are at: backend/app/routes/
# Data is at: backend/app/data/
# So we go up 2 levels and down into data
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/app
DATA_DIR = os.path.join(BASE_DIR, 'data')

logger.info(f"📂 Looking for data files in: {DATA_DIR}")

def load_json_file(filename: str) -> Dict:
    """Load JSON data file"""
    try:
        filepath = os.path.join(DATA_DIR, filename)
        logger.info(f"🔍 Attempting to load: {filepath}")
        
        if not os.path.exists(filepath):
            logger.warning(f"⚠️ File not found: {filepath}")
            return {}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            items_count = len(data.get('tips', data.get('symptoms', [])))
            logger.info(f"✅ Successfully loaded {filename} with {items_count} items")
            return data
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode error in {filename}: {e}")
        return {}
    except Exception as e:
        logger.error(f"❌ Error loading {filename}: {e}")
        return {}

# Load your actual data
HEALTH_TIPS_DATA = load_json_file('health_tips.json')
SYMPTOMS_DATA = load_json_file('symptoms.json')

logger.info(f"📚 Loaded {len(HEALTH_TIPS_DATA.get('tips', []))} health tips")
logger.info(f"🔍 Loaded {len(SYMPTOMS_DATA.get('symptoms', []))} symptoms for mapping")

# ============================================================================
# REQUEST MODELS
# ============================================================================

class SaveTipRequest(BaseModel):
    """Save accessed tip"""
    session_id: str
    tip_id: Optional[str] = None  # Auto-generated if not provided
    title: str
    content: str
    category: str = "general"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_tip_id(title: str) -> str:
    """Generate unique ID from title"""
    from hashlib import md5
    hash_id = md5(title.encode()).hexdigest()[:8]
    return f"tip_{hash_id}"

def get_content_in_language(tip: Dict, language: str = "en") -> str:
    """Get tip content in requested language"""
    if language == "hi":
        return tip.get('content_hi', tip.get('content_en', ''))
    return tip.get('content_en', '')

def get_title_in_language(tip: Dict, language: str = "en") -> str:
    """Get tip title in requested language"""
    if language == "hi":
        return tip.get('title_hi', tip.get('title_en', ''))
    return tip.get('title_en', '')

def search_tips_in_text(query: str) -> List[Dict]:
    """Search tips by matching query in titles and content"""
    query_lower = query.lower()
    matching_tips = []
    
    for tip in HEALTH_TIPS_DATA.get('tips', []):
        title_en = tip.get('title_en', '').lower()
        title_hi = tip.get('title_hi', '').lower()
        content_en = tip.get('content_en', '').lower()
        tags = [t.lower() for t in tip.get('tags', [])]
        
        if (query_lower in title_en or 
            query_lower in title_hi or 
            query_lower in content_en or
            any(query_lower in tag for tag in tags)):
            matching_tips.append(tip)
    
    return matching_tips

def find_tips_for_symptom(symptom_name: str) -> List[Dict]:
    """Find health tips related to a specific symptom"""
    symptom_name_lower = symptom_name.lower()
    related_tips = []
    
    # Search for symptom in tips tags and content
    for tip in HEALTH_TIPS_DATA.get('tips', []):
        tags = [t.lower() for t in tip.get('tags', [])]
        content = tip.get('content_en', '').lower()
        
        if any(symptom_name_lower in tag for tag in tags) or symptom_name_lower in content:
            related_tips.append(tip)
    
    return related_tips

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/", summary="Get All Health Tips")
async def get_all_tips(
    limit: int = 50,
    category: Optional[str] = None,
    language: str = "en"
):
    """
    Get all health tips from YOUR health_tips.json
    
    Query params:
    - limit: Max results
    - category: Filter by category (e.g., 'prevention', 'guidance')
    - language: en (English) or hi (Hindi)
    """
    try:
        logger.info(f"📚 Getting health tips (category: {category}, language: {language})")
        
        all_tips = HEALTH_TIPS_DATA.get('tips', [])
        
        # Filter by category if provided
        if category:
            all_tips = [t for t in all_tips if t.get('category') == category]
        
        # Format response with language support
        formatted_tips = []
        for tip in all_tips[:limit]:
            formatted_tips.append({
                "id": tip.get('id'),
                "title": get_title_in_language(tip, language),
                "content": get_content_in_language(tip, language),
                "category": tip.get('category'),
                "tags": tip.get('tags', []),
                "read_time_minutes": tip.get('read_time_minutes')
            })
        
        categories = list(set(t.get('category') for t in HEALTH_TIPS_DATA.get('tips', [])))
        
        return {
            "status": "success",
            "data": {
                "tips": formatted_tips,
                "count": len(formatted_tips),
                "total_available": len(all_tips),
                "category_filter": category or "all",
                "available_categories": categories,
                "language": language
            }
        }
    except Exception as e:
        logger.error(f"❌ Error getting tips: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/category/{category}", summary="Get Tips by Category")
async def get_tips_by_category(category: str, language: str = "en"):
    """
    Get all health tips in a specific category from YOUR health_tips.json
    
    Categories: prevention, guidance, etc.
    """
    try:
        logger.info(f"📚 Getting tips for category: {category}")
        
        all_tips = HEALTH_TIPS_DATA.get('tips', [])
        category_tips = [t for t in all_tips if t.get('category') == category]
        
        formatted_tips = []
        for tip in category_tips:
            formatted_tips.append({
                "id": tip.get('id'),
                "title": get_title_in_language(tip, language),
                "content": get_content_in_language(tip, language),
                "category": tip.get('category'),
                "tags": tip.get('tags', [])
            })
        
        return {
            "status": "success",
            "data": {
                "category": category,
                "tips": formatted_tips,
                "count": len(formatted_tips),
                "available_categories": list(set(t.get('category') for t in all_tips))
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", summary="Search Health Tips")
async def search_health_tips(query: str, language: str = "en"):
    """
    Search health tips by keyword from YOUR health_tips.json
    
    Searches in: titles, content, tags
    """
    try:
        logger.info(f"🔍 Searching tips: {query}")
        
        results = search_tips_in_text(query)
        
        formatted_results = []
        for tip in results:
            formatted_results.append({
                "id": tip.get('id'),
                "title": get_title_in_language(tip, language),
                "content": get_content_in_language(tip, language),
                "category": tip.get('category'),
                "tags": tip.get('tags', [])
            })
        
        return {
            "status": "success",
            "data": {
                "query": query,
                "tips": formatted_results,
                "count": len(formatted_results),
                "language": language
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/for-symptom/{symptom}", summary="Get Tips for Symptom")
async def get_tips_for_symptom(symptom: str, language: str = "en"):
    """
    Get health tips related to a specific symptom
    Uses YOUR health_tips.json tags to match symptoms
    """
    try:
        logger.info(f"🔍 Getting tips for symptom: {symptom}")
        
        related_tips = find_tips_for_symptom(symptom)
        
        formatted_tips = []
        for tip in related_tips:
            formatted_tips.append({
                "id": tip.get('id'),
                "title": get_title_in_language(tip, language),
                "content": get_content_in_language(tip, language),
                "category": tip.get('category'),
                "tags": tip.get('tags', [])
            })
        
        return {
            "status": "success",
            "data": {
                "symptom": symptom,
                "tips": formatted_tips,
                "count": len(formatted_tips),
                "language": language
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save", summary="Save Accessed Tip")
async def save_accessed_tip(request: SaveTipRequest):
    """
    Save when user accesses a health tip
    Stores in database (health_tips table) to track user education
    
    Generates tip_id automatically if not provided
    
    Example:
    {
        "session_id": "f4bb2499-...",
        "tip_id": "tip_001",  # Optional - auto-generated if missing
        "title": "How to Prevent Common Cold",
        "content": "...",
        "category": "prevention"
    }
    """
    try:
        logger.info(f"💾 Saving tip for session {request.session_id[:8]}...")
        
        # Auto-generate tip_id if not provided
        tip_id = request.tip_id or generate_tip_id(request.title)
        
        # Save to database (health_tips table)
        success = DatabaseManager.save_health_tip(
            session_id=request.session_id,
            title=request.title,
            content=request.content,
            category=request.category
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save tip to database")
        
        logger.info(f"✅ Tip saved to database")
        
        return {
            "status": "success",
            "message": "Tip accessed and saved to your learning history",
            "data": {
                "session_id": request.session_id,
                "tip_id": tip_id,
                "title": request.title,
                "saved_at": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"❌ Error saving tip: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", summary="Get Tips Statistics")
async def get_statistics():
    """
    Get statistics about your health tips data
    Shows what data is loaded from health_tips.json
    """
    try:
        all_tips = HEALTH_TIPS_DATA.get('tips', [])
        
        # Count by category
        categories = {}
        for tip in all_tips:
            cat = tip.get('category', 'general')
            categories[cat] = categories.get(cat, 0) + 1
        
        # Collect all tags
        all_tags = set()
        for tip in all_tips:
            all_tags.update(tip.get('tags', []))
        
        return {
            "status": "success",
            "data": {
                "total_tips": len(all_tips),
                "categories": categories,
                "all_tags": list(all_tags),
                "data_file": "health_tips.json",
                "tips_list": [t.get('title_en') for t in all_tips]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug", summary="Debug - View All Loaded Data")
async def debug_view_data():
    """
    DEBUG endpoint - View what data is loaded from YOUR JSON files
    Remove in production!
    """
    try:
        return {
            "health_tips_loaded": len(HEALTH_TIPS_DATA.get('tips', [])),
            "symptoms_loaded": len(SYMPTOMS_DATA.get('symptoms', [])),
            "health_tips_details": HEALTH_TIPS_DATA.get('tips', []),
            "status": "All data loaded successfully ✅" if HEALTH_TIPS_DATA else "❌ No data loaded"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))