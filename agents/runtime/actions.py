#!/usr/bin/env python3
"""Compatibility entry point; new code lives in harness.engine.actions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from harness.engine.actions import *

if __name__ == "__main__":
    main()
