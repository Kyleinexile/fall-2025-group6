# src/afsc_pipeline/pipeline.py
from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List

# Local pipeline modules
from afsc_pipeline.extract_laiser import extract_ksa_items, ItemDraft, ItemType
from afsc_pipeline.preprocess import clean_afsc_text
from afsc_pipeline.graph_writer import upsert_afsc_and_items
from afsc_pipeline.audit import log_extract_event
from afsc_pipeline.quality_filter import apply_quality_filter

# Optional: fuzzy/near-duplicate canonicalization.
# If your dedupe stage isn't implemented yet, we no-op gracefully.
try:
    from afsc_pipeline.dedupe import canonicalize_items  # type: ignore
except Exception:
    def canonicalize_items(items: List[ItemDraft]) -> List[ItemDraft]:
        return items

# Optional: LLM enhancer (disabled by default via env)
_USE_LLM_ENHANCER = (os.getenv("USE_LLM_ENHANCER") or "false").strip().lower() in {"1", "true", "yes"}
if _USE_LLM_ENHANCER:
    try:
        from afsc_pipeline.enhance_llm import enhance_items_with_llm  # type: ignore
    except Exception:
        _USE_LLM_ENHANCER = False  # fail closed if import not available


# ----------------------------
# Quality filter utilities
# ----------------------------
_GEOINT_HINT = re.compile(
    r"\b(imagery|geospatial|geoint|gis|remote sensing|target|mensurat|terrain|annotation|coordinates|azimuth|order of battle|brief|ipoe|aoc)\b",
    re.I,
)

# things we’ve seen slip in that aren’t helpful for GEOINT demo
_BANNED = {
    "business intelligence",
    "perform cleaning duties",
    "source (digital game creation systems)",
    "operation of transport equipment",
    "develop defence policies",
}

# light canonical mapping of frequent variants
_CANON_MAP = {
    "imagery analysis": "imagery exploitation",
    "mensuration": "geoint mensuration",
    "intelligence briefing": "brief intelligence findings",
}

def _itype_str(t) -> str:
    # ItemType Enum -> "skill"/"knowledge"/"ability"
    if hasattr(t, "value"):
        return str(t.value).lower()
    return str(t).lower()

def _canon_text(txt: str) -> str:
    t = " ".join((txt or "").strip().lower().split())
    return t.strip(" .,:;()[]{}")

def quality_filter(
    items: List[ItemDraft],
    *,
    need_esco_for_low: bool = False,
    geoint_bias: bool = False,
    min_len: int = 3,
    max_len: int = 80,
) -> List[ItemDraft]:
    """Prune noisy/out-of-domain items, lightly canonicalize, and exact-dedupe."""
    out: List[ItemDraft] = []
    seen: set[tuple[str, str]] = set()
    for it in items:
        if not getattr(it, "text", None):
            continue

        txt0 = it.text
        txt = _canon_text(txt0)
        if not txt or len(txt) < min_len or len(txt) > max_len:
            continue
        if txt in _BANNED:
            continue

        itype = _itype_str(getattr(it, "item_type", ""))
        conf = float(getattr(it, "confidence", 0.0) or 0.0)
        esco = (getattr(it, "esco_id", "") or "").strip()

        # Prefer GEOINT-ish skills; trim weak off-topic ones
        if geoint_bias and itype == "skill":
            if not _GEOINT_HINT.search(txt) and conf < 0.60:
                continue

        # Require ESCO for low-confidence skills (keeps AF terms if high conf)
        if need_esco_for_low and itype == "skill":
            if conf < 0.60 and not esco:
                continue

        # canonical text normalization
        txt = _CANON_MAP.get(txt, txt)
        it.text = txt

        sig = (itype, txt)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(it)

    return out


def _fallback_items(clean_text: str) -> List[ItemDraft]:
    """
    Extremely light heuristic fallback so a run still produces something.
    """
    text_lower = clean_text.lower()
    out: List[ItemDraft] = []
    # Very naive splits
    if "knowledge" in text_lower:
        out.append(ItemDraft(text="knowledge of intelligence cycle", item_type=ItemType.KNOWLEDGE, confidence=0.2, source="fallback"))
    if "skill" in text_lower:
        out.append(ItemDraft(text="imagery exploitation", item_type=ItemType.SKILL, confidence=0.2, source="fallback"))
    if "abilit" in text_lower:
        out.append(ItemDraft(text="brief intelligence findings", item_type=ItemType.ABILITY, confidence=0.2, source="fallback"))
    if not out:
        out.append(ItemDraft(text="general geospatial intelligence competence", item_type=ItemType.SKILL, confidence=0.1, source="fallback"))
    return out


