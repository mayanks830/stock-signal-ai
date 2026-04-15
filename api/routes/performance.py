from fastapi import APIRouter
from database import get_all_performance, get_performance_summary

router = APIRouter()


@router.get("/performance")
def all_performance():
    return get_all_performance()


@router.get("/stats")
def stats():
    return get_performance_summary()
