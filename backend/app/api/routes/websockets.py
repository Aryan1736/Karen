"""
Karen's Ear — Real-Time WebSocket Event Stream
Implements /ws/events strictly matching docs/api-contract.md Section 6 and architecture/realtime.md.
"""
from __future__ import annotations

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.services.websocket_manager import connection_manager

logger = logging.getLogger("karen.backend.api.websockets")

router = APIRouter(tags=["Realtime"])


def _handle_client_frame(client_frame: str, websocket: WebSocket) -> None:
    """
    Process incoming client frame:
    - Parses JSON safely without logging raw unvalidated payload
    - Ingests keepalive PONG responses ({"type": "PONG"} or {"event": "PONG"})
    - Logs unhandled message types or non-dict frames safely
    """
    try:
        message = json.loads(client_frame)
    except Exception:
        # Do not send ERROR events for malformed client frames.
        # Safe operational log: log frame length only, never raw payload.
        logger.warning(
            "Malformed non-JSON client frame received over WebSocket (length: %d)",
            len(client_frame),
        )
        return

    if isinstance(message, dict):
        msg_type = message.get("type") or message.get("event")
        if msg_type == "PONG":
            connection_manager.record_pong(websocket)
        else:
            logger.debug("Received unhandled client message type: %s", msg_type)
    else:
        logger.debug("Received non-dict JSON client frame of type: %s", type(message).__name__)


@router.websocket("/ws/events")
async def websocket_events_endpoint(websocket: WebSocket) -> None:
    """
    Real-time streaming event bus for operator dashboards.
    - Accepts WebSocket connection and registers with in-memory connection manager.
    - Unidirectional event streaming (Server -> Client).
    - Ingests keepalive PONG responses ({"type": "PONG"}).
    - Tolerates {"event": "PONG"} as defensive compatibility input.
    - Malformed client frames do not crash server or emit ERROR frames; ignored/logged safely.
    - Removes dead socket upon client disconnect or socket error.
    """
    await connection_manager.connect(websocket)
    try:
        while True:
            # Read incoming frames from client (e.g. keepalive PONG)
            try:
                client_frame = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception as recv_err:
                logger.warning("Error receiving WebSocket text: %s", recv_err)
                break

            _handle_client_frame(client_frame, websocket)
    except Exception as exc:
        logger.warning("WebSocket connection encountered unhandled error: %s", exc)
    finally:
        connection_manager.disconnect(websocket)
