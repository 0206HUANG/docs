import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import CurrentUser, DB
from app.core.exceptions import NotFoundError
from app.db.models import ResumeProfile

router = APIRouter()


def _serialize(r: ResumeProfile) -> dict:
    return {
        "id": str(r.id),
        "email_id": str(r.email_id),
        "candidate_name": r.candidate_name,
        "candidate_email": r.candidate_email,
        "candidate_phone": r.candidate_phone,
        "education": r.education,
        "experience": r.experience,
        "skills": r.skills,
        "desired_position": r.desired_position,
        "expected_salary": r.expected_salary,
        "years_experience": r.years_experience,
        "summary": r.summary,
        "match_score": r.match_score,
        "match_notes": r.match_notes,
        "source": r.source,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("")
async def list_resumes(
    current_user: CurrentUser,
    db: DB,
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    result = await db.execute(
        select(ResumeProfile)
        .where(ResumeProfile.tenant_id == current_user.tenant_id)
        .order_by(ResumeProfile.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [_serialize(r) for r in result.scalars().all()]


@router.get("/{resume_id}")
async def get_resume(resume_id: str, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(ResumeProfile).where(
            ResumeProfile.id == uuid.UUID(resume_id),
            ResumeProfile.tenant_id == current_user.tenant_id,
        )
    )
    r = result.scalar_one_or_none()
    if not r:
        raise NotFoundError("Resume")
    return _serialize(r)
