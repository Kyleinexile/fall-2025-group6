cat > src/afsc_pipeline/extract_laiser.py << 'ENDOFFILE'
# src/afsc_pipeline/extract_laiser.py
from __future__ import annotations

import os
import re
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

# ---------- Public model ----------

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

# ---------- LAiSER loader ----------

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
        print(f"[LAISER] Initializing extractor...")
        extractor = SkillExtractorRefactored(
            model_id="google/flan-t5-base",
            use_gpu=False
        )
        _EXTRACTOR_CACHE = extractor
        print("[LAISER] Extractor cached successfully")
        return extractor
    except Exception as e:
        print(f"[LAISER] Init failed: {e}")
        return None

# ---------- Fallback ----------

def _fallback_extract(clean_text: str) -> List[ItemDraft]:
    out = []
    lc = clean_text.lower()
    if "knowledge" in lc:
        out.append(ItemDraft(text="knowledge of intelligence cycle", item_type=ItemType.KNOWLEDGE, confidence=0.2, source="fallback"))
    if "skill" in lc or "skills" in lc:
        out.append(ItemDraft(text="imagery exploitation", item_type=ItemType.SKILL, confidence=0.2, source="fallback"))
    if "abilit" in lc:
        out.append(ItemDraft(text="brief intelligence findings", item_type=ItemType.ABILITY, confidence=0.2, source="fallback"))
    if not out:
        out.append(ItemDraft(text="general intelligence competence", item_type=ItemType.SKILL, confidence=0.1, source="fallback"))
    return out

# ---------- Main API ----------

def extract_ksa_items(clean_text: str) -> List[ItemDraft]:
    """
    Extract skills using LAiSER's align_skills method (CPU-friendly, ESCO-aware).
    """
    use_laiser = (os.getenv("USE_LAISER") or "false").strip().lower() in {"1","true","yes"}
    top_k = int(os.getenv("LAISER_ALIGN_TOPK", "25"))

    print(f"[LAISER] USE_LAISER={use_laiser}, TOP_K={top_k}")

    if not use_laiser:
        print("[LAISER] Disabled, using fallback")
        return _fallback_extract(clean_text)

    extractor = _build_extractor()
    if extractor is None:
        print("[LAISER] Could not build extractor, using fallback")
        return _fallback_extract(clean_text)

    # Extract candidate phrases
    raw_candidates = []
    for seg in re.split(r"[;\n\.\u2022\-]", clean_text):
        c = seg.strip()
        if len(c) >= 4:
            raw_candidates.append(c)
    
    if not raw_candidates:
        print("[LAISER] No candidates, using defaults")
        raw_candidates = [
            "imagery exploitation",
            "geospatial intelligence",
            "target development",
            "intelligence briefing",
        ]
    
    print(f"[LAISER] Generated {len(raw_candidates)} candidate phrases")

    # Call align_skills
    try:
        result_df = extractor.align_skills(
            raw_skills=raw_candidates,
            document_id="AFSC-0",
            description="AFSC narrative"
        )
        print(f"[LAISER] align_skills returned {len(result_df)} results")
    except Exception as e:
        print(f"[LAISER] align_skills error: {e}")
        return _fallback_extract(clean_text)

    # Parse results - CRITICAL: Use correct column names!
    items = []
    for idx, row in result_df.iterrows():
        # LAiSER returns:
        # - "Taxonomy Skill" = the matched skill text
        # - "Correlation Coefficient" = confidence score
        # - "Skill Tag" = ESCO ID (may be empty string)
        
        txt = str(row.get("Taxonomy Skill") or "").strip()
        if not txt:
            continue
        
        conf = float(row.get("Correlation Coefficient") or 0.5)
        esco_id = str(row.get("Skill Tag") or "").strip() or None
        
        if esco_id:
            print(f"[LAISER] ✓ Mapped '{txt[:40]}' -> ESCO: {esco_id} (conf={conf:.2f})")
        
        items.append(ItemDraft(
            text=txt,
            item_type=ItemType.SKILL,
            confidence=conf,
            source="laiser:align",
            esco_id=esco_id
        ))

    # Limit to top_k by confidence
    if len(items) > top_k:
        items.sort(key=lambda x: x.confidence, reverse=True)
        items = items[:top_k]
    
    print(f"[LAISER] Returning {len(items)} skills, {sum(1 for i in items if i.esco_id)} with ESCO")
    return items or _fallback_extract(clean_text)
ENDOFFILE

echo "✅ Updated extract_laiser.py with correct column mappings!"
