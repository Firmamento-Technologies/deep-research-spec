from fastapi import APIRouter
from typing import Optional

router = APIRouter()


@router.get("/analytics")
async def get_analytics(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    preset: Optional[str] = None,
    keyword: Optional[str] = None,
):
    # TODO: STEP 11 — query PostgreSQL runs table with filters
    return {
        "runs_completed": 0,
        "avg_cost": 0.0,
        "total_words": 0,
        "avg_css": 0.0,
        "first_iter_success_rate": 0.0,
        "runs": [],
    }
