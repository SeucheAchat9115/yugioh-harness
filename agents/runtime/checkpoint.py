#!/usr/bin/env python3
"""Compatibility entry point; new code lives in harness.storage.checkpoint."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from harness.storage.checkpoint import *

if __name__ == "__main__":
    main()
