# src/afsc_pipeline/quality_filter.py
"""
Quality filtering and light normalization for extracted KSA items.

This module sits between the raw extraction/enhancement steps and the
downstream deduplication / graph-writing stages. Its job is to:

- Remove obviously noisy or out-of-domain items.
- Enforce minimum/maximum length constraints.
- Apply optional GEOINT-focused biasing rules.
- Optionally require ESCO alignment for low-confidence skills.
- Canonicalize certain phrases to a preferred surface form.
- Perform *exact* deduplication on (item_type, text) pairs.

The goal is to ensure that only reasonably clean, on-topic items move
forward into semantic deduplication (FAISS) and graph persistence.
"""

from __future__ import annotations

import os
import re
from typing import List, Tuple

from afsc_pipeline.extract_laiser import ItemDraft, ItemType

# ---------------------------------------------------------------------------
# Environment-backed knobs
# ---------------------------------------------------------------------------
# These helpers read boolean/float flags from the environment, allowing
# behavior to be tuned without code changes (e.g., in Streamlit, Codespaces,
# or a containerized deployment).
# ---------------------------------------------------------------------------


def _get_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes"}


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


# Length constraints for item text
MIN_LEN = int(os.getenv("QUALITY_MIN_LEN", "3"))
MAX_LEN_SKILL = int(os.getenv("QUALITY_MAX_LEN", "80"))
MAX_LEN_KA = int(os.getenv("QUALITY_MAX_LEN_KA", "150"))  # Higher limit for Knowledge/Ability

# If a SKILL's confidence is below this, we may require ESCO (strict mode)
# and/or a GEOINT hint (geoint_bias mode).
LOW_CONF_SKILL = _get_float("LOW_CONF_SKILL_THRESHOLD", 0.60)


# ---------------------------------------------------------------------------
# Domain hints / canonicalization
# ---------------------------------------------------------------------------
# GEOINT_HINT:
#     Regex capturing GEOINT / targeting / imagery / geospatial cues.
#
# BANNED:
#     Known-bad phrases that should never appear in the final KSA set.
#
# CANON_MAP:
#     Canonical text replacements for certain common variants.
# ---------------------------------------------------------------------------

GEOINT_HINT = re.compile(
    r"\b(imagery|geospatial|geoint|gis|remote sensing|target(ing)?|mensurat|terrain|"
    r"annotation|coordinates?|azimuth|order of battle|brief(ing)?|ipoe|aoc)\b",
    re.I,
)

BANNED = {
    "business intelligence",
    "perform cleaning duties",
    "source (digital game creation systems)",
    "operation of transport equipment",
    "develop defence policies",
}

CANON_MAP = {
    "imagery analysis": "imagery exploitation",
    "mensuration": "geoint mensuration",
    "intelligence briefing": "brief intelligence findings",
}

PUNCT_STRIP = " .,:;()[]{}\"'`""''|/\\"


def _itype_str(t) -> str:
    """Normalize an ItemType or string-like value to a lowercase type name."""
    if hasattr(t, "value"):
        return str(t.value).lower()
    return str(t).lower()


def _canon_text(txt: str) -> str:
    """
    Normalize text for comparison and deduplication.

    - Lowercases and collapses internal whitespace.
    - Strips common leading/trailing punctuation.
    - Applies CANON_MAP overrides when a canonical form is defined.
    """
    t = " ".join((txt or "").strip().lower().split())
    t = t.strip(PUNCT_STRIP)
    return CANON_MAP.get(t, t)


def _has_esco(it: ItemDraft) -> bool:
    """Return True if the item has a non-empty ESCO identifier."""
    return bool((getattr(it, "esco_id", "") or "").strip())


def _get_max_len(itype: str) -> int:
    """
    Return the appropriate max length based on item type.
    
    Skills use stricter limits (80 chars) since they should be concise.
    Knowledge and Ability items are naturally more verbose (150 chars).
    """
    if itype == "skill":
        return MAX_LEN_SKILL
    else:
        return MAX_LEN_KA


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_quality_filter(
    items: List[ItemDraft],
    *,
    strict_skill_filter: bool = _get_bool("STRICT_SKILL_FILTER", False),
    geoint_bias: bool = _get_bool("GEOINT_BIAS", False),
) -> List[ItemDraft]:
    """
    Prune noisy/out-of-domain items, normalize text, and exact-dedupe.

    Rules (summarized)
    ------------------
    - Drop items with:
        * Empty text
        * Length < QUALITY_MIN_LEN (default: 3)
        * Length > MAX_LEN_SKILL for skills (default: 80)
        * Length > MAX_LEN_KA for knowledge/abilities (default: 150)
        * Text in the BANNED list
    - Normalize item text via `_canon_text` (lowercase, trimmed, punctuation-stripped,
      plus any CANON_MAP replacements).
    - GEOINT bias:
        * If `geoint_bias` is True, SKILLs with confidence < LOW_CONF_SKILL must
          match GEOINT_HINT somewhere in the text or they are dropped.
    - Strict skill filter:
        * If `strict_skill_filter` is True, SKILLs with confidence < LOW_CONF_SKILL
          must have an ESCO ID or they are dropped.
    - Exact deduplication:
        * Final items are deduped on (item_type, normalized_text).

    Parameters
    ----------
    items:
        List of draft items (typically from LAiSER + LLM enhancement).
    strict_skill_filter:
        When True, enforces that low-confidence SKILL items must have ESCO
        alignment to survive the filter.
    geoint_bias:
        When True, enforces that low-confidence SKILL items must show GEOINT
        domain hints (imagery, targeting, geospatial, etc.).

    Returns
    -------
    List[ItemDraft]
        Filtered and normalized items, safe for downstream deduplication
        and graph persistence.
    """
    out: List[ItemDraft] = []
    seen: set[Tuple[str, str]] = set()

    for it in items:
        txt0 = getattr(it, "text", None)
        if not txt0:
            continue

        txt = _canon_text(txt0)
        itype = _itype_str(getattr(it, "item_type", ""))
        
        # Use type-specific max length
        max_len = _get_max_len(itype)
        
        if not txt or len(txt) < MIN_LEN or len(txt) > max_len:
            continue
        if txt in BANNED:
            continue

        conf = float(getattr(it, "confidence", 0.0) or 0.0)

        # GEOINT bias prefers on-topic skills when confidence is low
        if geoint_bias and itype == "skill":
            if conf < LOW_CONF_SKILL and not GEOINT_HINT.search(txt):
                continue

        # When strict, require ESCO for low-confidence skills
        if strict_skill_filter and itype == "skill":
            if conf < LOW_CONF_SKILL and not _has_esco(it):
                continue

        # Update the normalized text back onto the object
        it.text = txt

        sig = (itype, txt)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(it)

    return out
