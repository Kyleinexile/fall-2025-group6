# src/afsc_pipeline/pipeline.py
"""
End-to-end AFSC extraction pipeline.

High-level flow for a single AFSC:

1. Preprocess raw AFSC text into a clean narrative block.
2. Extract K/S/A items via LAiSER (or a regex fallback).
3. (Optional) Enhance with an LLM to add Knowledge/Ability items.
4. Apply quality filtering (length, domain hints, ESCO gating, exact dedupe).
5. (Optional) Canonicalize / merge near-duplicates (fuzzy dedupe).
6. Write AFSC + items + relationships into Neo4j (idempotent upserts).
7. Emit a compact summary and log an audit event.

This module is intentionally “thin”: it orchestrates specialized helpers in
other modules rather than doing complex logic itself.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List

# Local pipeline modules
from afsc_pipeline.extract_laiser import extract_ksa_items, ItemDraft, ItemType
from afsc_pipeline.preprocess import clean_afsc_text
from afsc_pipeline.graph_writer_v2 import upsert_afsc_and_items
from afsc_pipeline.audit import log_extract_event
from afsc_pipeline.quality_filter import apply_quality_filter

# Optional: fuzzy/near-duplicate canonicalization.
try:
    from afsc_pipeline.dedupe import canonicalize_items  # type: ignore
except Exception:  # pragma: no cover - defensive fallback
    def canonicalize_items(items: List[ItemDraft]) -> List[ItemDraft]:
        """No-op dedupe when the dedupe module is unavailable."""
        return items


# Optional: LLM enhancer (disabled by default via env)
_USE_LLM_ENHANCER = (os.getenv("USE_LLM_ENHANCER") or "false").strip().lower() in {
    "1",
    "true",
    "yes",
}
if _USE_LLM_ENHANCER:
    try:
        from afsc_pipeline.enhance_llm import enhance_items_with_llm  # type: ignore
    except Exception:
        # If import fails, silently disable LLM enhancement.
        _USE_LLM_ENHANCER = False


# --------------------------------------------------------------------------- #
# Fallback extraction (when LAiSER fails hard)
# --------------------------------------------------------------------------- #
def _fallback_items(clean_text: str) -> List[ItemDraft]:
    """
    Extremely light heuristic fallback so a run still produces something.

    This is only used when LAiSER extraction raises or returns nothing.
    The goal is: never return an empty list, so downstream steps and the UI
    have *something* to show.
    """
    text_lower = (clean_text or "").lower()
    out: List[ItemDraft] = []

    # Very naive pattern-based hints
    if "knowledge" in text_lower:
        out.append(
            ItemDraft(
                text="knowledge of intelligence cycle",
                item_type=ItemType.KNOWLEDGE,
                confidence=0.20,
                source="fallback",
            )
        )
    if "skill" in text_lower:
        out.append(
            ItemDraft(
                text="imagery exploitation",
                item_type=ItemType.SKILL,
                confidence=0.20,
                source="fallback",
            )
        )
    if "abilit" in text_lower:
        out.append(
            ItemDraft(
                text="brief intelligence findings",
                item_type=ItemType.ABILITY,
                confidence=0.20,
                source="fallback",
            )
        )

    # Ultra-generic backstop
    if not out:
        out.append(
            ItemDraft(
                text="general geospatial intelligence competence",
                item_type=ItemType.SKILL,
                confidence=0.10,
                source="fallback",
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def run_pipeline(
    afsc_code: str,
    afsc_raw_text: str,
    neo4j_session: Any,
    *,
    # Existing knobs
    min_confidence: float = float(os.getenv("MIN_CONFIDENCE", "0.0")),
    keep_types: bool = (
        os.getenv("KEEP_TYPES", "true").strip().lower() in {"1", "true", "yes"}
    ),
    # Quality knobs (env-backed defaults)
    strict_skill_filter: bool = (
        os.getenv("STRICT_SKILL_FILTER", "false").strip().lower()
        in {"1", "true", "yes"}
    ),
    geoint_bias: bool = (
        os.getenv("GEOINT_BIAS", "false").strip().lower() in {"1", "true", "yes"}
    ),
    aggressive_dedupe: bool = (
        os.getenv("AGGRESSIVE_DEDUPE", "true").strip().lower() in {"1", "true", "yes"}
    ),
) -> Dict[str, Any]:
    """
    Run the full AFSC pipeline for a single specialty description.

    Parameters
    ----------
    afsc_code : str
        AFSC identifier (e.g., "1N0X1", "17D3").
    afsc_raw_text : str
        Raw block of text from AFOCD/AFECD for this AFSC.
    neo4j_session : Any
        An active Neo4j driver session (v5 Python driver).
    min_confidence : float, optional
        Drop items whose confidence is below this threshold (0.0 = no filter).
    keep_types : bool, optional
        If False, coerce all items to SKILL (simplified mode for some UIs).
    strict_skill_filter : bool, optional
        When True, low-confidence skills must have ESCO IDs to survive filter.
    geoint_bias : bool, optional
        When True, prefers GEOINT-ish skills when confidence is low.
    aggressive_dedupe : bool, optional
        When True, apply fuzzy canonicalization to merge near-duplicates.

    Returns
    -------
    Dict[str, Any]
        A summary dict including counts, errors, write stats, and the final items.
    """
    t0 = time.time()
    used_fallback = False
    errors: List[str] = []

    # ------------------------------------------------------------------ #
    # 1) Preprocess
    # ------------------------------------------------------------------ #
    clean_text = clean_afsc_text(afsc_raw_text or "")
    print(
        f"[PIPELINE] Processing AFSC {afsc_code}, "
        f"cleaned text length: {len(clean_text)}"
    )

    # ------------------------------------------------------------------ #
    # 2) Extraction (LAiSER or fallback)
    # ------------------------------------------------------------------ #
    try:
        extract_result = extract_ksa_items(clean_text)
        # Accept both a plain list and an object with `.items`
        items: List[ItemDraft] = (
            extract_result
            if isinstance(extract_result, list)
            else list(getattr(extract_result, "items", []))
        )
        print(f"[PIPELINE] Extracted {len(items)} raw items")
    except Exception as e:  # pragma: no cover - defensive logging
        print(f"[PIPELINE] Extraction error: {e}")
        errors.append(f"extract_error:{type(e).__name__}")
        items = []

    if not items:
        items = _fallback_items(clean_text)
        used_fallback = True
        print(f"[PIPELINE] Used fallback, got {len(items)} items")

    n_items_raw = len(items)

    # ------------------------------------------------------------------ #
    # 3) Confidence + type handling
    # ------------------------------------------------------------------ #
    if min_confidence > 0.0:
        before = len(items)
        items = [it for it in items if (it.confidence or 0.0) >= min_confidence]
        print(
            f"[PIPELINE] After confidence filter (>={min_confidence}): "
            f"{before} -> {len(items)} items"
        )

    if not keep_types:
        # If KEEP_TYPES=false, coerce everything to SKILL (simple UX mode)
        for it in items:
            it.item_type = ItemType.SKILL
        print("[PIPELINE] Coerced all item types to SKILL")

    # ------------------------------------------------------------------ #
    # 4) Optional LLM enhancement (adds new K/A items)
    # ------------------------------------------------------------------ #
    if _USE_LLM_ENHANCER and items:
        try:
            print("[PIPELINE] Running LLM enhancement...")
            before = len(items)
            # enhance_items_with_llm returns *only* new items
            new_items = enhance_items_with_llm(
                afsc_code=afsc_code,
                afsc_text=clean_text,
                items=items,
            )
            items = items + new_items
            print(
                f"[PIPELINE] After LLM enhancement: {before} -> {len(items)} items "
                f"(+{len(new_items)} new)"
            )
        except Exception as e:  # pragma: no cover - defensive logging
            print(f"[PIPELINE] LLM enhancement error: {e}")
            errors.append(f"llm_enhance_error:{type(e).__name__}")

    # ------------------------------------------------------------------ #
    # 5) Quality filter
    # ------------------------------------------------------------------ #
    try:
        before = len(items)
        items = apply_quality_filter(
            items,
            strict_skill_filter=strict_skill_filter,
            geoint_bias=geoint_bias,
        )
        print(
            f"[PIPELINE] After quality filter: {before} -> {len(items)} items"
        )
    except Exception as e:  # pragma: no cover - defensive logging
        print(f"[PIPELINE] Quality filter error: {e}")
        errors.append(f"quality_filter_error:{type(e).__name__}")

    n_items_after_filters = len(items)

    # ------------------------------------------------------------------ #
    # 6) Optional canonicalization / fuzzy dedupe
    # ------------------------------------------------------------------ #
    try:
        if aggressive_dedupe:
            before = len(items)
            items = canonicalize_items(items)
            print(
                f"[PIPELINE] After dedupe: {before} -> {len(items)} items"
            )
    except Exception as e:  # pragma: no cover - defensive logging
        print(f"[PIPELINE] Dedupe error: {e}")
        errors.append(f"dedupe_error:{type(e).__name__}")

    n_items_after_dedupe = len(items)

    # ------------------------------------------------------------------ #
    # 7) Write to Neo4j
    # ------------------------------------------------------------------ #
    write_stats: Dict[str, int] = {}
    try:
        write_stats = upsert_afsc_and_items(
            session=neo4j_session,
            afsc_code=afsc_code,
            items=items,
        )
        print(f"[PIPELINE] Wrote to Neo4j: {write_stats}")
    except Exception as e:  # pragma: no cover - defensive logging
        print(f"[PIPELINE] Write error: {e}")
        errors.append(f"write_error:{type(e).__name__}")

    duration_ms = int((time.time() - t0) * 1000)

    # ------------------------------------------------------------------ #
    # 8) Telemetry (best-effort)
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    # 9) Build and print summary
    # ------------------------------------------------------------------ #
    esco_tagged_count = sum(
        1 for it in items if (getattr(it, "esco_id", "") or "").strip()
    )

    # Show sample items (first few) with ESCO tags for quick sanity checks
    sample_items = []
    for it in items[:5]:
        sample_items.append(
            {
                "text": (it.text or "")[:60],
                "type": getattr(it.item_type, "value", str(it.item_type)),
                "conf": round(float(it.confidence or 0.0), 2),
                "esco": (it.esco_id or "none"),
            }
        )

    print("[PIPELINE] Sample items:")
    for s in sample_items:
        print(
            f"  - {s['type']}: {s['text']} "
            f"(conf={s['conf']}, esco={s['esco']})"
        )

    summary: Dict[str, Any] = {
        "afsc": afsc_code,
        "n_items_raw": n_items_raw,
        "n_items_after_filters": n_items_after_filters,
        "n_items_after_dedupe": n_items_after_dedupe,
        "esco_tagged_count": esco_tagged_count,
        "used_fallback": used_fallback,
        "errors": errors,
        "duration_ms": duration_ms,
        "write_stats": write_stats,
        # Include full items so the Streamlit app / tests can inspect them
        "items": items,
    }

    print(
        f"[PIPELINE] Complete: {n_items_after_dedupe} items, "
        f"{esco_tagged_count} with ESCO, {duration_ms}ms"
    )
    return summary
