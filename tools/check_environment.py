"""
Karen's Ear — Link Verification Tool: Environment & Project Memory
Checks Python, Node.js, Git remote, and mandatory project-memory files.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


def check_python() -> bool:
    v = sys.version_info
    print(f"  Python Version: {v.major}.{v.minor}.{v.micro}")
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        print("  [FAIL] Python 3.10+ required")
        return False
    return True


def check_node() -> bool:
    node_path = shutil.which("node")
    if not node_path:
        print("  [FAIL] Node.js not found in PATH")
        return False
    res = subprocess.run([node_path, "--version"], capture_output=True, text=True)
    version = res.stdout.strip()
    print(f"  Node.js Version: {version}")
    return True


def check_git() -> bool:
    git_path = shutil.which("git")
    if not git_path:
        print("  [FAIL] Git not found in PATH")
        return False
    res = subprocess.run(["git", "remote", "-v"], cwd=WORKSPACE_ROOT, capture_output=True, text=True)
    out = res.stdout
    if "https://github.com/Aryan1736/Karen" in out or "git@github.com:Aryan1736/Karen" in out:
        print("  Git Remote: Aryan1736/Karen (Verified)")
        return True
    print(f"  [WARN] Unexpected Git remote: {out.strip()}")
    return False


def check_files() -> bool:
    required_files = [
        "gemini.md",
        "task_plan.md",
        "findings.md",
        "progress.md",
        ".gitignore",
        ".env.example",
    ]
    missing = []
    for f in required_files:
        p = WORKSPACE_ROOT / f
        if not p.exists():
            missing.append(f)
    if missing:
        print(f"  [FAIL] Missing required files: {missing}")
        return False
    print("  Project Memory Files: Verified (gemini.md, task_plan.md, findings.md, progress.md)")
    print("  Config Files: Verified (.gitignore, .env.example)")
    return True


def main() -> int:
    print("\n--- [CHECK: Environment & Files] ---")
    py_ok = check_python()
    node_ok = check_node()
    git_ok = check_git()
    files_ok = check_files()

    if py_ok and node_ok and git_ok and files_ok:
        print(">>> RESULT: [PASS]")
        return 0
    else:
        print(">>> RESULT: [FAIL]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
