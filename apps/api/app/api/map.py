from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.map import BackfillResponse, MapResponse
from app.services.map_service import backfill_coordinates, build_map_payload

router = APIRouter(tags=["map"])


@router.get("/map", response_model=MapResponse)
def get_map(db: Session = Depends(get_db)) -> MapResponse:
    return build_map_payload(db)


@router.post("/map/backfill", response_model=BackfillResponse)
def post_map_backfill(db: Session = Depends(get_db)) -> BackfillResponse:
    return backfill_coordinates(db)
