"""Fleet Intelligence API entry point."""
import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    activity_logs, alerts, attachments, auth, boards,
    card_links, cards, connections, phases, users,
)
from .api.deps import _validate_portal_token
from .config import settings
from .core.seed import ensure_seed_admin
from .database import SessionLocal

logger = logging.getLogger("fleet_intelligence")


@asynccontextmanager
async def lifespan(app: FastAPI):
    with SessionLocal() as db:
        ensure_seed_admin(db)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.3.0",
    description="Workflow intelligence platform for fleet equipment lifecycle",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Log de acesso no Command Center ──────────────────────────────────────────
# Mesma logica dos outros sistemas (RTS, RTA, RDA, RCA): fire-and-forget.
_access_seen: dict[str, float] = {}
_ACCESS_TTL = 30 * 60  # 30 min


async def _log_access_to_portal(request: Request):
    """Notifica o Command Center de que o usuario acessou o Fleet Intelligence."""
    portal_token = request.cookies.get("portal_token")
    if not portal_token:
        return
    payload = _validate_portal_token(portal_token)
    if not payload:
        return
    email = payload.get("email", "")
    import time
    now = time.time()
    if email in _access_seen and (now - _access_seen[email]) < _ACCESS_TTL:
        return
    _access_seen[email] = now
    try:
        hostname = (request.headers.get("host") or "").split(":")[0] or "192.168.0.106"
        portal_url = f"http://{hostname}:{settings.COMMAND_CENTER_PORT}/api/audit/access"
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                portal_url,
                json={"system": "fi"},
                cookies={"portal_token": portal_token},
            )
    except Exception as e:
        logger.warning(f"[FI] Log de acesso falhou: {e}")


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": settings.APP_NAME, "env": settings.APP_ENV}


# ─── Rota raiz — log de acesso SSO ───────────────────────────────────────────
@app.get("/", tags=["meta"])
async def root(request: Request):
    """Rota raiz — registra acesso no Command Center quando via SSO."""
    asyncio.ensure_future(_log_access_to_portal(request))
    return {"status": "ok", "service": settings.APP_NAME}


# Mount routers under /api
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(boards.router, prefix="/api")
app.include_router(phases.router, prefix="/api")
app.include_router(cards.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(activity_logs.router, prefix="/api")
app.include_router(connections.router, prefix="/api")
app.include_router(attachments.router, prefix="/api")
app.include_router(card_links.router, prefix="/api")
