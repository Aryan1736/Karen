"""
Karen's Ear — Link Verification Tool: PostgreSQL Connectivity
Verifies that PostgreSQL is reachable, executes a minimal SELECT 1, and reports version.
Never exposes credentials in logs.
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(WORKSPACE_ROOT / ".env", override=True)
except ImportError:
    pass

import psycopg2


def mask_url(url: str) -> str:
    """Mask password in connection URI."""
    try:
        parsed = urlparse(url)
        netloc = ""
        if parsed.username:
            netloc += parsed.username
            if parsed.password:
                netloc += ":****"
            netloc += "@"
        netloc += parsed.hostname or "localhost"
        if parsed.port:
            netloc += f":{parsed.port}"
        return f"{parsed.scheme}://{netloc}{parsed.path}"
    except Exception:
        return "<DATABASE_URL masked>"


def main() -> int:
    print("\n--- [CHECK: PostgreSQL Connectivity] ---")
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("  DATABASE_URL: MISSING in environment / .env")
        print("  [FAIL] Please configure DATABASE_URL in .env")
        print(">>> RESULT: [FAIL]")
        return 1

    print("  DATABASE_URL: PRESENT")
    print(f"  Target: {mask_url(db_url)}")

    try:
        conn = psycopg2.connect(db_url, connect_timeout=5)
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            result = cur.fetchone()
            cur.execute("SHOW server_version;")
            version = cur.fetchone()[0]

        conn.close()

        if result and result[0] == 1:
            print(f"  Handshake (SELECT 1): Successful")
            print(f"  PostgreSQL Server Version: {version}")
            print(">>> RESULT: [PASS]")
            return 0
        else:
            print("  [FAIL] Unexpected query result")
            print(">>> RESULT: [FAIL]")
            return 1

    except Exception as e:
        print(f"  [FAIL] PostgreSQL Connection Error: {e}")
        print(">>> RESULT: [FAIL]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
