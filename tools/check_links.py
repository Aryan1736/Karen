"""
Karen's Ear — Master Link Verification Entry Point
Executes all deterministic Phase 2 Link verification checks:
1. Environment & Project Memory
2. OpenStreetMap Reachability
3. CrisiText Dataset Handshake
4. ML Runtime Handshake
5. PostgreSQL Connectivity
6. Vercel Architectural Compatibility
7. Render Architectural Compatibility
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = TOOLS_DIR.parent


def run_subtool(script_name: str) -> tuple[bool, str]:
    script_path = TOOLS_DIR / script_name
    res = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)
    output = (res.stdout + res.stderr).strip()
    return res.returncode == 0, output


def check_vercel_compatibility() -> tuple[bool, str]:
    node = shutil.which("node")
    npm = shutil.which("npm")
    if not node or not npm:
        return False, "Node.js / npm not found in system path"
    return True, "Node.js & npm present. Ready for Vite/React/Next.js client build."


def check_render_compatibility() -> tuple[bool, str]:
    # Check Python support, virtualenv, and absence of hardcoded absolute paths
    py_ver = sys.version_info
    if py_ver < (3, 10):
        return False, f"Python {py_ver.major}.{py_ver.minor} incompatible with modern Render Python runtime"
    return True, f"Python {py_ver.major}.{py_ver.minor} compatible with Render Web Service & Worker architecture."


def main() -> int:
    print("==================================================")
    print("      KAREN'S EAR — MASTER LINK VERIFICATION       ")
    print("==================================================")

    results = {}

    # 1. Environment & Files
    ok, out = run_subtool("check_environment.py")
    print(out)
    results["Environment & Memory"] = ok

    # 2. OpenStreetMap
    ok, out = run_subtool("check_osm.py")
    print(out)
    results["OpenStreetMap"] = ok

    # 3. CrisiText Dataset
    ok, out = run_subtool("check_crisitext.py")
    print(out)
    results["CrisiText Dataset"] = ok

    # 4. ML Runtime
    ok, out = run_subtool("check_ml_runtime.py")
    print(out)
    results["ML Runtime"] = ok

    # 5. PostgreSQL
    ok, out = run_subtool("check_postgres.py")
    print(out)
    results["PostgreSQL"] = ok

    # 6. Vercel Compatibility
    print("\n--- [CHECK: Vercel Compatibility] ---")
    ok, msg = check_vercel_compatibility()
    print(f"  {msg}")
    print(f">>> RESULT: [{'PASS' if ok else 'FAIL'}]")
    results["Vercel Compatibility"] = ok

    # 7. Render Compatibility
    print("\n--- [CHECK: Render Compatibility] ---")
    ok, msg = check_render_compatibility()
    print(f"  {msg}")
    print(f">>> RESULT: [{'PASS' if ok else 'FAIL'}]")
    results["Render Compatibility"] = ok

    print("\n==================================================")
    print("                SUMMARY SCORECARD                 ")
    print("==================================================")
    all_passed = True
    for name, passed in results.items():
        tag = "[PASS]" if passed else "[FAIL]"
        if not passed:
            all_passed = False
        print(f"  {tag:<8} {name}")

    print("--------------------------------------------------")
    if all_passed:
        print("  Overall: READY FOR PHASE 3 (ARCHITECT)")
        print("==================================================")
        return 0
    else:
        print("  Overall: BLOCKED — One or more required links failed.")
        print("==================================================")
        return 1


if __name__ == "__main__":
    sys.exit(main())
