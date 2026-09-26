"""
Karen's Ear — FastAPI Backend Application Entrypoint
Foundation setup: Request IDs, canonical envelope, error handlers, and /health probe.
DO NOT call Base.metadata.create_all() on startup.
"""
import asyncio
from contextlib import asynccontextmanager
import logging
from fastapi import Depends, FastAPI, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from .core.config import settings
from .core.envelope import (
    error_response,
    generate_request_id,
    get_request_id,
    set_request_id,
    success_response,
)
from .core.exceptions import setup_exception_handlers
from .db.session import get_db
from .services.websocket_manager import connection_manager

logger = logging.getLogger("karen.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager:
    - Registers running ASGI event loop for thread-safe WebSocket broadcasts.
    - Initiates 30-second server keepalive heartbeat loop.
    - Cleanly cancels heartbeat task and closes active sockets on shutdown.
    """
    loop = asyncio.get_running_loop()
    connection_manager.set_event_loop(loop)
    heartbeat_task = asyncio.create_task(connection_manager.heartbeat_loop(interval=30.0))
    try:
        yield
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        await connection_manager.close_all()
        connection_manager.set_event_loop(None)


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_tracing_middleware(request: Request, call_next):
    """
    Tracing middleware that:
    1. Accepts incoming X-Request-Id header if present.
    2. Otherwise generates a canonical req-<uuid> identifier.
    3. Propagates request_id through context and response headers.
    """
    client_req_id = request.headers.get("x-request-id")
    request_id = client_req_id.strip() if client_req_id and client_req_id.strip() else generate_request_id()

    set_request_id(request_id)
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


# Register global canonical error envelope handlers
setup_exception_handlers(app)

from .api.routes.incidents import router as incidents_router
from .api.routes.reports import router as reports_router
from .api.routes.websockets import router as websockets_router

app.include_router(reports_router)
app.include_router(incidents_router)
app.include_router(websockets_router)



@app.get("/health", status_code=status.HTTP_200_OK)
def health_check(request: Request, db: Session = Depends(get_db)):
    """
    Health check endpoint:
    - Executes SELECT 1 against PostgreSQL
    - Success => canonical 200 response
    - Database failure => canonical 503 response
    - Never exposes credentials, stack traces, or internal secrets
    """
    req_id = getattr(request.state, "request_id", None) or get_request_id()
    try:
        db.execute(text("SELECT 1"))
        return success_response(
            data={
                "status": "healthy",
                "database": "connected",
            },
            status_code=status.HTTP_200_OK,
            request_id=req_id,
        )
    except Exception as exc:
        logger.error("Health check database probe failed: %s", exc)
        return error_response(
            code="DATABASE_UNAVAILABLE",
            message="Database connection failed",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            request_id=req_id,
        )
