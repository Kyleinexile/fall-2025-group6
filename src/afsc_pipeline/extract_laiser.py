# src/afsc_pipeline/extract_laiser.py
from __future__ import annotations

import os
import re
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

class ItemType(str, Enum):
    KNOWLEDGE = "knowledge"
    SKILL = "skill"
    ABILITY = "ability"

@dataclass
class ItemDraft:
    text: str
    item_type: ItemType
    confidence: float = 0.0
    source: str = "unknown"
    esco_id: Optional[str] = None

    @property
    def content_sig(self) -> str:
        h = hashlib.sha1()
        h.update(f"{self.item_type.value}::{self.text.strip()}".encode("utf-8"))
        return h.hexdigest()

_EXTRACTOR_CACHE = None

def _build_extractor():
    global _EXTRACTOR_CACHE
    if _EXTRACTOR_CACHE is not None:
        print("[LAISER] Using cached extractor")
        return _EXTRACTOR_CACHE
    
    try:
        from laiser.skill_extractor_refactored import SkillExtractorRefactored
    except Exception as e:
        print(f"[LAISER] Import failed: {e}")
        return None

    try:
        print(f"[LAISER] Initializing...")
        extractor = SkillExtractorRefactored(model_id="google/flan-t5-base", use_gpu=False)
        _EXTRACTOR_CACHE = extractor
        print("[LAISER] Cached")
        return extractor
    except Exception as e:
        print(f"[LAISER] Init failed: {e}")
        return None

def _fallback_extract(clean_text: str) -> List[ItemDraft]:
    out = []
    lc = clean_text.lower()
    if "knowledge" in lc:
        out.append(ItemDraft(text="knowledge of intelligence cycle", item_type=ItemType.KNOWLEDGE, confidence=0.2, source="fallback"))
    if "skill" in lc:
        out.append(ItemDraft(text="imagery exploitation", item_type=ItemType.SKILL, confidence=0.2, source="fallback"))
    if "abilit" in lc:
        out.append(ItemDraft(text="brief intelligence findings", item_type=ItemType.ABILITY, confidence=0.2, source="fallback"))
    if not out:
        out.append(ItemDraft(text="general intelligence", item_type=ItemType.SKILL, confidence=0.1, source="fallback"))
    return out

def extract_ksa_items(clean_text: str) -> List[ItemDraft]:
    use_laiser = (os.getenv("USE_LAISER") or "false").strip().lower() in {"1","true","yes"}
    top_k = int(os.getenv("LAISER_ALIGN_TOPK", "25"))

    print(f"[LAISER] Enabled={use_laiser}, TopK={top_k}")

    if not use_laiser:
        return _fallback_extract(clean_text)

    extractor = _build_extractor()
    if not extractor:
        return _fallback_extract(clean_text)

    # Split text into phrases
    raw_candidates = []
    for seg in re.split(r"[;\n\.\u2022,]", clean_text):
        c = seg.strip()
        if c.lower().startswith(("duties", "knowledge", "skills", "abilities")):
            continue
        if 4 <= len(c) < 100:
            raw_candidates.append(c)
    
    if not raw_candidates:
        raw_candidates = ["imagery exploitation", "geospatial intelligence", "target development"]
    
    raw_candidates = list(dict.fromkeys(raw_candidates))[:50]
    print(f"[LAISER] {len(raw_candidates)} phrases")

    # Call align_skills
    try:
        result_df = extractor.align_skills(raw_skills=raw_candidates, document_id="AFSC-0", description="AFSC")
        print(f"[LAISER] Got {len(result_df)} results")
    except Exception as e:
        print(f"[LAISER] Error: {e}")
        return _fallback_extract(clean_text)

    if result_df.empty:
        return _fallback_extract(clean_text)

    # Parse results
    items = []
    for idx, row in result_df.iterrows():
        txt = str(row.get("Taxonomy Skill") or "").strip()
        if not txt:
            continue
        
        conf = float(row.get("Correlation Coefficient") or 0.5)
        esco_id = str(row.get("Skill Tag") or "").strip() or None
        
        if esco_id:
            print(f"[LAISER] ✓ {txt[:40]} -> {esco_id}")
        
        items.append(ItemDraft(text=txt, item_type=ItemType.SKILL, confidence=conf, source="laiser", esco_id=esco_id))

    if items:
        items.sort(key=lambda x: x.confidence, reverse=True)
        items = items[:top_k]
    
    esco_count = sum(1 for i in items if i.esco_id)
    print(f"[LAISER] Returning {len(items)} ({esco_count} with ESCO)")
    
    return items if items else _fallback_extract(clean_text)
