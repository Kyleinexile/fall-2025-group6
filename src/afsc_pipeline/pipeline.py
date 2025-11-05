# src/afsc_pipeline/pipeline.py
from __future__ import annotations

import os
import time
from typing import Any, Dict, List

# Local pipeline modules
from afsc_pipeline.extract_laiser import extract_ksa_items, ItemDraft, ItemType
from afsc_pipeline.preprocess import clean_afsc_text
from afsc_pipeline.graph_writer import upsert_afsc_and_items
from afsc_pipeline.audit import log_extract_event
from afsc_pipeline.quality_filter import apply_quality_filter

# Optional: fuzzy/near-duplicate canonicalization.
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
        _USE_LLM_ENHANCER = False


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
    print(f"[PIPELINE] Processing AFSC {afsc_code}, cleaned text length: {len(clean_text)}")

    # ---- Extraction (LAiSER or fallback) ----
    try:
        extract_result = extract_ksa_items(clean_text)
        # Accept both a plain list and an object with `.items`
        items: List[ItemDraft] = (
            extract_result
            if isinstance(extract_result, list)
            else list(getattr(extract_result, "items", []))
        )
        print(f"[PIPELINE] Extracted {len(items)} raw items")
    except Exception as e:
        print(f"[PIPELINE] Extraction error: {e}")
        errors.append(f"extract_error:{type(e).__name__}")
        items = []

    if not items:
        items = _fallback_items(clean_text)
        used_fallback = True
        print(f"[PIPELINE] Used fallback, got {len(items)} items")

    n_items_raw = len(items)

    # ---- Filter by confidence / item types (if requested) ----
    if min_confidence > 0:
        items = [it for it in items if (it.confidence or 0.0) >= min_confidence]
        print(f"[PIPELINE] After confidence filter (>={min_confidence}): {len(items)} items")

    if not keep_types:
        # If KEEP_TYPES=false, coerce everything to 'skill' (simple UX mode)
        for it in items:
            it.item_type = ItemType.SKILL
        print(f"[PIPELINE] Coerced all types to SKILL")

    # ---- Optional LLM enhancement ----
    if _USE_LLM_ENHANCER and items:
        try:
            print(f"[PIPELINE] Running LLM enhancement...")
            items = enhance_items_with_llm(items, context=clean_text)
            print(f"[PIPELINE] After LLM enhancement: {len(items)} items")
        except Exception as e:
            print(f"[PIPELINE] LLM enhancement error: {e}")
            errors.append(f"llm_enhance_error:{type(e).__name__}")

    # ---- Quality filter (using imported module version) ----
    try:
        items = apply_quality_filter(
            items,
            strict_skill_filter=strict_skill_filter,
            geoint_bias=geoint_bias,
        )
        print(f"[PIPELINE] After quality filter: {len(items)} items")
    except Exception as e:
        print(f"[PIPELINE] Quality filter error: {e}")
        errors.append(f"quality_filter_error:{type(e).__name__}")

    n_items_after_filters = len(items)

    # ---- Optional canonicalization / near-dup dedupe ----
    try:
        if aggressive_dedupe:
            items = canonicalize_items(items)
            print(f"[PIPELINE] After dedupe: {len(items)} items")
    except Exception as e:
        print(f"[PIPELINE] Dedupe error: {e}")
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
        print(f"[PIPELINE] Wrote to Neo4j: {write_stats}")
    except Exception as e:
        print(f"[PIPELINE] Write error: {e}")
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
    
    # Show sample items with ESCO
    sample_items = []
    for it in items[:5]:  # First 5 items
        sample_items.append({
            "text": it.text[:60],
            "type": it.item_type.value,
            "conf": round(it.confidence, 2),
            "esco": it.esco_id or "none"
        })
    
    print(f"[PIPELINE] Sample items with ESCO tags:")
    for s in sample_items:
        print(f"  - {s['type']}: {s['text']} (conf={s['conf']}, esco={s['esco']})")
    
    summary = {
        "afsc": afsc_code,
        "n_items_raw": n_items_raw,
        "n_items_after_filters": n_items_after_filters,
        "n_items_after_dedupe": n_items_after_dedupe,
        "esco_tagged_count": esco_tagged_count,
        "used_fallback": used_fallback,
        "errors": errors,
        "duration_ms": duration_ms,
        "write_stats": write_stats,
        "items": items,  # Include full items for inspection
    }
    
    print(f"[PIPELINE] Complete: {n_items_after_dedupe} items, {esco_tagged_count} with ESCO, {duration_ms}ms")
    return summary