def run_pipeline(
    afsc_code: str,
    afsc_raw_text: str,
    neo4j_session,
    *,
    # existing knobs
    min_confidence: float = float(os.getenv("MIN_CONFIDENCE", "0.0")),
    keep_types: bool = (os.getenv("KEEP_TYPES", "true").strip().lower() in {"1", "true", "yes"}),
    # NEW quality knobs (env-backed)
    strict_skill_filter: bool = (os.getenv("STRICT_SKILL_FILTER", "false").strip().lower() in {"1", "true", "yes"}),
    geoint_bias: bool = (os.getenv("GEOINT_BIAS", "false").strip().lower() in {"1", "true", "yes"}),
    aggressive_dedupe: bool = (os.getenv("AGGRESSIVE_DEDUPE", "true").strip().lower() in {"1", "true", "yes"}),
) -> Dict[str, Any]:
    """
    End-to-end pipeline stage for a single AFSC text blob.
    - Clean text
    - Extract K/S/A items (LAiSER or fallback)
    - Optional LLM enhancement
    - Quality filter (domain/length/ESCO gating + canonical map + exact dedupe)
    - Optional near-dup canonicalization
    - Write to Neo4j
    - Emit telemetry
    """
    t0 = time.time()
    used_fallback = False
    errors: List[str] = []

    clean_text = clean_afsc_text(afsc_raw_text or "")

    # ---- Extraction (LAiSER or fallback) ----
    try:
        extract_result = extract_ksa_items(clean_text)
        # Accept both a plain list and an object with `.items`
        items: List[ItemDraft] = (
            extract_result
            if isinstance(extract_result, list)
            else list(getattr(extract_result, "items", []))
        )
    except Exception as e:
        errors.append(f"extract_error:{type(e).__name__}")
        items = []

    if not items:
        items = _fallback_items(clean_text)
        used_fallback = True

    n_items_raw = len(items)

    # ---- Filter by confidence / item types (if requested) ----
    if min_confidence > 0:
        items = [it for it in items if (it.confidence or 0.0) >= min_confidence]

    if not keep_types:
        # If KEEP_TYPES=false, coerce everything to 'skill' (simple UX mode)
        for it in items:
            it.item_type = ItemType.SKILL

    # ---- Optional LLM enhancement ----
    if _USE_LLM_ENHANCER and items:
        try:
            items = enhance_items_with_llm(items, context=clean_text)
        except Exception as e:
            errors.append(f"llm_enhance_error:{type(e).__name__}")

    # ---- Quality filter (before near-dup canonicalization) ----
    try:
        items = quality_filter(
            items,
            need_esco_for_low=strict_skill_filter,
            geoint_bias=geoint_bias,
        )
    except Exception as e:
        errors.append(f"quality_filter_error:{type(e).__name__}")

    n_items_after_filters = len(items)

    # ---- Optional canonicalization / near-dup dedupe ----
    try:
        items = canonicalize_items(items) if aggressive_dedupe else items
    except Exception as e:
        errors.append(f"dedupe_error:{type(e).__name__}")

    n_items_after_dedupe = len(items)

    # ---- Write to Neo4j ----
    write_stats: Dict[str, int] = {}
    try:
        write_stats = upsert_afsc_and_items(
            session=neo4j_session,
            afsc_code=afsc_code,
            items=items,
        )
    except Exception as e:
        errors.append(f"write_error:{type(e).__name__}")

    duration_ms = int((time.time() - t0) * 1000)

    # ---- Telemetry ----
    try:
        log_extract_event(
            afsc_code=afsc_code,
            n_items_written=n_items_after_dedupe,
            used_fallback=used_fallback,
            errors=errors,
            duration_ms=duration_ms,
            write_stats=write_stats,
        )
    except Exception:
        # Best-effort logging; never fail the pipeline on telemetry
        pass

    # ---- Return a compact summary for CLI/debug ----
    esco_tagged_count = sum(1 for it in items if (it.esco_id or "").strip())
    return {
        "afsc": afsc_code,
        "n_items_raw": n_items_raw,
        "n_items_after_filters": n_items_after_filters,
        "n_items_after_dedupe": n_items_after_dedupe,
        "esco_tagged_count": esco_tagged_count,
        "used_fallback": used_fallback,
        "errors": errors,
        "duration_ms": duration_ms,
        "write_stats": write_stats,
    }
