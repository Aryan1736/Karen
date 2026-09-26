"""
Karen's Ear — Performance & Resource Evaluation Module.

Feature 11 — Quantitative Evaluation Layer.
Measures runtime execution characteristics of the ML pipeline:
- Cold-start latency (time for first inference triggering lazy model initialization)
- Warm latency distribution (p50, p90, p95, p99, mean, min, max)
- Inference throughput (reports/sec)
- Process memory footprint & RSS delta (measured via psutil)
- Benchmark environment metadata (Python version, OS, CPU architecture, timestamp)

CRITICAL BENCHMARK INTEGRITY NOTICE:
- Cold-start is isolated from warm latency samples.
- Memory measurements report process Resident Set Size (RSS) and peak working set.
- An RSS delta is explicitly NOT labeled as exact model tensor weights.
- Platform-sensitive working set behavior is explicitly documented.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from ml.evaluation.metrics import calculate_percentiles
from ml.pipeline import inference_engine
from ml.pipeline.inference_engine import InferenceEngine
from ml.tests.fixtures.incident_benchmark import INCIDENT_BENCHMARK_DATASET


@dataclass
class EnvironmentMetadata:
    """Hardware and runtime environment characteristics."""

    python_version: str
    platform: str
    operating_system: str
    architecture: str
    processor: str
    process_pid: int
    model_version: str


@dataclass
class ColdStartMemoryMetrics:
    """Process memory measurements in fresh subprocess during cold start."""

    methodology: str
    initial_rss_mb: float
    post_inference_rss_mb: float
    rss_delta_mb: float
    peak_working_set_mb: float | None
    limitation_notice: str


@dataclass
class ColdStartMetrics:
    """Isolated cold-start latency and memory metrics from fresh subprocess."""

    methodology: str  # "fresh subprocess first full inference"
    definition: str
    latency_ms: float
    unit: str
    memory: ColdStartMemoryMetrics
    subprocess_pid: int | None = None


@dataclass
class MemoryUsageMetrics:
    """Process memory measurements and methodology (legacy alias)."""

    methodology: str
    initial_rss_mb: float
    post_cold_rss_mb: float
    cold_load_delta_mb: float
    final_rss_mb: float
    peak_working_set_mb: float | None
    limitation_notice: str


@dataclass
class LatencyDistribution:
    """Latency percentiles and descriptive statistics in milliseconds."""

    unit: str
    warmup_samples: int = 0
    timed_samples: int = 0
    p50_ms: float = 0.0
    p90_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    mean_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    std_ms: float = 0.0
    throughput_items_per_sec: float = 0.0
    sample_count: int = 0
    definition: str = (
        "Latency of inference_engine.analyze(...) after model/runtime initialization "
        "and untimed warm-up have completed."
    )

    def __post_init__(self) -> None:
        if self.timed_samples == 0 and self.sample_count > 0:
            self.timed_samples = self.sample_count
        elif self.sample_count == 0 and self.timed_samples > 0:
            self.sample_count = self.timed_samples


@dataclass
class PerformanceEvaluationResult:
    """Consolidated quantitative results from performance benchmarking."""

    fixture_name: str
    environment: EnvironmentMetadata
    cold_start: ColdStartMetrics
    warm_latency: LatencyDistribution
    elapsed_seconds: float

    @property
    def cold_start_latency_ms(self) -> float:
        """Alias for backward compatibility."""
        return self.cold_start.latency_ms

    @property
    def memory(self) -> ColdStartMemoryMetrics:
        """Alias for backward compatibility."""
        return self.cold_start.memory

    def to_dict(self) -> dict[str, Any]:
        """Converts performance results to a JSON-serializable dictionary."""
        return {
            "fixture_name": self.fixture_name,
            "environment": asdict(self.environment),
            "cold_start": {
                "methodology": self.cold_start.methodology,
                "definition": self.cold_start.definition,
                "latency_ms": round(self.cold_start.latency_ms, 2),
                "unit": self.cold_start.unit,
                "memory": asdict(self.cold_start.memory),
            },
            "cold_start_latency_ms": round(self.cold_start.latency_ms, 2),
            "warm_latency": asdict(self.warm_latency),
            "memory": asdict(self.cold_start.memory),
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }


COLD_START_SUBPROCESS_SCRIPT = """
import sys
import json
import time
import os

