# src/afsc_pipeline/preprocess.py
from __future__ import annotations

import re
import textwrap

# Precompiled regexes for speed/readability
_WS = re.compile(r"\s+")
_CODE_FENCE = re.compile(r"```.+?```", re.DOTALL)
_TABLE_ROW = re.compile(r"^(\s*\|.*\|)\s*$", re.MULTILINE)  # markdown-style tables
_PAGE_HEADER = re.compile(r"^\s*(DAFECD|AFECD|AFI|AFMAN|USSF).*$", re.IGNORECASE | re.MULTILINE)
_PAGE_FOOTER = re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE)  # bare page numbers on their own line
_SECTION_NUM_GUNK = re.compile(r"\s{2,}")  # collapse long spacing
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")  # fix hyphenated line breaks: some- \n thing -> something
_NOTE_TRAILER = re.compile(r"^\s*NOTE:.*$", re.IGNORECASE | re.MULTILINE)

def clean_afsc_text(raw: str) -> str:
    """
    Light cleanup to give LAiSER a clean, narrative block.
    - Dedent/strip
    - Remove code fences / tables / obvious headers/footers
    - Fix hyphenated line breaks
    - Collapse whitespace to single spaces
    """
    if not raw:
        return ""

    txt = textwrap.dedent(raw).strip()

    # Remove code fences (just in case)
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
