from fastapi import APIRouter

router = APIRouter(prefix="/api/tailor", tags=["Resume Tailor"])

@router.get("/status")
def status():
    return {"status": "not implemented yet", "module": "resume-tailor"}
