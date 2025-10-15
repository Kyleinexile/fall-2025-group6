# src/afsc_pipeline/extract_laiser.py
"""
Real LAiSER integration with robust guards and graceful fallback.

Env toggles:
  USE_LAISER=true|false          # enable/disable LAiSER (fallback to heuristics)
  LAISER_MODE=auto|lib|http      # prefer local lib or HTTP endpoint
  LAISER_TIMEOUT_S=30            # request timeout for HTTP mode
  LAISER_HTTP_URL=<url>          # e.g., http://localhost:8000/extract
  LAISER_HTTP_KEY=<token>        # optional bearer token

Add to requirements (if not already pinned):
  pydantic>=2.7
  httpx>=0.27
  tenacity>=8.2
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
import hashlib
import json
import os
import re
import textwrap
import time

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
from pydantic import BaseModel, Field, constr

# ---------- Config ----------

LAISER_ENABLED = os.getenv("USE_LAISER", "true").lower() in {"1", "true", "yes"}
LAISER_MODE = os.getenv("LAISER_MODE", "auto")     # "auto" | "lib" | "http"
LAISER_TIMEOUT_S = int(os.getenv("LAISER_TIMEOUT_S", "30"))
LAISER_HTTP_URL = os.getenv("LAISER_HTTP_URL", "")
LAISER_HTTP_KEY = os.getenv("LAISER_HTTP_KEY", "")

_HAVE_LAISER_LIB = False
_laiser_lib = None
if LAISER_MODE in ("auto", "lib"):
    try:
        import laiser  # your real LAiSER python package, if available
        _laiser_lib = laiser
        _HAVE_LAISER_LIB = True
    except Exception:
        _HAVE_LAISER_LIB = False


# ---------- Public Types ----------

class ItemType(str, Enum):
    knowledge = "knowledge"
    skill = "skill"
    ability = "ability"


class ItemDraft(BaseModel):
    """Transient item representation used before graph write."""
    text: constr(strip_whitespace=True, min_length=2)
    item_type: ItemType
    confidence: float = Field(ge=0.0, le=1.0, default=0.6)
    esco_id: Optional[str] = None
    source: str = "laiser"  # "laiser" | "heuristic"
    content_sig: str

    @staticmethod
    def make_sig(text: str, item_type: ItemType, tag: str = "v1") -> str:
        h = hashlib.sha256()
        h.update(tag.encode("utf-8"))
        h.update(b"|")
        h.update(item_type.value.encode("utf-8"))
        h.update(b"|")
        h.update(text.encode("utf-8"))
        return h.hexdigest()[:16]


class ExtractResult(BaseModel):
    items: List[ItemDraft]
    errors: List[str] = []
    used_fallback: bool = False
    duration_ms: int


# ---------- Input Hygiene ----------

_MIN_CHARS = 280  # avoid garbage calls / accidental snippets

def _sanitize_text(raw: str) -> str:
    if not raw:
        return ""
    txt = textwrap.dedent(raw).strip()
    # remove code fences / markdown tables to reduce noise
    txt = re.sub(r"```.+?```", " ", txt, flags=re.DOTALL)
    txt = re.sub(r"\|.*\|\n", " ", txt)  # naive table row strip
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def _validate_ready(text: str) -> Tuple[bool, Optional[str]]:
    if not text:
        return False, "empty_input"
    if len(text) < _MIN_CHARS:
        return False, f"too_short:{len(text)}"
    return True, None


# ---------- Heuristic Fallback (current behavior preserved) ----------

def _heuristic_extract(text: str) -> List[ItemDraft]:
    """
    Lightweight heuristic: parse bullet-like lines; classify by simple phrase rules.
    Provides deterministic output to keep pipeline idempotent when LAiSER is down.
    """
    bullets = re.findall(r"(?:^|\s)[•\-–]\s([^•\-\n\r]{8,140})", text)
    candidates = [b.strip().rstrip(".") for b in bullets]
    out: List[ItemDraft] = []

    for c in candidates[:30]:
        lower = c.lower()
        if "knowledge of" in lower or "understanding of" in lower:
            t = ItemType.knowledge
            conf = 0.55
        elif lower.startswith("ability to") or "ability to" in lower:
            t = ItemType.ability
            conf = 0.55
        else:
            t = ItemType.skill
            conf = 0.6

        out.append(ItemDraft(
            text=c,
            item_type=t,
            confidence=conf,
            source="heuristic",
            content_sig=ItemDraft.make_sig(c, t, tag="heuristic-v1"),
        ))

    if not out:
        seeds = [
            ("Conduct multi-source intelligence analysis", ItemType.skill),
            ("Knowledge of intelligence cycle fundamentals", ItemType.knowledge),
            ("Ability to synthesize findings under time constraints", ItemType.ability),
        ]
        for c, t in seeds:
            out.append(ItemDraft(
                text=c,
                item_type=t,
                confidence=0.5,
                source="heuristic",
                content_sig=ItemDraft.make_sig(c, t, tag="heuristic-v1"),
            ))
    return out


# ---------- LAiSER via Python library ----------

class _LaiserLibClient:
    def __init__(self) -> None:
        if not _HAVE_LAISER_LIB:
            raise RuntimeError("LAiSER library not available")
        self._client = _laiser_lib  # type: ignore

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=3.0),
        reraise=True,
    )
    def extract(self, text: str) -> List[ItemDraft]:
        """
        Adjust to the real laiser API you have.
        Expected shape (example):
          laiser.extract(text) -> [{"type":"skill","text":"...","confidence":0.83,"esco_id":"ESCO:123"}]
        """
        raw_items = getattr(self._client, "extract", lambda _t: [])(text)
        items: List[ItemDraft] = []
        for r in raw_items or []:
            t_raw = (r.get("type") or "skill").lower()
            t = ItemType(t_raw) if t_raw in ItemType.__members__.keys() else ItemType.skill
            itxt = (r.get("text") or "").strip()
            if not itxt:
                continue
            conf = float(r.get("confidence", 0.7))
            esco_id = r.get("esco_id")
            items.append(ItemDraft(
                text=itxt,
                item_type=t,
                confidence=max(0.0, min(1.0, conf)),
                esco_id=esco_id,
                source="laiser",
                content_sig=ItemDraft.make_sig(itxt, t, tag="laiser-lib-v1"),
            ))
        return items


# ---------- LAiSER via HTTP ----------

class _LaiserHttpClient:
    def __init__(self, url: str, api_key: str = "") -> None:
        if not url:
            raise RuntimeError("LAISER_HTTP_URL is not configured")
        self.url = url
        self.api_key = api_key

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=3.0),
        reraise=True,
    )
    def extract(self, text: str) -> List[ItemDraft]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "text": text,
            "types": ["knowledge", "skill", "ability"],
            "return_esco": True,
        }

        with httpx.Client(timeout=LAISER_TIMEOUT_S) as client:
            resp = client.post(self.url, headers=headers, content=json.dumps(payload))
            resp.raise_for_status()
            data = resp.json()

        items: List[ItemDraft] = []
        for r in data.get("items", []):
            t_raw = (r.get("type") or "skill").lower()
            t = ItemType(t_raw) if t_raw in ItemType.__members__.keys() else ItemType.skill
            itxt = (r.get("text") or "").strip()
            if not itxt:
                continue
            conf = float(r.get("confidence", 0.7))
            esco_id = r.get("esco_id")
            items.append(ItemDraft(
                text=itxt,
                item_type=t,
                confidence=max(0.0, min(1.0, conf)),
                esco_id=esco_id,
                source="laiser",
                content_sig=ItemDraft.make_sig(itxt, t, tag="laiser-http-v1"),
            ))
        return items


# ---------- Facade ----------

class LaiserExtractor:
    """
    Unified extractor:
      - honors USE_LAISER / LAISER_MODE
      - selects lib vs http
      - falls back to heuristic with result metadata
    """
    def __init__(self) -> None:
        self._client = None
        if LAISER_ENABLED:
            if LAISER_MODE in ("auto", "lib") and _HAVE_LAISER_LIB:
                self._client = _LaiserLibClient()
            elif LAISER_MODE in ("auto", "http") and LAISER_HTTP_URL:
                self._client = _LaiserHttpClient(LAISER_HTTP_URL, LAISER_HTTP_KEY)
            # else: remain None -> fallback

    def extract_items(self, afsc_text: str) -> ExtractResult:
        started = time.time()
        errors: List[str] = []
        sanitized = _sanitize_text(afsc_text)

        ok, reason = _validate_ready(sanitized)
        if not ok:
            items = _heuristic_extract(sanitized)
            dur = int((time.time() - started) * 1000)
            return ExtractResult(items=items, errors=[f"input_invalid:{reason}"], used_fallback=True, duration_ms=dur)

        if self._client is not None:
            try:
                items = self._client.extract(sanitized)
                if not items:
                    errors.append("laiser_empty")
                    fb = _heuristic_extract(sanitized)
                    dur = int((time.time() - started) * 1000)
                    return ExtractResult(items=fb, errors=errors, used_fallback=True, duration_ms=dur)
                dur = int((time.time() - started) * 1000)
                return ExtractResult(items=items, errors=errors, used_fallback=False, duration_ms=dur)
            except Exception as e:
                errors.append(f"laiser_error:{type(e).__name__}:{str(e)[:200]}")
                fb = _heuristic_extract(sanitized)
                dur = int((time.time() - started) * 1000)
                return ExtractResult(items=fb, errors=errors, used_fallback=True, duration_ms=dur)

        # No LAiSER configured/enabled -> fallback
        fb = _heuristic_extract(sanitized)
        dur = int((time.time() - started) * 1000)
        return ExtractResult(items=fb, errors=errors, used_fallback=True, duration_ms=dur)


# ---------- Public entry point for pipeline ----------

def extract_ksa_items(afsc_text: str) -> ExtractResult:
    """
    Pipeline entry point. Stable public function used by pipeline.py
    """
    extractor = LaiserExtractor()
    return extractor.extract_items(afsc_text)