try:
    import psutil
    proc = psutil.Process(os.getpid())
    def get_mem():
        info = proc.memory_info()
        rss = round(info.rss / (1024 * 1024), 2)
        peak = round(info.peak_wset / (1024 * 1024), 2) if hasattr(info, "peak_wset") else None
        return rss, peak
except Exception:
    def get_mem():
        return 0.0, None

initial_rss, _ = get_mem()

# Read sample payload from stdin
payload = json.loads(sys.stdin.read())
text = payload.get("text", "")
report_id = payload.get("report_id", "perf-cold-subprocess")

t_start = time.perf_counter()

from ml.pipeline import inference_engine
result = inference_engine.analyze(text, report_id=report_id)

latency_ms = (time.perf_counter() - t_start) * 1000.0

post_rss, peak_wset = get_mem()
rss_delta = round(max(0.0, post_rss - initial_rss), 2)

out = {
    "methodology": "fresh subprocess first full inference",
    "definition": "Time from fresh subprocess execution immediately before ML initialization through completion of first full inference_engine.analyze(...) call.",
    "latency_ms": round(latency_ms, 2),
    "unit": "milliseconds",
    "memory": {
        "methodology": "Fresh subprocess Resident Set Size (RSS) and peak working set via psutil",
        "initial_rss_mb": initial_rss,
        "post_inference_rss_mb": post_rss,
        "rss_delta_mb": rss_delta,
        "peak_working_set_mb": peak_wset,
        "limitation_notice": "Process RSS reflects operating system virtual memory pages resident in RAM (Python runtime, PyTorch/ONNX runtime allocations, shared libraries). It represents process-level memory rather than isolated neural-network parameter weights."
    },
    "result_status": result.get("status"),
    "pid": os.getpid()
}

