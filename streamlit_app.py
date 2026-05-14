"""Entry point for Streamlit Cloud.

Adjusts the Python path so `from jobcopilot...` imports work in the
deployment environment, then loads the real dashboard module.
"""
import sys
from pathlib import Path

SRC_DIR = Path(__file__).parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import runpy
runpy.run_module("jobcopilot.ui.dashboard", run_name="__main__")
