"""
Karen's Ear — Safe Simulator Transport & Ingestion Bridge.

Owner: Pankaj (feature/evaluation-integration)
Authority: gemini.md (v1.2), docs/api-contract.md (v1.0), DISASTER_SIMULATOR_ROADMAP.md
Status: Production-Hardened Transport Architecture

This module provides:
1. prepare_payload(): Pre-flight leakage firewall verifying zero GroundTruth leakage.
2. BaseTransport: Canonical interface for simulation event dispatches.
3. DryRunTransport: Zero-dependency local dry-run transport for hermetic validation.
4. SafeHttpTransport: Resilient production HTTP client for POST /reports:
   - Token Bucket Rate Limiter
   - Exponential backoff retries with jitter
   - Three-state Circuit Breaker (CLOSED, OPEN, HALF_OPEN)
   - Zero-Data-Loss Event Buffer (preserves order on flush failure, prevents silent dropping)
   - Real measured latency profiling (P50, P95, mean)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import math
import random
import threading
import time
from typing import Any, Callable, Coroutine, Deque, Dict, List, Optional, Tuple, Union

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from simulator.models import (
    GroundTruthLeakageError,
    ScenarioEvent,
    verify_no_ground_truth_leakage,
)

logger = logging.getLogger("simulator.transport")


# =============================================================================
# 1. Custom Exceptions
# =============================================================================

class TransportDispatchError(RuntimeError):
    """Raised when transport dispatch permanently fails after all retries."""
    pass


class BufferOverflowError(RuntimeError):
    """Raised when event buffer capacity is exceeded, refusing to silently discard emergency reports."""
    pass


# =============================================================================
# 2. Pre-Flight Ground Truth Firewall
# =============================================================================

def prepare_payload(event: ScenarioEvent) -> Dict[str, Any]:
    """
    Extracts the public RawReport dictionary and validates safety invariants.

    Invariants Checked:
      1. is_synthetic is strictly True.
      2. source is strictly 'simulator'.
      3. No private evaluator GroundTruth keys exist anywhere in the payload (recursive).

    Raises:
      GroundTruthLeakageError: If any safety invariant is violated.
    """
    payload = event.public_payload()

    # Invariant 1: Synthetic flag strictly True
    if payload.get("is_synthetic") is not True:
        raise GroundTruthLeakageError(
            f"SAFETY VIOLATION in event '{event.event_id}': is_synthetic must be True."
        )

    # Invariant 2: Source strictly 'simulator'
    if payload.get("source") != "simulator":
        raise GroundTruthLeakageError(
            f"SAFETY VIOLATION in event '{event.event_id}': source must be 'simulator'."
        )

    # Invariant 3: Recursive Ground Truth Firewall across all nested structures
    verify_no_ground_truth_leakage(payload, path="prepare_payload")

    return payload


# =============================================================================
# 3. Circuit Breaker
# =============================================================================

class CircuitState(str, Enum):
    CLOSED = "CLOSED"        # Normal operation: traffic flows
    OPEN = "OPEN"            # Tripped: fail-fast and buffer locally
    HALF_OPEN = "HALF_OPEN"  # Testing: send probe requests to test backend recovery


class CircuitBreaker:
    """
    Three-state circuit breaker to protect the backend and prevent simulator hangs.
    Thread-safe and throttles probe requests during HALF_OPEN recovery.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 10.0,
        success_threshold: int = 2,
    ) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_timeout_seconds = max(0.1, recovery_timeout_seconds)
        self.success_threshold = max(1, success_threshold)

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._half_open_in_flight = 0
        self._opened_at: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN and self._opened_at is not None:
                if time.monotonic() - self._opened_at >= self.recovery_timeout_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._consecutive_successes = 0
                    self._half_open_in_flight = 0
                    logger.info("Circuit breaker transitioned to HALF_OPEN (probing backend).")
            return self._state

    def can_attempt(self) -> bool:
        """Returns True if a request is permitted to proceed."""
        with self._lock:
            if self._state == CircuitState.OPEN and self._opened_at is not None:
                if time.monotonic() - self._opened_at >= self.recovery_timeout_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._consecutive_successes = 0
                    self._half_open_in_flight = 0
                    logger.info("Circuit breaker transitioned to HALF_OPEN (probing backend).")

            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.HALF_OPEN:
                # Allow a controlled probe request to test backend health
                if self._half_open_in_flight < 1:
                    self._half_open_in_flight += 1
                    return True
                return False
            return False

    def record_success(self) -> None:
        """Records a successful dispatch."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_in_flight = max(0, self._half_open_in_flight - 1)
                self._consecutive_successes += 1
                if self._consecutive_successes >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._consecutive_failures = 0
                    self._opened_at = None
                    logger.info("Circuit breaker closed: backend recovered.")
            else:
                self._consecutive_failures = 0

    def record_failure(self) -> None:
        """Records a failed dispatch attempt."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_in_flight = max(0, self._half_open_in_flight - 1)
            self._consecutive_failures += 1
            if self._state == CircuitState.HALF_OPEN or self._consecutive_failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                logger.warning(
                    f"Circuit breaker tripped OPEN ({self._consecutive_failures} failures). "
                    f"Buffering requests for {self.recovery_timeout_seconds}s."
                )

    def reset(self) -> None:
        """Explicitly resets circuit breaker to CLOSED."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            self._half_open_in_flight = 0
            self._opened_at = None


# =============================================================================
# 4. Rate Limiter (Token Bucket)
# =============================================================================

class RateLimiter:
    """Token bucket rate limiter ensuring ingestion requests respect system capacity."""

    def __init__(self, rate_per_second: float = 10.0, capacity: Optional[float] = None) -> None:
        self.rate = max(0.1, float(rate_per_second))
        self.capacity = max(1.0, float(capacity) if capacity is not None else self.rate)
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, block: bool = True) -> bool:
        """Acquires a token, optionally blocking until available."""
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return True

                if not block:
                    return False

                sleep_duration = (1.0 - self.tokens) / self.rate
            time.sleep(max(0.001, sleep_duration))


# =============================================================================
# 5. Zero-Data-Loss Event Buffer
# =============================================================================

class EventBuffer:
    """
    Explicit, ordered event buffer that refuses to silently drop reports.
    """

    def __init__(self, max_capacity: int = 1000) -> None:
        self.max_capacity = max(1, max_capacity)
        self._queue: Deque[ScenarioEvent] = deque()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._queue)

    def append(self, event: ScenarioEvent) -> None:
        """Appends an event, raising BufferOverflowError if capacity is exceeded."""
        with self._lock:
            if len(self._queue) >= self.max_capacity:
                raise BufferOverflowError(
                    f"EventBuffer capacity of {self.max_capacity} exceeded. "
                    "Refusing to silently drop emergency disaster report."
                )
            self._queue.append(event)

    def popleft(self) -> ScenarioEvent:
        with self._lock:
            return self._queue.popleft()

    def prepend_all(self, events: List[ScenarioEvent]) -> None:
        """Prepends events back to the front of the queue, preserving their exact original order."""
        with self._lock:
            for event in reversed(events):
                self._queue.appendleft(event)

    def drain_all(self) -> List[ScenarioEvent]:
        with self._lock:
            items = list(self._queue)
            self._queue.clear()
            return items

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()

    def to_list(self) -> List[ScenarioEvent]:
        with self._lock:
            return list(self._queue)


# =============================================================================
# 6. Transport Data Models
# =============================================================================

@dataclass
class TransportConfig:
    """Configuration settings for Transport."""
    endpoint: str = "http://localhost:8000/reports"
    timeout_seconds: float = 5.0
    max_retries: int = 3
    backoff_factor: float = 0.5
    rate_limit_per_sec: float = 10.0
    dry_run: bool = True
    buffer_on_failure: bool = True
    max_buffer_size: int = 1000


@dataclass
class TransportResult:
    """Outcome of a dispatch attempt."""
    success: bool
    report_id: str
    event_id: str
    status_code: Optional[int] = None
    response_body: Optional[Dict[str, Any]] = None
    latency_ms: float = 0.0
    retries: int = 0
    buffered: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "report_id": self.report_id,
            "event_id": self.event_id,
            "status_code": self.status_code,
            "latency_ms": round(self.latency_ms, 2),
            "retries": self.retries,
            "buffered": self.buffered,
            "error": self.error,
        }


# =============================================================================
# 7. Base Transport Interface
# =============================================================================

class BaseTransport(ABC):
    """Abstract base class establishing the unified Transport interface."""

    @abstractmethod
    def send_event(self, event: ScenarioEvent) -> TransportResult:
        """Dispatches a ScenarioEvent."""
        pass

    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Returns transport execution metrics."""
        pass


