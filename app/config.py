"""Configuration — loads your curated target company list."""
from __future__ import annotations

from pathlib import Path

import yaml

COMPANIES_FILE = Path(__file__).resolve().parent / "companies.yaml"


def load_companies() -> dict[str, list[str]]:
    """Return {"greenhouse": [...slugs], "lever": [...slugs]}."""
    if not COMPANIES_FILE.exists():
        return {}
    data = yaml.safe_load(COMPANIES_FILE.read_text()) or {}
    return {k: list(v or []) for k, v in data.items()}
