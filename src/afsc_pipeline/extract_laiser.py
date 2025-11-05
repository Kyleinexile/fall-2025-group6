# src/afsc_pipeline/extract_laiser.py
from __future__ import annotations

import os
import re
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

def _build_extractor():
    """Build LAiSER extractor with Gemini API"""
    try:
        from laiser.skill_extractor_refactored import SkillExtractorRefactored
        
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            print("[LAISER] No GEMINI_API_KEY found")
            return None
        
        print("[LAISER] Initializing with Gemini API...")
        return SkillExtractorRefactored(
            model_id="gemini",
            api_key=gemini_key,
            use_gpu=False
        )
    except Exception as e:
        print(f"[LAISER] Could not init: {e}")
        import traceback
        traceback.print_exc()
        return None

def _fallback_extract(clean_text: str) -> List[ItemDraft]:
    """
    Intelligent fallback: Extract skills using pattern matching when LAiSER unavailable.
    """
    items = []
    
    # Common action verbs indicating skills
    action_verbs = [
        "perform", "conduct", "analyze", "develop", "manage", "coordinate",
        "evaluate", "assess", "prepare", "produce", "execute", "direct",
        "integrate", "synthesize", "collect", "process", "disseminate",
        "target", "exploit", "brief", "maintain", "establish", "implement",
        "monitor", "support", "plan", "organize", "identify", "determine"
    ]
    
    # Extract verb + object phrases - improved
    for verb in action_verbs:
        # Look for verb + 2-4 word phrases
        pattern = rf"\b{verb}(?:s|es|ing)?\s+([a-z]+\s+[a-z]+(?:\s+[a-z]+){{0,2}})\b"
        matches = re.findall(pattern, clean_text.lower())
        
        for phrase in matches:
            phrase = phrase.strip()
            # Skip common filler phrases
            if any(skip in phrase for skip in ["and the", "or the", "of the", "to the"]):
                continue
            if len(phrase) > 15:
                skill_text = f"{verb} {phrase}"
                # Remove trailing conjunctions/prepositions
                skill_text = re.sub(r"\s+(and|or|the|for|with|from)$", "", skill_text)
                items.append(ItemDraft(
                    text=skill_text,
                    item_type=ItemType.SKILL,
                    confidence=0.55,
                    source="fallback-pattern",
                    esco_id=None
                ))
                if len(items) >= 8:
                    break
        if len(items) >= 8:
            break
    
    # Extract phrases with domain keywords
    domain_keywords = [
        "intelligence", "analysis", "targeting", "collection", "exploitation",
        "assessment", "planning", "operations", "coordination", "management",
        "briefing", "reporting", "evaluation", "integration", "production"
    ]
    
    # Only add domain patterns if we have fewer than 4 verb-based skills
    if len(items) < 4:
        for keyword in domain_keywords:
            pattern = rf"\b([a-z]+\s+){keyword}(\s+[a-z]+)?\b"
            matches = re.findall(pattern, clean_text.lower())
            for match in matches[:1]:
                phrase = "".join([m for m in match if m]).strip()
                if 15 <= len(phrase) <= 60 and "  " not in phrase:
                    items.append(ItemDraft(
                        text=phrase,
                        item_type=ItemType.SKILL,
                        confidence=0.50,
                        source="fallback-domain",
                        esco_id=None
                    ))
    
    # Deduplicate
    seen = set()
    unique_items = []
    for item in items:
        key = item.text.lower().strip()
        if key not in seen and len(key) > 8:
            seen.add(key)
            unique_items.append(item)
            if len(unique_items) >= 6:
                break
    
    # Generic fallback if nothing found
    if not unique_items:
        unique_items = [
            ItemDraft(text="intelligence analysis", item_type=ItemType.SKILL, confidence=0.3, source="fallback-generic", esco_id=None),
            ItemDraft(text="data processing", item_type=ItemType.SKILL, confidence=0.3, source="fallback-generic", esco_id=None),
        ]
    
    return unique_items

def extract_ksa_items(clean_text: str) -> List[ItemDraft]:
    use_laiser = (os.getenv("USE_LAISER") or "false").strip().lower() in {"1","true","yes"}
    top_k = int(os.getenv("LAISER_ALIGN_TOPK", "25"))
    print(f"[LAISER] Enabled={use_laiser}, TopK={top_k}")
    
    if not use_laiser:
        print("[LAISER] Using fallback extraction (USE_LAISER=false)")
        return _fallback_extract(clean_text)
    
    extractor = _build_extractor()
    if not extractor:
        print("[LAISER] Extractor failed to initialize, using fallback")
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
    print(f"[LAISER] Extracted {len(raw_candidates)} candidate phrases")
    
    # Call align_skills with Gemini
    try:
        print("[LAISER] Calling align_skills...")
        result_df = extractor.align_skills(
            raw_skills=raw_candidates, 
            document_id="AFSC-0"
        )
        print(f"[LAISER] Got {len(result_df)} results from align_skills")
    except Exception as e:
        print(f"[LAISER] Error during align_skills: {e}")
        import traceback
        traceback.print_exc()
        return _fallback_extract(clean_text)
    
    if result_df.empty:
        print("[LAISER] Empty results, using fallback")
        return _fallback_extract(clean_text)
    
    # Parse results
    items = []
    for idx, row in result_df.iterrows():
        txt = str(row.get("Taxonomy Skill") or row.get("Description") or "").strip()
        if not txt:
            continue
        
        conf = float(row.get("Correlation Coefficient") or 0.5)
        esco_id = str(row.get("Skill Tag") or "").strip() or None
        
        if esco_id:
            print(f"[LAISER] ✓ {txt[:50]} -> {esco_id} (conf={conf:.3f})")
        
        items.append(ItemDraft(
            text=txt, 
            item_type=ItemType.SKILL, 
            confidence=conf, 
            source="laiser-gemini", 
            esco_id=esco_id
        ))
    
    if items:
        items.sort(key=lambda x: x.confidence, reverse=True)
        items = items[:top_k]
    
    esco_count = sum(1 for i in items if i.esco_id)
    print(f"[LAISER] Returning {len(items)} skills ({esco_count} with ESCO IDs)")
    
    return items if items else _fallback_extract(clean_text)