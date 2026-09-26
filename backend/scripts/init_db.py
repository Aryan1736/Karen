"""
Karen's Ear — Explicit Database Initialization Script
Executes Base.metadata.create_all(engine) to provision the 7 core operational tables.
Never called automatically at application startup.
"""
import sys
from pathlib import Path

# Ensure workspace root is in sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import inspect
from backend.app.core.config import settings
from backend.app.db.base import Base
from backend.app.db.session import engine
# Explicitly import models to register tables with Base.metadata
import backend.app.models


def init_database() -> int:
    """Create all registered database tables and inspect PostgreSQL state."""
    print("==================================================")
    print("      KAREN'S EAR — DATABASE INITIALIZATION       ")
    print("==================================================")
    print(f"Target Database: {settings.get_masked_db_url()}")

    registered_tables = sorted(list(Base.metadata.tables.keys()))
    print(f"Registered tables in Base.metadata ({len(registered_tables)}):")
    for tbl in registered_tables:
        print(f"  - {tbl}")

    if len(registered_tables) != 7:
        print(f"[FAIL] Expected 7 registered tables, found {len(registered_tables)}")
        return 1

    print("\nExecuting Base.metadata.create_all(engine)...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Schema creation completed successfully.")
    except Exception as e:
        print(f"[FAIL] Error creating tables: {e}")
        return 1

    # Introspect PostgreSQL database to verify tables exist
    inspector = inspect(engine)
    existing_tables = sorted(inspector.get_table_names())
    print(f"\nIntrospected PostgreSQL tables ({len(existing_tables)}):")
    for tbl in existing_tables:
        print(f"  * {tbl}")

    missing_tables = [t for t in registered_tables if t not in existing_tables]
    if missing_tables:
        print(f"\n[FAIL] Missing tables in PostgreSQL: {missing_tables}")
        return 1

    print("\nTable & Index Summary:")
    for tbl in registered_tables:
        indexes = inspector.get_indexes(tbl)
        index_names = [idx["name"] for idx in indexes]
        print(f"  * {tbl}: {len(indexes)} index(es) -> {', '.join(index_names) if index_names else 'PK/default'}")

    print("\n>>> RESULT: [PASS] All 7 tables initialized successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(init_database())
