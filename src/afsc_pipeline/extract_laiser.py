# src/afsc_pipeline/extract_laiser.py
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

# External (HTTP) mode deps
try:
    import httpx  # type: ignore
except Exception:
    httpx = None  # Only needed if LAISER_MODE=http

# ---------- Models ----------

class ItemType(str, Enum):
    KNOWLEDGE = "knowledge"
    SKILL = "skill"
    ABILITY = "ability"
    OTHER = "other"

@dataclass
class ItemDraft:
    text: str
    item_type: ItemType
    confidence: float = 0.0
    source: str = "laiser"
    esco_id: Optional[str] = None

    @property
    def content_sig(self) -> str:
        s = f"{self.text.strip()}|{self.item_type.value}"
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


# ---------- Helpers ----------

def _is_truthy(env: str, default: str = "false") -> bool:
    val = (os.getenv(env, default) or "").strip().lower()
    return val in {"1", "true", "yes", "y", "on"}

def _dbg(*args: Any) -> None:
    print(*args, file=sys.stderr)

def _coerce_type(s: str) -> ItemType:
    s = (s or "").strip().lower()
    if s.startswith("know"): return ItemType.KNOWLEDGE
    if s.startswith("abil"): return ItemType.ABILITY
    if s.startswith("skill"): return ItemType.SKILL
    return ItemType.OTHER

def _coerce_conf(x: Any) -> float:
    try:
        f = float(x)
        if f < 0: return 0.0
        if f > 1: return 1.0
        return f
    except Exception:
        return 0.0

def _maybe_get_esco_id(rec: Dict[str, Any]) -> Optional[str]:
    # Common shapes we might see from LAiSER returns
    for k in ("esco_id", "ESCO_ID", "esco", "taxonomy_id", "skill_tag"):
        v = rec.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            # sometimes {"id": "..."} or {"uri": "..."}
            for kk in ("id", "uri", "code"):
                vv = v.get(kk)
                if isinstance(vv, str) and vv.strip():
                    return vv.strip()
    return None


# ---------- LAiSER library (refactored) ----------

def _extract_with_laiser_lib(text: str) -> List[ItemDraft]:
    """
    Try the refactored LAiSER API first; gracefully downgrade if not present.
    Env:
      LAISER_MODEL_ID, HUGGINGFACE_TOKEN, LAISER_USE_GPU (optional, default False)
    """
    try:
        from laiser.skill_extractor_refactored import SkillExtractorRefactored  # type: ignore
        model_id = os.getenv("LAISER_MODEL_ID", "google/flan-t5-base")
        hf_token = os.getenv("HUGGINGFACE_TOKEN", "")
        use_gpu = _is_truthy("LAISER_USE_GPU", "false")
        _dbg(f"[LAISER/lib] Using SkillExtractorRefactored(model_id={model_id}, use_gpu={use_gpu})")

        se = SkillExtractorRefactored(model_id=model_id, hf_token=hf_token, use_gpu=use_gpu)
        # Try to request ESCO alignment/top-k; exact signature may vary by package version
        # We pass generic kwargs and ignore extras if not supported.
        try_kwargs = [
            {"top_k": 40, "include_esco": True},
            {"top_k": 40},  # fallback if include_esco not supported
            {},
        ]
        out: List[Dict[str, Any]] = []
        for kw in try_kwargs:
            try:
                res = se.extract(text, **kw)  # type: ignore[arg-type]
                if isinstance(res, dict) and "items" in res:
                    out = res.get("items") or []
                elif isinstance(res, list):
                    out = res
                else:
                    out = []
                if out:
                    break
            except TypeError:
                continue

        if not out:
            _dbg("[LAISER/lib] Empty result from se.extract()")
            return []

        items: List[ItemDraft] = []
        for rec in out:
            if not isinstance(rec, dict):
                continue
            txt = (rec.get("text") or rec.get("value") or rec.get("skill") or "").strip()
            if not txt:
                continue
            typ = _coerce_type(str(rec.get("type") or rec.get("label") or "skill"))
            conf = _coerce_conf(rec.get("confidence", 0.0))
            esco = _maybe_get_esco_id(rec)

            items.append(
                ItemDraft(
                    text=txt,
                    item_type=typ,
                    confidence=conf,
                    source="laiser:lib",
                    esco_id=esco,
                )
            )
        _dbg(f"[LAISER/lib] Parsed {len(items)} items")
        return items
    except Exception as e:
        _dbg(f"[LAISER/lib] import/use failed: {e.__class__.__name__}: {e}")
        return []


# ---------- LAiSER HTTP ----------

def _extract_with_laiser_http(text: str) -> List[ItemDraft]:
    if httpx is None:
        _dbg("[LAISER/http] httpx not available; skipping")
        return []
    url = os.getenv("LAISER_HTTP_URL", "").strip()
    if not url:
        _dbg("[LAISER/http] LAISER_HTTP_URL not set; skipping")
        return []
    key = os.getenv("LAISER_HTTP_KEY", "").strip()
    timeout_s = float(os.getenv("LAISER_TIMEOUT_S", "45"))
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    payload = {
        "text": text,
        "top_k": 40,
        "include_esco": True,
    }
    _dbg(f"[LAISER/http] POST {url} (timeout={timeout_s}s)")
    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        _dbg(f"[LAISER/http] request failed: {e}")
        return []

    # Normalize
    raw_items: List[Dict[str, Any]] = []
    if isinstance(data, dict) and "items" in data:
        raw_items = data.get("items") or []
    elif isinstance(data, list):
        raw_items = data
    items: List[ItemDraft] = []
    for rec in raw_items:
        if not isinstance(rec, dict):
            continue
        txt = (rec.get("text") or rec.get("value") or rec.get("skill") or "").strip()
        if not txt:
            continue
        typ = _coerce_type(str(rec.get("type") or rec.get("label") or "skill"))
        conf = _coerce_conf(rec.get("confidence", 0.0))
        esco = _maybe_get_esco_id(rec)
        items.append(ItemDraft(text=txt, item_type=typ, confidence=conf, source="laiser:http", esco_id=esco))
    _dbg(f"[LAISER/http] Parsed {len(items)} items")
    return items


