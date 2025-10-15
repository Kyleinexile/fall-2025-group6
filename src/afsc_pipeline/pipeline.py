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
        out.append(ItemDraft(text="imagery analysis", item_type=ItemType.SKILL, confidence=0.2, source="fallback"))
    if "abilit" in text_lower:
        out.append(ItemDraft(text="briefing and communication", item_type=ItemType.ABILITY, confidence=0.2, source="fallback"))
    if not out:
        out.append(ItemDraft(text="general geospatial intelligence competence", item_type=ItemType.SKILL, confidence=0.1, source="fallback"))
    return out


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
    - Clean text
    - Extract K/S/A items (LAiSER or fallback)
    - Optional LLM enhancement
    - Optional dedupe/canonicalization
    - Write to Neo4j (idempotent)
    - Emit a small telemetry dict
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

    if keep_types:
        pass  # keep as is
    else:
        # If KEEP_TYPES=false, coerce everything to 'skill' (simple UX mode)
        for it in items:
            it.item_type = ItemType.SKILL

    # ---- Optional LLM enhancement ----
    if _USE_LLM_ENHANCER and items:
        try:
            items = enhance_items_with_llm(items, context=clean_text)
        except Exception as e:
            errors.append(f"llm_enhance_error:{type(e).__name__}")

    # ---- Optional canonicalization / dedupe ----
    try:
        items = canonicalize_items(items)
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
        "n_items_after_filters": len(items),
        "n_items_after_dedupe": n_items_after_dedupe,
        "esco_tagged_count": esco_tagged_count,
        "used_fallback": used_fallback,
        "errors": errors,
        "duration_ms": duration_ms,
        "write_stats": write_stats,
    }
