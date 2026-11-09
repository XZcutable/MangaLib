"""Background jobs for slow file work: writing metadata into archives, crunching and unpacking.
One worker runs jobs in order, so two jobs never touch the same files at once. Jobs live in memory;
a restart forgets finished ones, and any half-written file is a ".partial" copy that's cleaned up.
With JOBS_INLINE set (tests), jobs run straight away in the calling request."""
import queue, threading, uuid
from typing import Callable, Optional

from flask import Flask, current_app

from ..database import db
from . import logbuffer

KEEP_FINISHED = 50

_jobs: dict[str, dict] = {}
_order: list[str] = []
_queue: "queue.Queue[tuple[Flask, dict, Callable]]" = queue.Queue()
_lock = threading.Lock()
_worker: Optional[threading.Thread] = None

def _run(app: Flask, job: dict, work: Callable[[dict], Optional[str]]):
    with app.app_context():
        job["status"] = "running"
        try:
            message = work(job)
            job["status"] = "done"
            if message:
                job["message"] = message
        except Exception as error:
            logbuffer.logger("jobs").exception("Job %s (%s) failed", job["id"], job["kind"])
            db.session.rollback()
            job["status"] = "failed"
            job["error"] = str(error) or error.__class__.__name__
        finally:
            db.session.remove()

def _work_loop():
    while True:
        app, job, work = _queue.get()
        try:
            _run(app, job, work)
        finally:
            _queue.task_done()

def submit(kind: str, manga_id: Optional[int], work: Callable[[dict], Optional[str]], total: int = 0) -> dict:
    """Queues `work(job)`. It can update job["done"] as it goes and return a message for the user.
    Pass plain values to it, not database objects from the request, since it runs on another thread."""
    global _worker
    job = {
        "id": uuid.uuid4().hex[:12],
        "kind": kind,
        "manga_id": manga_id,
        "status": "queued",
        "done": 0,
        "total": total,
        "error": None,
        "message": None,
    }
    with _lock:
        _jobs[job["id"]] = job
        _order.append(job["id"])
        # Forget the oldest finished jobs
        finished = [job_id for job_id in _order if _jobs[job_id]["status"] in ("done", "failed")]
        for job_id in finished[:max(0, len(finished) - KEEP_FINISHED)]:
            _order.remove(job_id)
            del _jobs[job_id]

    app = current_app._get_current_object()
    if app.config.get("JOBS_INLINE"):
        _run(app, job, work)
        return job

    with _lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_work_loop, name="mymangalib-jobs", daemon=True)
            _worker.start()
    _queue.put((app, job, work))
    return job

def get(job_id: str) -> Optional[dict]:
    return _jobs.get(job_id)

def active_for(manga_id: int) -> Optional[dict]:
    """A queued or running job for this manga, so the UI can show it and avoid starting another."""
    for job_id in reversed(_order):
        job = _jobs[job_id]
        if job["manga_id"] == manga_id and job["status"] in ("queued", "running"):
            return job
    return None

def any_active() -> bool:
    """Whether any job is queued or running, for changes that affect every manga's files."""
    return any(_jobs[job_id]["status"] in ("queued", "running") for job_id in _order)

def library_job() -> Optional[dict]:
    """A queued or running job for the whole library (no single manga), such as crunching every series."""
    for job_id in reversed(_order):
        job = _jobs[job_id]
        if job["manga_id"] is None and job["status"] in ("queued", "running"):
            return job
    return None
