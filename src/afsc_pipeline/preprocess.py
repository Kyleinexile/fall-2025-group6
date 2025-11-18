# src/afsc_pipeline/preprocess.py
"""
Preprocessing utilities for AFSC text.

This module normalizes raw AFOCD/AFECD excerpts into a single, clean
narrative block that downstream components (LAiSER, LLMs, etc.) can
consume reliably.

Key responsibilities:
- Strip out tables, code fences, and page headers/footers
- Fix common PDF artifacts (hyphenated line breaks, odd spacing)
- Collapse whitespace and newlines into a single, readable paragraph
"""

from __future__ import annotations

import re
import textwrap

# ---------------------------------------------------------------------------
# Precompiled regular expressions
# ---------------------------------------------------------------------------
# These are compiled once at import time for speed and readability.
# They target common artifacts seen in AFOCD/AFECD-style PDF text.
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")
_CODE_FENCE = re.compile(r"```.+?```", re.DOTALL)
_TABLE_ROW = re.compile(r"^(\s*\|.*\|)\s*$", re.MULTILINE)  # markdown-style tables
_PAGE_HEADER = re.compile(
    r"^\s*(DAFECD|AFECD|AFI|AFMAN|USSF).*$",
    re.IGNORECASE | re.MULTILINE,
)
_PAGE_FOOTER = re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE)  # bare page numbers
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")  # some- \n thing -> something
_NOTE_TRAILER = re.compile(r"^\s*NOTE:.*$", re.IGNORECASE | re.MULTILINE)


def clean_afsc_text(raw: str) -> str:
    """
    Perform light, AFSC-specific cleanup to produce a single narrative block.

    Steps
    -----
    - Dedent and strip leading/trailing whitespace.
    - Remove code fences, markdown-style tables, and simple page footers.
    - Remove common classification headers (AFECD / DAFECD / AFI / etc.) and
      trailing NOTE: sections that are not part of the core narrative.
    - Fix hyphenated line breaks introduced by PDF wrapping.
    - Normalize line endings and collapse all whitespace to single spaces.

    Parameters
    ----------
    raw:
        Raw text extracted from AFOCD/AFECD (potentially noisy, multi-line).

    Returns
    -------
    str
        A cleaned, single-paragraph string suitable for LAiSER and LLM input.
        Returns an empty string if the input is falsy.
    """
    if not raw:
        return ""

    # Normalize indentation / leading whitespace
    txt = textwrap.dedent(raw).strip()

    # Remove code fences (defensive for copied markdown snippets)
    txt = _CODE_FENCE.sub(" ", txt)

    # Remove obvious tables and single-number footers
    txt = _TABLE_ROW.sub(" ", txt)
    txt = _PAGE_FOOTER.sub(" ", txt)

    # Remove common headers (AFECD/DAFECD/etc.) and NOTE trailers
    txt = _PAGE_HEADER.sub(" ", txt)
    txt = _NOTE_TRAILER.sub(" ", txt)

    # Normalize line breaks; fix hyphenated wraps first
    txt = _HYPHEN_BREAK.sub(r"\1\2", txt)
    txt = txt.replace("\r", "\n")

    # Collapse whitespace/newlines to single spaces
    txt = _WS.sub(" ", txt)

    return txt.strip()
