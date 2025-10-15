# src/afsc_pipeline/extract_laiser.py
from __future__ import annotations

import os
import re
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Any

# ---------- Public model the rest of the pipeline uses ----------

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
        # natural key; stable across runs
        h = hashlib.sha1()
        h.update(f"{self.item_type.value}::{self.text.strip()}".encode("utf-8"))
        return h.hexdigest()

# ---------- LAiSER loader helpers ----------

def _get_laiser_extractor(*, mode: str = "auto"):
    """
    Try to load LAiSER's refactored extractor. Returns None if unavailable.
    """
    try:
        from laiser.skill_extractor_refactored import SkillExtractorRefactored  # type: ignore
    except Exception:
        return None

    model_id = (os.getenv("LAISER_MODEL_ID") or "").strip() or "google/flan-t5-base"
    hf_token = (os.getenv("HUGGINGFACE_TOKEN") or "").strip()
    use_gpu = (os.getenv("LAISER_USE_GPU") or "false").strip().lower() in {"1","true","yes"}

    try:
        print(f"[LAISER/lib] init SkillExtractorRefactored(model_id={model_id}, use_gpu={use_gpu})")
        return SkillExtractorRefactored(model_id=model_id, hf_token=hf_token, use_gpu=use_gpu)
    except Exception as e:
        print(f"[LAISER/lib] init failed: {e}")
        return None

# ---------- Tiny local fallback (never blocks pipeline) ----------

def _fallback_extract(clean_text: str) -> List[ItemDraft]:
    out: List[ItemDraft] = []
    lc = clean_text.lower()
    if "knowledge" in lc:
        out.append(ItemDraft(text="knowledge of intelligence cycle", item_type=ItemType.KNOWLEDGE, confidence=0.2, source="fallback"))
    if "skill" in lc or "skills" in lc:
        out.append(ItemDraft(text="imagery analysis", item_type=ItemType.SKILL, confidence=0.2, source="fallback"))
    if "abilit" in lc:
        out.append(ItemDraft(text="briefing and communication", item_type=ItemType.ABILITY, confidence=0.2, source="fallback"))
    if not out:
        out.append(ItemDraft(text="general geospatial intelligence competence", item_type=ItemType.SKILL, confidence=0.1, source="fallback"))
    return out

# ---------- Main API used by pipeline ----------

def extract_ksa_items(clean_text: str) -> List[ItemDraft]:
    """
    Preferred path:
      1) Try LAiSER.extract_and_align(DataFrame,...)  -> may return 0 on CPU.
      2) If 0 rows, fall back to LAiSER.align_skills(raw_skills=...) which
         uses FAISS+spaCy and returns ESCO-aligned skill rows (CPU-friendly).
      3) If LAiSER is unavailable, use tiny heuristic fallback.
    """
    use_laiser = (os.getenv("USE_LAISER") or "false").strip().lower() in {"1","true","yes"}
    mode = (os.getenv("LAISER_MODE") or "auto").strip().lower()
    top_k = int(os.getenv("LAISER_ALIGN_TOPK", "25"))

    # If LAiSER disabled, return the tiny heuristic
    if not use_laiser:
        return _fallback_extract(clean_text)

    extractor = _get_laiser_extractor(mode=mode)
    if extractor is None:
        # LAiSER not importable or failed init
        return _fallback_extract(clean_text)

    # ---- 1) Structured DF path
    try:
        import pandas as pd  # local import
        df = pd.DataFrame([{"Research ID": "AFSC-0", "text": clean_text}])
        df_out = extractor.extract_and_align(
            data=df,
            id_column="Research ID",
            text_columns=["text"],
            input_type="job_desc",
            top_k=None,          # let LAiSER decide
            levels=False,
            batch_size=32,
            warnings=False,
        )
    except Exception as e:
        print(f"[LAISER/lib] extract_and_align error: {e}")
        df_out = None

    items: List[ItemDraft] = []
    if df_out is not None:
        for _, row in df_out.iterrows():
            txt = str(row.get("label") or row.get("cleaned_text") or "").strip()
            if not txt:
                continue
            raw_t = str(row.get("type") or "skill").strip().lower()
            if raw_t.startswith("know"):
                itype = ItemType.KNOWLEDGE
            elif raw_t.startswith("abil"):
                itype = ItemType.ABILITY
            else:
                itype = ItemType.SKILL
            conf = float(row.get("confidence") or 0.5)
            esco_id = (row.get("esco_id") or "").strip() or None
            items.append(ItemDraft(text=txt, item_type=itype, confidence=conf, source="laiser:df", esco_id=esco_id))

    if items:
        return items

    # ---- 2) CPU-friendly: align_skills on raw candidate phrases
    # Sentence-ish/phrase splits from the narrative
    raw_candidates: List[str] = []
    for seg in re.split(r"[;\n\.\u2022\-]", clean_text):
        c = seg.strip(" \t\r")
        if len(c) >= 4:
            raw_candidates.append(c)

    if not raw_candidates:
        raw_candidates = [
            "imagery analysis",
            "geospatial intelligence",
            "target development",
            "mensuration",
            "intelligence briefing",
        ]

    try:
        df2 = extractor.align_skills(
            raw_skills=raw_candidates,
            document_id="AFSC-0",
            description="AFSC narrative",
        )
    except Exception as e:
        print(f"[LAISER/lib] align_skills error: {e}")
        df2 = None

    items2: List[ItemDraft] = []
    if df2 is not None:
        for _, row in df2.iterrows():
            txt = str(row.get("label") or row.get("text") or "").strip()
            if not txt:
                continue
            conf = float(row.get("confidence") or 0.5)
            esco_id = (row.get("esco_id") or "").strip() or None
            items2.append(ItemDraft(text=txt, item_type=ItemType.SKILL, confidence=conf, source="laiser:align", esco_id=esco_id))

    if len(items2) > top_k:
        items2.sort(key=lambda x: (x.confidence or 0.0), reverse=True)
        items2 = items2[:top_k]

    return items2 or _fallback_extract(clean_text)
