from fastapi import APIRouter

router = APIRouter(prefix="/api/providers", tags=["AI Providers"])

@router.get("/status")
def status():
    return {"status": "not implemented yet", "module": "ai-providers"}