print("__COLD_START_METRICS__:" + json.dumps(out))
"""


class PerformanceEvaluator:
    """
    Evaluator for latency, throughput, cold start, and memory profiling.
    """

    def __init__(self, engine: InferenceEngine | None = None) -> None:
        self.engine = engine or inference_engine

    def _collect_environment(self) -> EnvironmentMetadata:
        """Captures host system and Python environment details without duplicate timestamps."""
        config = getattr(self.engine, "config", None)
        model_version = getattr(config, "model_version", "1.0.0") if config else "1.0.0"
        return EnvironmentMetadata(
            python_version=sys.version.split()[0],
            platform=platform.platform(),
            operating_system=platform.system(),
            architecture=platform.machine(),
            processor=platform.processor() or "Unknown",
            process_pid=os.getpid(),
            model_version=str(model_version),
        )

    def _get_process_memory_mb(self) -> tuple[float, float | None]:
        """
        Reads current process RSS (MB) and peak working set (MB) via psutil.
        Falls back safely if psutil is unavailable or platform lacks peak metric.
        """
        try:
            import psutil
            proc = psutil.Process(os.getpid())
            mem_info = proc.memory_info()
            rss_mb = round(mem_info.rss / (1024 * 1024), 2)
            peak_mb: float | None = None
            if hasattr(mem_info, "peak_wset"):
                peak_mb = round(mem_info.peak_wset / (1024 * 1024), 2)
            return rss_mb, peak_mb
        except Exception:
            return 0.0, None

    def _run_cold_start_subprocess(self, cold_sample: str) -> ColdStartMetrics:
        """
        Executes a true cold-start measurement in an isolated, fresh Python subprocess.
        Measures:
        - Latency from immediately before ML initialization through completion of analyze().
        - Process memory (initial RSS, post-inference RSS, RSS delta, peak working set)
          via psutil inside the fresh subprocess.
        """
        project_root = Path(__file__).resolve().parents[2]
        env = os.environ.copy()
        python_path = str(project_root)
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{python_path}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = python_path

        input_payload = json.dumps({"text": cold_sample, "report_id": "perf-cold-subprocess"})

        proc = subprocess.run(
            [sys.executable, "-c", COLD_START_SUBPROCESS_SCRIPT],
            input=input_payload,
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env=env,
            timeout=180,
        )

        if proc.returncode != 0:
            raise RuntimeError(
                f"Cold-start subprocess failed with exit code {proc.returncode}:\n"
                f"STDOUT:\n{proc.stdout}\n"
                f"STDERR:\n{proc.stderr}"
            )

        marker = "__COLD_START_METRICS__:"
        for line in proc.stdout.splitlines():
            if line.startswith(marker):
                data = json.loads(line[len(marker):])
                mem_data = data["memory"]
                mem_obj = ColdStartMemoryMetrics(
                    methodology=mem_data["methodology"],
                    initial_rss_mb=mem_data["initial_rss_mb"],
                    post_inference_rss_mb=mem_data["post_inference_rss_mb"],
                    rss_delta_mb=mem_data["rss_delta_mb"],
                    peak_working_set_mb=mem_data.get("peak_working_set_mb"),
                    limitation_notice=mem_data["limitation_notice"],
                )
                return ColdStartMetrics(
                    methodology=data["methodology"],
                    definition=data["definition"],
                    latency_ms=data["latency_ms"],
                    unit=data["unit"],
                    memory=mem_obj,
                    subprocess_pid=data.get("pid"),
                )

        raise RuntimeError(
            f"Cold-start subprocess did not emit metrics marker.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    def evaluate(
        self,
        samples: Sequence[str] | None = None,
        warm_trials: int = 25,
        warmup_trials: int = 2,
        use_subprocess_cold_start: bool = True,
        fixture_name: str = "INCIDENT_BENCHMARK_DATASET",
    ) -> PerformanceEvaluationResult:
        """
        Executes performance benchmarking measuring:
        1. Cold-start in an isolated fresh subprocess.
        2. Untimed parent-process warm-up ensuring model weights & caches are resident.
        3. N timed warm inferences without outlier filtering.
        4. Warm throughput calculated purely from timed samples.
        """
        t_total_start = time.perf_counter()
        env = self._collect_environment()

        benchmark_texts: list[str] = (
            list(samples)
            if samples
            else [item.text for item in INCIDENT_BENCHMARK_DATASET]
        )
        if not benchmark_texts:
            raise ValueError("Performance benchmark requires at least one text sample")

        cold_sample = benchmark_texts[0]
        warm_samples = benchmark_texts[:warm_trials]
        while len(warm_samples) < warm_trials:
            warm_samples.extend(benchmark_texts[: (warm_trials - len(warm_samples))])

        # ----------------------------------------------------------------------
        # 1. Cold-Start Measurement (Isolated Fresh Subprocess)
        # ----------------------------------------------------------------------
        is_mock = self.engine is not None and not isinstance(self.engine, InferenceEngine)
        if use_subprocess_cold_start and not is_mock:
            cold_start = self._run_cold_start_subprocess(cold_sample)
        else:
            initial_rss, _ = self._get_process_memory_mb()
            t_cold_0 = time.perf_counter()
            _ = self.engine.analyze(cold_sample, report_id="perf-cold-01")
            cold_latency_ms = (time.perf_counter() - t_cold_0) * 1000.0
            post_cold_rss, peak_wset = self._get_process_memory_mb()
            cold_rss_delta = round(max(0.0, post_cold_rss - initial_rss), 2)
            cold_start = ColdStartMetrics(
                methodology="in-process first full inference (mock/test mode)",
                definition="Time for in-process engine.analyze(...) call.",
                latency_ms=round(cold_latency_ms, 2),
                unit="milliseconds",
                memory=ColdStartMemoryMetrics(
                    methodology="In-process Resident Set Size (RSS) via psutil",
                    initial_rss_mb=initial_rss,
                    post_inference_rss_mb=post_cold_rss,
                    rss_delta_mb=cold_rss_delta,
                    peak_working_set_mb=peak_wset,
                    limitation_notice=(
                        "Process RSS reflects operating system virtual memory pages resident in RAM, "
                        "including Python runtime, PyTorch/ONNX runtime allocations, and shared libraries. "
                        "It represents process-level memory rather than isolated neural-network parameter weights."
                    ),
                ),
                subprocess_pid=os.getpid(),
            )

        # ----------------------------------------------------------------------
        # 2. Parent-Process Model Warm-Up (Untimed)
        # ----------------------------------------------------------------------
        # Before starting the timed warm-latency loop:
        # 1. Ensure the canonical ML pipeline is fully initialized.
        # 2. Execute untimed warm-up calls through inference_engine.analyze(...).
        # These warm-up calls ensure sentence-transformers, tokenizers, and class
        # prototype embeddings are loaded into memory and are strictly EXCLUDED
        # from warm latency statistics and percentiles.
        warmup_count = max(0, warmup_trials)
        for w_idx in range(warmup_count):
            w_text = benchmark_texts[w_idx % len(benchmark_texts)]
            _ = self.engine.analyze(w_text, report_id=f"perf-warmup-{w_idx:03d}")

        # ----------------------------------------------------------------------
        # 3. Timed Warm Latency Measurements (In-Process)
        # ----------------------------------------------------------------------
        # Timed calls are executed on the genuinely warmed pipeline.
        # No arbitrary outlier filtering or percentile clipping is applied.
        warm_latencies_ms: list[float] = []

        for idx, text in enumerate(warm_samples):
            t0 = time.perf_counter()
            _ = self.engine.analyze(text, report_id=f"perf-warm-{idx:03d}")
            lat_ms = (time.perf_counter() - t0) * 1000.0
            warm_latencies_ms.append(lat_ms)

        # Latency statistics computed purely from timed warm calls
        percentiles = calculate_percentiles(warm_latencies_ms, (50.0, 90.0, 95.0, 99.0))
        mean_ms = round(float(np.mean(warm_latencies_ms)), 2)
        min_ms = round(float(np.min(warm_latencies_ms)), 2)
        max_ms = round(float(np.max(warm_latencies_ms)), 2)
        std_ms = round(float(np.std(warm_latencies_ms)), 2)

        total_warm_sec = sum(warm_latencies_ms) / 1000.0
        throughput = round(len(warm_latencies_ms) / total_warm_sec, 2) if total_warm_sec > 0 else 0.0

        latency_dist = LatencyDistribution(
            unit="milliseconds",
            warmup_samples=warmup_count,
            timed_samples=len(warm_latencies_ms),
            p50_ms=percentiles["p50"],
            p90_ms=percentiles["p90"],
            p95_ms=percentiles["p95"],
            p99_ms=percentiles["p99"],
            mean_ms=mean_ms,
            min_ms=min_ms,
            max_ms=max_ms,
            std_ms=std_ms,
            throughput_items_per_sec=throughput,
            sample_count=len(warm_latencies_ms),
            definition=(
                "Latency of inference_engine.analyze(...) after model/runtime initialization "
                "and untimed warm-up have completed."
            ),
        )

        elapsed = time.perf_counter() - t_total_start

        return PerformanceEvaluationResult(
            fixture_name=fixture_name,
            environment=env,
            cold_start=cold_start,
            warm_latency=latency_dist,
            elapsed_seconds=elapsed,
        )

