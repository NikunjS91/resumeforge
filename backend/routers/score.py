from fastapi import APIRouter

router = APIRouter(prefix="/api/score", tags=["ATS Scorer"])

@router.get("/status")
def status():
    return {"status": "not implemented yet", "module": "ats-scorer"}
