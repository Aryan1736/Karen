"""
Karen's Ear — FastAPI Backend Application Entrypoint
Foundation setup: Request IDs, canonical envelope, error handlers, and /health probe.
DO NOT call Base.metadata.create_all() on startup.
"""
import asyncio
from contextlib import asynccontextmanager
import logging
import os
from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
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
from .core.logging import configure_logging
from .db.session import dispose_engine, get_db
from .services.websocket_manager import connection_manager

# Configure application logging level and formatting from settings.LOG_LEVEL
configure_logging()
logger = logging.getLogger("karen.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager:
    - Verifies single-worker deployment invariant for in-memory WebSocket manager.
    - Registers running ASGI event loop for thread-safe WebSocket broadcasts.
    - Initiates 30-second server keepalive heartbeat loop.
    - Cleanly cancels heartbeat task and closes active sockets on shutdown.
    - Disposes of SQLAlchemy database engine connection pool on shutdown.
    """
    web_concurrency = os.getenv("WEB_CONCURRENCY")
    if web_concurrency:
        try:
            if int(web_concurrency) > 1:
                logger.warning(
                    "WEB_CONCURRENCY is set to %s. Karen's Ear uses an in-memory WebSocket "
                    "ConnectionManager and must be deployed with exactly 1 worker (--workers 1) "
                    "to prevent isolated client registries across processes.",
                    web_concurrency,
                )
        except ValueError:
            pass

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
        dispose_engine()
        logger.info("Database engine pool disposed.")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware for cross-origin frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|.*\.vercel\.app)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
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
from .api.routes.simulation import router as simulation_router
from .api.routes.websockets import router as websockets_router

app.include_router(reports_router)
app.include_router(incidents_router)
app.include_router(simulation_router)
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
        logger.error(
            "[%s] Health check database probe failed: %s",
            req_id,
            type(exc).__name__,
        )
        return error_response(
            code="DATABASE_UNAVAILABLE",
            message="Database connection failed",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            request_id=req_id,
        )
