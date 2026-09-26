"""
Karen's Ear — Raw Emergency Report Ingestion Route
Implements POST /reports matching docs/api-contract.md Section 3.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from backend.app.core.envelope import get_request_id, success_response
from backend.app.db.session import get_db
from backend.app.schemas.report import RawReportCreate
from backend.app.services.ingestion import IngestionService
from backend.app.services.ml_adapter import get_ml_adapter

logger = logging.getLogger("karen.backend.api.reports")

router = APIRouter(tags=["Reports"])


def get_current_ingestion_service(db: Session = Depends(get_db)) -> IngestionService:
    """Dependency provider for IngestionService."""
    return IngestionService(db=db, ml_adapter=get_ml_adapter())


@router.post(
    "/reports",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
    summary="Ingest Emergency Dispatch Report",
    description="Primary entry point for citizens, simulator, and external data feeds. Guarantees durable append-only raw logging and automated tactical correlation.",
)
def submit_report(
    payload: RawReportCreate,
    request: Request,
    service: IngestionService = Depends(get_current_ingestion_service),
) -> Response:
    """
    Ingests a raw emergency report:
    1. Validates and durably records raw report payload.
    2. Runs advisory ML analysis.
    3. Correlates against active incidents and performs deterministic fusion.
    4. Computes deterministic triage priority.
    5. Returns canonical ReportIngestResult envelope.
    """
    req_id = getattr(request.state, "request_id", None) or get_request_id()

    result = service.ingest_report(payload)

    return success_response(
        data=result.model_dump(mode="json"),
        status_code=status.HTTP_201_CREATED,
        request_id=req_id,
    )
