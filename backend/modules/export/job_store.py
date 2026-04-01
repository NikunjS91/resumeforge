"""
In-memory store for async export jobs.
Jobs complete within minutes, so no persistence needed.
"""
import threading
import uuid
import time

_jobs: dict = {}
_lock = threading.Lock()

TTL = 1800  # 30 minutes


def create_job(user_id: int) -> str:
    """Create a new job entry and return its job_id."""
    job_id = str(uuid.uuid4())
    _cleanup_old_jobs()
    with _lock:
        _jobs[job_id] = {
            "status":     "pending",   # pending | running | done | error
            "stage":      "Queued",
            "user_id":    user_id,
            "pdf_path":   None,
            "error":      None,
            "created_at": time.time(),
        }
    return job_id


def update_job(job_id: str, **kwargs):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def _cleanup_old_jobs():
    cutoff = time.time() - TTL
    with _lock:
        stale = [jid for jid, j in _jobs.items() if j["created_at"] < cutoff]
        for jid in stale:
            del _jobs[jid]