# =============================================================================
# 8. Dry-Run Transport
# =============================================================================

class DryRunTransport(BaseTransport):
    """
    Hermetic offline transport that validates safety invariants and records
    dispatches without opening any network connections.
    """

    def __init__(self) -> None:
        self._dispatches: List[ScenarioEvent] = []
        self._start_time = time.perf_counter()

    def send_event(self, event: ScenarioEvent) -> TransportResult:
        t0 = time.perf_counter()
        # Verify safety firewall
        prepare_payload(event)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self._dispatches.append(event)
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return TransportResult(
            success=True,
            report_id=event.dispatch.report_id,
            event_id=event.event_id,
            status_code=201,
            response_body={
                "success": True,
                "data": {
                    "report_id": event.dispatch.report_id,
                    "status": "DRY_RUN_ACCEPTED",
                },
                "error": None,
                "request_id": f"req-dryrun-{event.event_id}",
                "timestamp": now_iso,
            },
            latency_ms=elapsed_ms,
            retries=0,
            buffered=False,
        )

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_dispatches": len(self._dispatches),
            "successful_dispatches": len(self._dispatches),
            "failed_dispatches": 0,
            "buffered_events_remaining": 0,
            "circuit_state": "CLOSED",
            "mode": "DRY_RUN",
        }


