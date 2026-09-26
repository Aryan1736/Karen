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
                raw_text = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception as recv_err:
                logger.warning("Error receiving WebSocket text: %s", recv_err)
                break

            try:
                message = json.loads(raw_text)
            except Exception:
                # Do not send ERROR events for malformed client frames. Ignore/log safely.
                logger.warning("Malformed non-JSON client frame received over WebSocket: %s", raw_text)
                continue

            if isinstance(message, dict):
                msg_type = message.get("type") or message.get("event")
                if msg_type == "PONG":
                    connection_manager.record_pong(websocket)
                else:
                    logger.debug("Received unhandled client message: %s", message)
            else:
                logger.debug("Received non-dict JSON client frame: %s", message)
    except Exception as exc:
        logger.warning("WebSocket connection encountered unhandled error: %s", exc)
    finally:
        connection_manager.disconnect(websocket)
