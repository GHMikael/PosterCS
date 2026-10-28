"""Stable filesystem locations for the self-contained research workspace."""

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
RESEARCH_ROOT = PACKAGE_ROOT.parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parents[2]

CONFIG_ROOT = RESEARCH_ROOT / "configs"
DATA_ROOT = RESEARCH_ROOT / "data"
RESULTS_ROOT = RESEARCH_ROOT / "results"
RUNS_ROOT = RESEARCH_ROOT / "runs"
