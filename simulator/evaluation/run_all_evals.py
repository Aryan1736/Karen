"""
Karen's Ear — Backward Compatibility Re-export for evaluation.run_all_evals.

All canonical implementations now reside in the top-level evaluation/ package.
"""

from evaluation.run_all_evals import *

if __name__ == "__main__":
    import sys
    sys.exit(main())
