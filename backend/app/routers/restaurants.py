from fastapi import APIRouter, HTTPException

from ..data_store import load_restaurants
from ..models import Restaurant

router = APIRouter(prefix="/api/restaurants", tags=["restaurants"])


@router.get("", response_model=list[Restaurant])
def list_restaurants():
    return load_restaurants()


@router.get("/{restaurant_id}", response_model=Restaurant)
def get_restaurant(restaurant_id: str):
    for r in load_restaurants():
        if r.id == restaurant_id:
            return r
    raise HTTPException(status_code=404, detail="Restaurant not found")
