"""
Karen's Ear — Connection Manager & Event Broadcaster
Manages in-memory WebSocket connections, heartbeat keepalive, and thread-safe
concurrent broadcasting from synchronous REST routes to the ASGI event loop.
Adheres strictly to architecture/realtime.md and docs/api-contract.md Section 6.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any, Optional
from fastapi import WebSocket

from backend.app.core.envelope import format_utc_now
from backend.app.schemas.websocket import SimulationPulsePayload

logger = logging.getLogger("karen.backend.websocket")

HEARTBEAT_INTERVAL_SECONDS = 30.0


class ConnectionManager:
    """
    In-memory registry of active WebSocket connections for a single-worker deployment.
    Guarantees:
    - All active connection mutations occur on the ASGI event loop.
    - Synchronous worker threads safely schedule broadcasts via asyncio.run_coroutine_threadsafe.
    - Send errors on dead/broken sockets are isolated and pruned without affecting healthy clients.
    - Dead clients are removed upon WebSocketDisconnect, receive failure, or send failure.
    - No server-side forced disconnect for missing PONG (last_pong tracked for observability only).
    """

    def __init__(self) -> None:
        self._active_connections: set[WebSocket] = set()
        self._connection_meta: dict[WebSocket, dict[str, Any]] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: Optional[asyncio.AbstractEventLoop]) -> None:
        """Register the running ASGI event loop."""
        self._loop = loop

    def get_event_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        """Retrieve the registered or currently running event loop."""
        if self._loop is not None and self._loop.is_running():
            return self._loop
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                return loop
        except RuntimeError:
            pass
        return None

    @property
    def active_connections_count(self) -> int:
        """Return the number of currently active connections."""
        return len(self._active_connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept handshake and register client connection."""
        await websocket.accept()
        self._active_connections.add(websocket)
        self._connection_meta[websocket] = {
            "connected_at": format_utc_now(),
            "last_pong": format_utc_now(),
        }
        logger.info(
            "WebSocket client connected. Active connections: %d",
            len(self._active_connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Safely remove a client connection and clean up its metadata."""
        self._active_connections.discard(websocket)
        self._connection_meta.pop(websocket, None)
        logger.info(
            "WebSocket client disconnected. Active connections: %d",
            len(self._active_connections),
        )

    def record_pong(self, websocket: WebSocket) -> None:
        """Update last_pong timestamp for observability upon receiving client PONG."""
        if websocket in self._connection_meta:
            self._connection_meta[websocket]["last_pong"] = format_utc_now()
            logger.debug("Received PONG from client; updated last_pong")

    def get_last_pong(self, websocket: WebSocket) -> Optional[str]:
        """Retrieve last recorded PONG timestamp for observability/testing."""
        meta = self._connection_meta.get(websocket)
        return meta["last_pong"] if meta else None

    async def close_all(self) -> None:
        """Close all active connections during application shutdown."""
        sockets = list(self._active_connections)
        for ws in sockets:
            try:
                await ws.close(code=1000)
            except Exception:
                pass
            self.disconnect(ws)

    async def broadcast(self, event: str, payload: dict[str, Any]) -> None:
        """
        Concurrently broadcast an event to all connected clients.
        Enforces canonical envelope with ONLY: event, payload, timestamp.
        Isolates client send exceptions; prunes dead sockets afterward.
        """
        envelope = {
            "event": event,
            "payload": payload,
            "timestamp": format_utc_now(),
        }

        # Snapshot current connections on the event loop
        sockets = list(self._active_connections)
        if not sockets:
            return

        async def _send_to_client(ws: WebSocket) -> Optional[WebSocket]:
            try:
                await ws.send_json(envelope)
                return None
            except Exception as send_err:
                logger.warning("Failed to send WebSocket frame to client: %s", send_err)
                return ws

        # Concurrently dispatch to all clients so one slow client doesn't serially block others
        results = await asyncio.gather(*[_send_to_client(ws) for ws in sockets], return_exceptions=True)

        dead_sockets: list[Any] = []
        for res in results:
            if res is not None and not isinstance(res, Exception):
                dead_sockets.append(res)

        for dead in dead_sockets:
            self.disconnect(dead)


    def broadcast_sync(self, event: str, payload: dict[str, Any]) -> None:
        """
        Thread-safe bridge to schedule an async broadcast from synchronous REST routes.
        Best-effort: errors during dispatch are logged and never raised to caller.
        """
        try:
            loop = self.get_event_loop()
            if loop is not None and loop.is_running():
                try:
                    current_loop = asyncio.get_running_loop()
                except RuntimeError:
                    current_loop = None

                if current_loop is loop:
                    task = loop.create_task(self.broadcast(event=event, payload=payload))
                    def _log_task_result(t: asyncio.Task) -> None:
                        try:
                            t.result()
                        except Exception as exc:
                            logger.error("Exception in task WebSocket broadcast for %s: %s", event, exc)
                    task.add_done_callback(_log_task_result)
                else:
                    fut = asyncio.run_coroutine_threadsafe(
                        self.broadcast(event=event, payload=payload),
                        loop,
                    )
                    def _log_future_result(f: concurrent.futures.Future[None]) -> None:
                        try:
                            f.result()
                        except Exception as exc:
                            logger.error("Exception in scheduled WebSocket broadcast for %s: %s", event, exc)
                    fut.add_done_callback(_log_future_result)
            else:
                logger.warning("No running ASGI event loop available for WebSocket broadcast (%s)", event)
        except Exception as exc:
            logger.error("Failed to dispatch WebSocket broadcast for %s: %s", event, exc)

    async def send_heartbeat(self) -> None:
        """Broadcasts server PING heartbeat matching canonical envelope."""
        await self.broadcast(
            event="PING",
            payload={},
        )

    async def heartbeat_loop(self, interval: float = HEARTBEAT_INTERVAL_SECONDS) -> None:
        """Background keepalive loop broadcasting PING every 30s."""
        try:
            while True:
                await asyncio.sleep(interval)
                await self.send_heartbeat()
        except asyncio.CancelledError:
            logger.debug("Heartbeat loop cancelled.")
            raise


# Global singleton ConnectionManager instance
connection_manager = ConnectionManager()


def broadcast_event(event: str, payload: dict[str, Any]) -> None:
    """Public helper to broadcast an event across all WebSocket clients."""
    connection_manager.broadcast_sync(event=event, payload=payload)


def broadcast_simulation_pulse(injected_count: int, total_simulated: int, scenario: str) -> None:
    """Reusable broadcast helper for SIMULATION_PULSE events."""
    pulse = SimulationPulsePayload(
        injected_count=injected_count,
        total_simulated=total_simulated,
        scenario=scenario,
    )
    broadcast_event("SIMULATION_PULSE", pulse.model_dump(mode="json"))
