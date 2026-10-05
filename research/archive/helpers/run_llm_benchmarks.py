"""Compatibility entry point; reusable benchmark lives in the deliverable."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/benchmark_llm.py"), run_name="__main__")
