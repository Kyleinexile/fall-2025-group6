# src/afsc_pipeline/extract_laiser.py
from __future__ import annotations

import os
import re
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

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

# ---------- LAiSER loader helpers (robust CPU / no-LLM path) ----------

def _build_extractor():
    """
    Construct a LAiSER extractor.

    - If LAISER_NO_LLM=true, we force a SkillNer-only configuration (no transformers).
    - Otherwise, we try the requested model_id; if that fails, we fall back to SkillNer-only.
    """
    try:
        from laiser.skill_extractor_refactored import SkillExtractorRefactored  # type: ignore
    except Exception:
        return None

    no_llm = (os.getenv("LAISER_NO_LLM", "false").strip().lower() in {"1", "true", "yes"})
    model_id = (os.getenv("LAISER_MODEL_ID") or "").strip()  # empty -> internal default if not no_llm
    hf_token = (os.getenv("HUGGINGFACE_TOKEN") or "").strip()
    use_gpu = (os.getenv("LAISER_USE_GPU", "false").strip().lower() in {"1", "true", "yes"})

    # Force SkillNer-only if requested
    if no_llm:
        try:
            return SkillExtractorRefactored(model_id=None, use_gpu=False)
        except Exception:
            return None

    # Try transformer-backed mode first; if it fails, drop to SkillNer-only
    try:
        # If model_id == "", LAiSER will try a default; that may attempt HF downloads.
        # That's fine; if it fails we'll fall back.
        return SkillExtractorRefactored(
            model_id=(model_id or "google/flan-t5-base"),
            hf_token=hf_token or None,
            use_gpu=use_gpu,
        )
    except Exception:
        # Last resort: CPU-only SkillNer/ESCO alignment
        try:
            return SkillExtractorRefactored(model_id=None, use_gpu=False)
        except Exception:
            return None

_EXTRACTOR = None
def _get_extractor():
    global _EXTRACTOR
    if _EXTRACTOR is None:
        _EXTRACTOR = _build_extractor()
    return _EXTRACTOR

# ---------- Tiny local fallback (never blocks pipeline) ----------

def _fallback_extract(clean_text: str) -> List[ItemDraft]:
    out: List[ItemDraft] = []
    lc = (clean_text or "").lower()
    if "knowledge" in lc:
        out.append(ItemDraft(text="knowledge of intelligence cycle", item_type=ItemType.KNOWLEDGE, confidence=0.2, source="fallback"))
    if "skill" in lc or "skills" in lc:
        out.append(ItemDraft(text="imagery exploitation", item_type=ItemType.SKILL, confidence=0.2, source="fallback"))
    if "abilit" in lc:
        out.append(ItemDraft(text="brief intelligence findings", item_type=ItemType.ABILITY, confidence=0.2, source="fallback"))
    if not out:
        out.append(ItemDraft(text="general geospatial intelligence competence", item_type=ItemType.SKILL, confidence=0.1, source="fallback"))
    return out

# ---------- Main API used by pipeline ----------

def extract_ksa_items(clean_text: str) -> List[ItemDraft]:
    """
    Preferred path on CPU:
      A) If USE_LAISER=false or LAiSER unavailable -> tiny heuristic fallback.
      B) If LAISER_NO_LLM=true, skip DF/LLM path and use align_skills (SkillNer/ESCO).
      C) Else, try extractor.extract_and_align (may return 0 on some setups).
         If empty, fall back to align_skills.
    """
    use_laiser = (os.getenv("USE_LAISER") or "false").strip().lower() in {"1", "true", "yes"}
    top_k = int(os.getenv("LAISER_ALIGN_TOPK", "25"))
    no_llm = (os.getenv("LAISER_NO_LLM", "false").strip().lower() in {"1", "true", "yes"})

    if not use_laiser:
        return _fallback_extract(clean_text)

    extractor = _get_extractor()
    if extractor is None:
        return _fallback_extract(clean_text)

    items: List[ItemDraft] = []

    # ---- A (skip DF path entirely in no-LLM mode)
    if not no_llm:
        # 1) Structured DataFrame path (when LLM/transformer is allowed)
        try:
            import pandas as pd  # local import
            df = pd.DataFrame([{"Research ID": "AFSC-0", "text": clean_text or ""}])
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
        except Exception:
            df_out = None

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

    # ---- B) CPU-friendly: align_skills on raw candidate phrases (SkillNer + ESCO/FAISS)
    raw_candidates: List[str] = []
    for seg in re.split(r"[;\n\.\u2022\-]", clean_text or ""):
        c = seg.strip(" \t\r")
        if len(c) >= 4:
            raw_candidates.append(c)

    if not raw_candidates:
        raw_candidates = [
            "imagery exploitation",
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
    except Exception:
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
