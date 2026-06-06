import threading
import queue
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.database import SessionLocal
from app.models import AccessLog

_log_queue: queue.Queue = queue.Queue(maxsize=1000)
_worker_started = False


def _log_worker():
    while True:
        batch = []
        try:
            item = _log_queue.get(timeout=5)
            batch.append(item)
            while len(batch) < 50:
                try:
                    batch.append(_log_queue.get_nowait())
                except queue.Empty:
                    break
        except queue.Empty:
            continue

        if batch:
            db = SessionLocal()
            try:
                for entry in batch:
                    db.add(AccessLog(**entry))
                db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()


def _ensure_worker():
    global _worker_started
    if not _worker_started:
        _worker_started = True
        t = threading.Thread(target=_log_worker, daemon=True)
        t.start()


class AccessLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        _ensure_worker()

        if request.url.path.startswith("/static"):
            return await call_next(request)

        response = await call_next(request)

        user_id = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            from jose import jwt, JWTError
            from app.config import SECRET_KEY
            try:
                payload = jwt.decode(auth_header[7:], SECRET_KEY, algorithms=["HS256"])
                user_id = int(payload.get("sub"))
            except (JWTError, ValueError, TypeError):
                pass

        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else None)
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        try:
            _log_queue.put_nowait({
                "user_id": user_id,
                "method": request.method,
                "path": str(request.url.path)[:500],
                "status_code": response.status_code,
                "ip_address": ip,
            })
        except queue.Full:
            pass

        return response
