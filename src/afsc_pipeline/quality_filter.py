from __future__ import annotations
import os
from typing import List
from afsc_pipeline.extract_laiser import ItemDraft, ItemType

MIN_CONF = float(os.getenv("MIN_CONFIDENCE", "0.15"))  # bump default a bit
STRICT_SKILL_FILTER = (os.getenv("STRICT_SKILL_FILTER","false").lower() in {"1","true","yes"})

def keep_item(it: ItemDraft) -> bool:
    conf = float(it.confidence or 0.0)

    # Always allow high confidence
    if conf >= MIN_CONF:
        return True

    # For low confidence: keep if we have an ESCO hit (good anchor)
    has_esco = bool((it.esco_id or "").strip())

    if STRICT_SKILL_FILTER:
        # If strict, only keep low-conf SKILL when ESCO is present
        if it.item_type == ItemType.SKILL:
            return has_esco
        # Knowledge/Ability: allow low-conf if they have ESCO or conf just below threshold
        return has_esco or conf >= (MIN_CONF - 0.05)

    # Not strict: allow near-threshold, or ESCO-anchored
    return has_esco or conf >= (MIN_CONF - 0.05)

def apply_quality_filter(items: List[ItemDraft]) -> List[ItemDraft]:
    # de-dup basic text noise early (exact text)
    seen = set()
    filtered = []
    for it in items:
        key = (it.item_type, (it.text or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        if keep_item(it):
            filtered.append(it)
    return filtered