# =============================================================================
# 9. Production Safe HTTP Transport
# =============================================================================

class SafeHttpTransport(BaseTransport):
    """
    Canonical synchronous production transport with full resilience:
      - Ground-truth recursive leakage firewall
      - Token bucket rate limiting
      - 3-state Circuit Breaker
      - Exponential backoff retries with jitter
      - Zero-data-loss event buffering
      - Real measured latency profiling
    """

    def __init__(
        self,
        config: Optional[TransportConfig] = None,
        endpoint: Optional[str] = None,
        dry_run: Optional[bool] = None,
        mock_handler: Optional[Callable[[Dict[str, Any]], Tuple[int, Dict[str, Any]]]] = None,
    ) -> None:
        if config is not None:
            self.config = config
        else:
            self.config = TransportConfig()

        if endpoint is not None:
            self.config.endpoint = endpoint
            if dry_run is None:
                self.config.dry_run = False

        if dry_run is not None:
            self.config.dry_run = dry_run

        self.mock_handler = mock_handler

        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout_seconds=5.0,
            success_threshold=2,
        )
        self.rate_limiter = RateLimiter(rate_per_second=self.config.rate_limit_per_sec)
        self.buffer = EventBuffer(max_capacity=self.config.max_buffer_size)

        # Performance and latency metrics tracking
        self._latencies: List[float] = []
        self._total_dispatches = 0
        self._successful_dispatches = 0
        self._failed_dispatches = 0
        self._buffered_count = 0
        self._client: Optional[Any] = None

    @property
    def buffer_size(self) -> int:
        return len(self.buffer)

    def clear_buffer(self) -> None:
        self.buffer.clear()

    def get_buffered_events(self) -> List[ScenarioEvent]:
        return self.buffer.to_list()

    def send_event(self, event: ScenarioEvent) -> TransportResult:
        """
        Dispatches a ScenarioEvent synchronously after verifying firewall invariants.
        """
        self._total_dispatches += 1

        # 1. Pre-flight Leakage Firewall (raises GroundTruthLeakageError if breached)
        payload = prepare_payload(event)

        # 2. Dry-Run Mode check
        if self.config.dry_run:
            self._successful_dispatches += 1
            return TransportResult(
                success=True,
                report_id=event.dispatch.report_id,
                event_id=event.event_id,
                status_code=201,
                response_body={"success": True, "status": "DRY_RUN_ACCEPTED"},
                latency_ms=0.01,
                retries=0,
                buffered=False,
            )

        # 3. Check Circuit Breaker
        if not self.circuit_breaker.can_attempt():
            if self.config.buffer_on_failure:
                self.buffer.append(event)
                self._buffered_count += 1
                return TransportResult(
                    success=False,
                    report_id=event.dispatch.report_id,
                    event_id=event.event_id,
                    buffered=True,
                    error="Circuit breaker is OPEN. Event buffered locally.",
                )
            return TransportResult(
                success=False,
                report_id=event.dispatch.report_id,
                event_id=event.event_id,
                buffered=False,
                error="Circuit breaker is OPEN. Buffering disabled.",
            )

        # 4. Rate Limiting
        self.rate_limiter.acquire(block=True)

        # 5. Dispatch with Exponential Backoff Retries
        last_error = None
        retries = 0
        is_permanent_client_error = False
        status_code = None

        for attempt in range(self.config.max_retries + 1):
            if attempt > 0:
                retries += 1
                delay = self.config.backoff_factor * (2 ** (attempt - 1)) + random.uniform(0, 0.05)
                time.sleep(delay)

            start_t = time.perf_counter()
            try:
                status_code, body = self._execute_http_post(payload)
                elapsed_ms = (time.perf_counter() - start_t) * 1000.0
                self._latencies.append(elapsed_ms)

                # Check HTTP 2xx status AND canonical API response envelope
                if 200 <= status_code < 300:
                    if isinstance(body, dict) and body.get("success") is False:
                        last_error = f"API Application Error (HTTP {status_code}): {body.get('error')}"
                        # Application rejected report; permanent client error, do not retry or buffer
                        is_permanent_client_error = True
                        break
                    else:
                        self.circuit_breaker.record_success()
                        self._successful_dispatches += 1
                        return TransportResult(
                            success=True,
                            report_id=event.dispatch.report_id,
                            event_id=event.event_id,
                            status_code=status_code,
                            response_body=body,
                            latency_ms=elapsed_ms,
                            retries=retries,
                            buffered=False,
                        )
                elif status_code in (429, 503):
                    # Ingestion throttle / Service Unavailable: honor backoff rather than immediately giving up
                    last_error = f"HTTP {status_code}: {body}"
                    retry_after = 0.5
                    if isinstance(body, dict) and "retry_after" in body:
                        try:
                            retry_after = float(body["retry_after"])
                        except (ValueError, TypeError):
                            pass
                    time.sleep(min(retry_after, 2.0))
                    continue
                elif 400 <= status_code < 500:
                    # Permanent client error (400, 401, 403, 404, 422 Unprocessable Entity)
                    last_error = f"HTTP {status_code} (Permanent Client Rejection): {body}"
                    is_permanent_client_error = True
                    break
                else:
                    # 5xx Server Error
                    last_error = f"HTTP {status_code}: {body}"

            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start_t) * 1000.0
                last_error = str(exc)
                logger.warning(
                    f"Dispatch attempt {attempt + 1}/{self.config.max_retries + 1} failed for {event.event_id}: {exc}"
                )

        # 6. Failure: Record to circuit breaker and buffer only for server/network faults
        self._failed_dispatches += 1
        is_buffered = False

        if not is_permanent_client_error:
            self.circuit_breaker.record_failure()
            if self.config.buffer_on_failure:
                try:
                    self.buffer.append(event)
                    self._buffered_count += 1
                    is_buffered = True
                except BufferOverflowError as overflow_exc:
                    last_error = f"{last_error or 'Dispatch failed'}; Buffer overflow: {overflow_exc}"
                    logger.error(f"Event buffer overflow on {event.event_id}: {overflow_exc}")
                    is_buffered = False

        return TransportResult(
            success=False,
            report_id=event.dispatch.report_id,
            event_id=event.event_id,
            status_code=status_code,
            retries=retries,
            buffered=is_buffered,
            error=last_error or "Unknown dispatch error",
        )

    def _get_or_create_client(self) -> Any:
        if self._client is None or getattr(self._client, "is_closed", False):
            self._client = httpx.Client(timeout=self.config.timeout_seconds)
        return self._client

    def close(self) -> None:
        """Closes underlying persistent HTTP client."""
        if self._client is not None and not getattr(self._client, "is_closed", True):
            self._client.close()

    def __enter__(self) -> "SafeHttpTransport":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _execute_http_post(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """Executes actual HTTP POST via mock handler or persistent httpx client."""
        if self.mock_handler is not None:
            return self.mock_handler(payload)

        if not HAS_HTTPX:
            raise RuntimeError("httpx is required for live network dispatch. Install httpx.")

        client = self._get_or_create_client()
        resp = client.post(
            self.config.endpoint,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Source": "disaster-simulator",
                "X-Request-Id": f"req-sim-{payload.get('report_id', 'unknown')}",
            },
        )
        try:
            body = resp.json()
        except Exception:
            body = {"text": resp.text}
        if isinstance(body, dict) and "Retry-After" in resp.headers:
            body["retry_after"] = resp.headers["Retry-After"]
        return resp.status_code, body

    def flush_buffer(self) -> List[TransportResult]:
        """
        Attempts to re-dispatch all currently buffered events.
        If a dispatch fails at index i:
          Re-buffers every unsent event from i onward in their exact original order!
        Guarantees zero data loss and strict FIFO order preservation with exception safety.
        """
        results: List[TransportResult] = []
        if len(self.buffer) == 0:
            return results

        events_to_flush = self.buffer.drain_all()

        try:
            for idx, event in enumerate(events_to_flush):
                res = self.send_event(event)
                results.append(res)

                # If this event failed (e.g. backend still down or circuit tripped)
                if not res.success:
                    remaining = events_to_flush[idx + 1:]
                    for rem in remaining:
                        self.buffer.append(rem)
                    break
        except Exception:
            # On unexpected crash during flush, restore all un-flushed events safely
            unprocessed = events_to_flush[len(results):]
            for rem in unprocessed:
                self.buffer.append(rem)
            raise

        return results

    async def send_event_async(self, event: ScenarioEvent) -> TransportResult:
        """Asynchronous dispatch offloaded to worker thread to prevent event loop blocking."""
        import asyncio
        return await asyncio.to_thread(self.send_event, event)

    def get_metrics(self) -> Dict[str, Any]:
        """Calculates latency profile (P50, P95, mean) from real observed timings."""
        latencies = sorted(self._latencies)
        p50 = 0.0
        p95 = 0.0
        mean = 0.0

        if latencies:
            p50 = latencies[int(len(latencies) * 0.50)]
            p95 = latencies[min(int(len(latencies) * 0.95), len(latencies) - 1)]
            mean = sum(latencies) / len(latencies)

        return {
            "total_dispatches": self._total_dispatches,
            "successful_dispatches": self._successful_dispatches,
            "failed_dispatches": self._failed_dispatches,
            "buffered_events_remaining": len(self.buffer),
            "circuit_state": self.circuit_breaker.state.value,
            "latency_p50_ms": round(p50, 2) if latencies else None,
            "latency_p95_ms": round(p95, 2) if latencies else None,
            "latency_mean_ms": round(mean, 2) if latencies else None,
        }


# Alias for backward compatibility
SafeTransport = SafeHttpTransport


