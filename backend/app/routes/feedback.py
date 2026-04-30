"""
Feedback Route - FIXED VERSION
File: backend/app/routes/feedback.py

Complete feedback implementation with database storage
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import logging
from app.database import (
    get_db, create_or_get_user, store_feedback,
    get_feedback_stats
)
from app.models.models import Feedback, User
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["Feedback"])

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class FeedbackSubmit(BaseModel):
    user_id: str
    rating: int  # 1-5 stars
    comments: Optional[str] = Field(None, alias="feedback_text")
    would_recommend: Optional[bool] = None
    improvement_areas: Optional[str] = None
    assessment_type: Optional[str] = "triage"  # triage, general, appointment
    session_id: Optional[str] = None
    language: Optional[str] = "en"

class FeedbackResponse(BaseModel):
    id: int
    user_id: str
    rating: int
    comments: str
    feedback_date: str
    status: str

# ============================================================================
# ROUTES
# ============================================================================

@router.post("/submit", summary="Submit feedback")
async def submit_feedback(feedback: FeedbackSubmit, db: Session = Depends(get_db)):
    """Submit feedback"""
    try:
        # ✅ Create or get user
        user = create_or_get_user(
            db=db,
            external_id=feedback.user_id,
            language=feedback.language
        )
        
        # ✅ Store feedback
        feedback_obj = store_feedback(
            db=db,
            session_id=None,  # or get from request
            user_id=user.id,
            rating=feedback.rating,
            comments=feedback.comments,
            was_helpful=feedback.rating >= 4
        )
        
        logger.info(f"✅ Feedback stored: {feedback_obj.id}")
        
        return {
            "success": True,
            "data": {
                "id": feedback_obj.id,
                "status": "submitted"
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list", summary="Get feedback list")
async def get_feedback_list(
    user_id: Optional[str] = None,
    assessment_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get feedback list with optional filters"""
    try:
        query = db.query(Feedback)

        if user_id:
            user = db.query(User).filter(User.external_id == user_id).first()
            if not user:
                return {
                    "success": True,
                    "data": {
                        "total": 0,
                        "count": 0,
                        "feedbacks": []
                    }
                }
            query = query.filter(Feedback.user_id == user.id)

        # `assessment_type` is not currently stored in the SQLAlchemy feedback model.
        # It is accepted in the request shape for compatibility but ignored here.

        total = query.count()
        feedbacks = query.order_by(Feedback.created_at.desc()).limit(limit).offset(offset).all()

        result = [
            {
                "id": item.id,
                "session_id": item.session_id,
                "user_id": item.user_id,
                "rating": item.rating,
                "was_helpful": item.was_helpful,
                "comments": item.comments,
                "actual_diagnosis": item.actual_diagnosis,
                "created_at": item.created_at.isoformat() if item.created_at else None
            }
            for item in feedbacks
        ]

        logger.info(f"✅ Retrieved {len(result)} feedback entries")

        return {
            "success": True,
            "data": {
                "total": total,
                "count": len(result),
                "feedbacks": result
            }
        }
    except Exception as e:
        logger.error(f"❌ Error getting feedback list: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch feedback list")

@router.get("/stats", summary="Get feedback statistics")
async def get_stats(db: Session = Depends(get_db)):
    """Get feedback statistics"""
    try:
        stats = get_feedback_stats(db)
        return {"success": True, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{feedback_id}", summary="Get feedback details")
async def get_feedback_details(feedback_id: int, db: Session = Depends(get_db)):
    """Get specific feedback details"""
    try:
        feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")

        logger.info(f"✅ Feedback retrieved: ID {feedback_id}")

        return {
            "success": True,
            "data": {
                "id": feedback.id,
                "session_id": feedback.session_id,
                "user_id": feedback.user_id,
                "rating": feedback.rating,
                "was_helpful": feedback.was_helpful,
                "comments": feedback.comments,
                "actual_diagnosis": feedback.actual_diagnosis,
                "created_at": feedback.created_at.isoformat() if feedback.created_at else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting feedback details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch feedback")

@router.delete("/{feedback_id}", summary="Delete feedback")
async def delete_feedback(feedback_id: int, user_id: str, db: Session = Depends(get_db)):
    """Delete feedback (by owner only)"""
    try:
        feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")

        user = db.query(User).filter(User.external_id == user_id).first()
        if not user or feedback.user_id != user.id:
            raise HTTPException(status_code=403, detail="Unauthorized to delete this feedback")

        db.delete(feedback)
        db.commit()

        logger.info(f"✅ Feedback deleted: ID {feedback_id}")

        return {
            "success": True,
            "data": {
                "deleted_id": feedback_id,
                "status": "deleted"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete feedback")