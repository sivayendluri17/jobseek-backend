"""Detect employment type (Full-time / C2C / W2 contract) from job data.

Aggregators give a coarse type (FULLTIME / CONTRACTOR). The C2C-vs-W2
distinction lives in the description text, written inconsistently by
recruiters. We parse conservatively: only tag C2C or W2 when the text is
reasonably clear, otherwise fall back to generic CONTRACT rather than guess.
"""
from __future__ import annotations

import re

from ..models.job import EmploymentType

# Corp-to-Corp signals
_C2C = re.compile(
    r"\bc2c\b|\bc-2-c\b|corp[\s-]*to[\s-]*corp|corp[\s-]*2[\s-]*corp"
    r"|corp\.?[\s-]*to[\s-]*corp",
    re.I,
)
# W2 signals
_W2 = re.compile(r"\bw2\b|\bw-2\b|w2 (only|contract|position|role)", re.I)

# Explicit "no C2C" — a strong signal the role is W2-only
_NO_C2C = re.compile(r"no\s*c2c|c2c\s*(not|is not)\s*(available|allowed)|w2 only", re.I)

# Generic contract signals (used when aggregator type is ambiguous)
_CONTRACT = re.compile(
    r"\bcontract\b|contractor|contract[\s-]*to[\s-]*hire|\bc2h\b|1099|per diem",
    re.I,
)
_FULLTIME_HINT = re.compile(
    r"full[\s-]*time|full time|permanent|direct hire|fte\b|salaried", re.I
)


def detect_employment_type(
    text: str,
    aggregator_type: str | None = None,
) -> EmploymentType:
    """Classify a role. `text` = title + description (+ any type text).
    `aggregator_type` = the source's own hint, e.g. 'FULLTIME' / 'CONTRACTOR'.
    """
    t = text or ""
    agg = (aggregator_type or "").upper()

    # 1) Explicit W2-only / no-C2C wins for the W2 bucket.
    if _NO_C2C.search(t):
        return EmploymentType.W2_CONTRACT

    has_c2c = bool(_C2C.search(t))
    has_w2 = bool(_W2.search(t))

    # 2) Both mentioned (e.g. "W2 / C2C") -> it's open to C2C, so C2C bucket
    #    (consultancy candidates filtering for C2C want to see these).
    if has_c2c:
        return EmploymentType.C2C
    if has_w2:
        return EmploymentType.W2_CONTRACT

    # 3) Aggregator says contractor, or text mentions contract -> generic contract.
    if agg in ("CONTRACTOR", "CONTRACT", "TEMPORARY") or _CONTRACT.search(t):
        return EmploymentType.CONTRACT

    # 4) Aggregator says full-time, or full-time hints -> full-time.
    if agg in ("FULLTIME", "FULL_TIME", "PERMANENT") or _FULLTIME_HINT.search(t):
        return EmploymentType.FULLTIME

    # 5) Default: company-board roles etc. are full-time.
    return EmploymentType.FULLTIME
