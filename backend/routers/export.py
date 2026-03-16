from fastapi import APIRouter

router = APIRouter(prefix="/api/export", tags=["PDF Exporter"])

@router.get("/status")
def status():
    return {"status": "not implemented yet", "module": "pdf-exporter"}
