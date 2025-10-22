# src/afsc_pipeline/quality_filter.py
from __future__ import annotations

import os
import re
from typing import List, Tuple

from afsc_pipeline.extract_laiser import ItemDraft, ItemType

# ----------------------------
# Environment-backed knobs
# ----------------------------
def _get_bool(name: str, default: bool) -> bool:
    return (os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes"})

def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default

MIN_LEN = int(os.getenv("QUALITY_MIN_LEN", "3"))
MAX_LEN = int(os.getenv("QUALITY_MAX_LEN", "80"))

# If a SKILL's confidence is below this, we may require ESCO (strict mode) or GEOINT hint.
LOW_CONF_SKILL = _get_float("LOW_CONF_SKILL_THRESHOLD", 0.60)

# ----------------------------
# Domain hints / canonicalization
# ----------------------------
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

PUNCT_STRIP = " .,:;()[]{}\"'`“”‘’|/\\"

def _itype_str(t) -> str:
    if hasattr(t, "value"):
        return str(t.value).lower()
    return str(t).lower()

def _canon_text(txt: str) -> str:
    t = " ".join((txt or "").strip().lower().split())
    t = t.strip(PUNCT_STRIP)
    return CANON_MAP.get(t, t)

def _has_esco(it: ItemDraft) -> bool:
    return bool((getattr(it, "esco_id", "") or "").strip())

# ----------------------------
# Public API
# ----------------------------
def apply_quality_filter(
    items: List[ItemDraft],
    *,
    strict_skill_filter: bool = _get_bool("STRICT_SKILL_FILTER", False),
    geoint_bias: bool = _get_bool("GEOINT_BIAS", False),
) -> List[ItemDraft]:
    """
    Prune noisy/out-of-domain items, normalize text, and exact-dedupe.

    Rules (summarized):
      - Drop empty/very short/very long items (QUALITY_MIN_LEN/QUALITY_MAX_LEN).
      - Drop known-bad phrases (BANNED).
      - If KEEP_TYPES coerced everything to SKILL upstream, we still apply SKILL rules below.
      - If geoint_bias: SKILLs with conf < LOW_CONF_SKILL must show a GEOINT_HINT.
      - If strict_skill_filter: SKILLs with conf < LOW_CONF_SKILL must have ESCO.
      - Canonicalize text via CANON_MAP (lowercased, trimmed, punctuation-stripped).
      - Exact dedupe on (item_type, text).
    """
    out: List[ItemDraft] = []
    seen: set[Tuple[str, str]] = set()

    for it in items:
        txt0 = getattr(it, "text", None)
        if not txt0:
            continue

        txt = _canon_text(txt0)
        if not txt or len(txt) < MIN_LEN or len(txt) > MAX_LEN:
            continue
        if txt in BANNED:
            continue

        itype = _itype_str(getattr(it, "item_type", ""))
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
