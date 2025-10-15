# src/afsc_pipeline/pipeline.py
from __future__ import annotations

import os
from typing import Any, Dict, List

# Local pipeline modules
from afsc_pipeline.extract_laiser import extract_ksa_items, ItemDraft
from afsc_pipeline.preprocess import clean_afsc_text
from afsc_pipeline.graph_writer import upsert_afsc_and_items
from afsc_pipeline.audit import log_extract_event

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


def run_pipeline(
    afsc_code: str,
    afsc_raw_text: str,
    neo4j_session,
    *,
    min_confidence: float = float(os.getenv("MIN_CONFIDENCE", "0.0")),
    keep_types: bool = (os.getenv("KEEP_TYPES", "true").strip().lower() in {"1", "true", "yes"}),
) -> Dict[str, Any]:
    """
    End-to-end pipeline stage for a single AFSC text blob.

    Parameters
    ----------
    afsc_code : str
        AFSC identifier (e.g., '1N0X1').
    afsc_raw_text : str
        Raw AFSC document/section text.
    neo4j_session :
        An active Neo4j session (e.g., driver.session(database='neo4j')).
    min_confidence : float, optional
        Drop items below this confidence (0.0-1.0). Default from env MIN_CONFIDENCE or 0.0.
    keep_types : bool, optional
        If True, ensures we keep at least one of each item_type (K/S/A) after filtering.

    Returns
    -------
    Dict[str, Any]
        Summary dict for logs/UI.
    """

    # --- 1) Preprocess / clean the AFSC text ---
    cleaned = clean_afsc_text(afsc_raw_text)

    # --- 2) Extraction (LAiSER with robust fallback; includes ESCO tags when available) ---
    extract_result = extract_ksa_items(cleaned)
    items: List[ItemDraft] = list(extract_result.items)

    # --- 3) Optional: confidence filtering ---
    if min_confidence > 0.0:
        items = [it for it in items if it.confidence >= min_confidence]

    # --- 4) Optional: keep at least one of each type (K/S/A) ---
    if keep_types:
        if not any(it.item_type.value == "knowledge" for it in items):
            candidates = [it for it in extract_result.items if it.item_type.value == "knowledge"]
            if candidates:
                items.append(sorted(candidates, key=lambda x: x.confidence, reverse=True)[0])
        if not any(it.item_type.value == "skill" for it in items):
            candidates = [it for it in extract_result.items if it.item_type.value == "skill"]
            if candidates:
                items.append(sorted(candidates, key=lambda x: x.confidence, reverse=True)[0])
        if not any(it.item_type.value == "ability" for it in items):
            candidates = [it for it in extract_result.items if it.item_type.value == "ability"]
            if candidates:
                items.append(sorted(candidates, key=lambda x: x.confidence, reverse=True)[0])

    # --- 5) Optional: LLM enhancement (adds extra K/A) ---
    if _USE_LLM_ENHANCER:
        try:
            extra = enhance_items_with_llm(afsc_code, cleaned, items)
            if extra:
                items.extend(extra)
        except Exception:
            # Hardening: silently skip if any provider/parse error occurs
            pass

    # --- 6) Dedupe / canonicalize ---
    items_canon: List[ItemDraft] = canonicalize_items(items) if items else []

    # --- 7) Graph write (idempotent upserts) ---
    write_stats = upsert_afsc_and_items(
        session=neo4j_session,
        afsc_code=afsc_code,
        items=items_canon,
    )

    # --- 8) Audit / metrics ---
    log_extract_event(
        afsc_code=afsc_code,
        used_fallback=extract_result.used_fallback,
        errors=extract_result.errors,
        duration_ms=extract_result.duration_ms,
        n_items=len(items_canon),
        write_stats=write_stats,
    )

    # --- 9) Return a concise summary for CLI/UI logging ---
    esco_tagged_count = sum(1 for it in items_canon if (it.esco_id or "").strip())
    return {
        "afsc": afsc_code,
        "n_items_raw": len(extract_result.items),
        "n_items_after_filters": len(items),
        "n_items_after_dedupe": len(items_canon),
        "esco_tagged_count": esco_tagged_count,
        "used_fallback": extract_result.used_fallback,
        "errors": extract_result.errors,
        "duration_ms": extract_result.duration_ms,
        "write_stats": write_stats,
    }
