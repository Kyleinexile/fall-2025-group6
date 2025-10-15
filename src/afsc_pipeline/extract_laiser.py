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
    Decide which extractor to run based on env:
      USE_LAISER=true + LAISER_MODE in {lib,http,auto}
    Returns [] if nothing found; the pipeline will fallback.
    """
    use_laiser = _is_truthy("USE_LAISER", "false")
    mode = (os.getenv("LAISER_MODE", "auto") or "auto").strip().lower()
    if not use_laiser:
        _dbg("[extract] USE_LAISER=false -> skipping LAiSER")
        return []

    _dbg(f"[extract] USE_LAISER=true, mode={mode}")
    lib_items: List[ItemDraft] = []
    http_items: List[ItemDraft] = []

    if mode in {"lib", "auto"}:
        lib_items = _extract_with_laiser_lib(clean_text)
        if lib_items:
            return lib_items

    if mode in {"http", "auto"}:
        http_items = _extract_with_laiser_http(clean_text)
        if http_items:
            return http_items

    _dbg("[extract] LAiSER produced no items (laiser_empty)")
    return []


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
