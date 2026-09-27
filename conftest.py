import sys
from pathlib import Path

# Ensure Karen directory is on sys.path
karen_dir = str(Path(__file__).resolve().parent)
if karen_dir not in sys.path:
    sys.path.insert(0, karen_dir)