# ---------- Public API used by pipeline ----------

def extract_ksa_items(clean_text: str) -> List[ItemDraft]:
    """
    Primary extractor:
      1) Try LAiSER.extract_and_align (structured DF path).
      2) If it returns 0 rows OR the model can't init on CPU, fall back to
         LAiSER.align_skills(raw_skills=...) which uses FAISS+spaCy and
         returns ESCO-aligned skills without a heavy LM.
    """
    use_laiser = (os.getenv("USE_LAISER") or "false").strip().lower() in {"1", "true", "yes"}
    mode = (os.getenv("LAISER_MODE") or "auto").strip().lower()
    top_k = int(os.getenv("LAISER_ALIGN_TOPK", "20"))

    if not use_laiser:
        # Heuristic tiny fallback (same as before)
        return _fallback_extract(clean_text)

    try:
        # -------- 1) Try the refactored DF path (may be 0 on CPU) --------
        extractor = _get_laiser_extractor(mode=mode)
        if extractor is None:
            raise RuntimeError("laiser_extractor_unavailable")

        # DF path expects a dataframe with an ID + text column
        import pandas as pd  # local import to avoid hard dep at import time
        df = pd.DataFrame([{"Research ID": "AFSC-0", "text": clean_text}])
        try:
            df_out = extractor.extract_and_align(
                data=df,
                id_column="Research ID",
                text_columns=["text"],
                input_type="job_desc",
                top_k=None,              # let LAiSER pick
                levels=False,
                batch_size=32,
                warnings=False,
            )
        except Exception:
            df_out = None

        items: List[ItemDraft] = []
        if df_out is not None and len(df_out) > 0:
            # Expecting columns like: "cleaned_text","type","label","confidence","esco_id"
            for _, row in df_out.iterrows():
                txt = str(row.get("label") or row.get("cleaned_text") or "").strip()
                if not txt:
                    continue
                # LAiSER tends to emit skills; if "type" available, map it; else default SKILL
                t = str(row.get("type") or "skill").strip().lower()
                if t.startswith("know"):
                    itype = ItemType.KNOWLEDGE
                elif t.startswith("abil"):
                    itype = ItemType.ABILITY
                else:
                    itype = ItemType.SKILL
                conf = float(row.get("confidence") or 0.5)
                esco_id = (row.get("esco_id") or "").strip() or None
                items.append(
                    ItemDraft(
                        text=txt,
                        item_type=itype,
                        confidence=conf,
                        source="laiser:df",
                        esco_id=esco_id,
                    )
                )

        # If DF path yielded items, return them
        if items:
            return items

        # -------- 2) CPU-friendly fallback: align_skills(...) --------
        # Build simple candidate phrases from the text (sentences & comma splits)
        raw_candidates: List[str] = []
        for line in re.split(r"[;\n\.]", clean_text):
            c = line.strip(" -•\t\r ")
            if len(c) >= 4:
                raw_candidates.append(c)

        # If still too short, seed a few generic phrases so we get something back
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
        except Exception:
            df2 = None

        items2: List[ItemDraft] = []
        if df2 is not None and len(df2) > 0:
            # Expect columns: text/label, confidence, esco_id (names vary slightly)
            for _, row in df2.iterrows():
                txt = str(row.get("label") or row.get("text") or "").strip()
                if not txt:
                    continue
                conf = float(row.get("confidence") or 0.5)
                esco_id = (row.get("esco_id") or "").strip() or None
                items2.append(
                    ItemDraft(
                        text=txt,
                        item_type=ItemType.SKILL,  # align_skills emits skills
                        confidence=conf,
                        source="laiser:align",
                        esco_id=esco_id,
                    )
                )

        # Keep only the top_k highest-confidence matches (optional)
        if len(items2) > top_k:
            items2.sort(key=lambda x: (x.confidence or 0.0), reverse=True)
            items2 = items2[:top_k]

        return items2 or _fallback_extract(clean_text)

    except Exception:
        # Total failure: last-resort tiny fallback so the pipeline still runs
        return _fallback_extract(clean_text)



# ---------- Heuristic fallback (kept here so try_pipeline import works) ----------

def _heuristic_extract(clean_text: str) -> List[ItemDraft]:
    """
    Extremely simple fallback: split on sentences; label a few as K/S/A by keyword.
    """
    import re
    sents = [s.strip() for s in re.split(r"[.\n]+", clean_text) if len(s.strip()) > 5]
    out: List[ItemDraft] = []
    for s in sents[:30]:
        lower = s.lower()
        if "know" in lower:
            t = ItemType.KNOWLEDGE
        elif "abilit" in lower:
            t = ItemType.ABILITY
        elif "skill" in lower:
            t = ItemType.SKILL
        else:
            t = ItemType.OTHER
        out.append(ItemDraft(text=s, item_type=t, confidence=0.1, source="fallback"))
    # Prefer a small, de-duped set
    uniq: Dict[str, ItemDraft] = {}
    for it in out:
        uniq[it.content_sig] = it
    return list(uniq.values())[:40]
