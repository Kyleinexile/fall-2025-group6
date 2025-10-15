"""
Real LAiSER integration with robust guards and graceful fallback.

Dependencies (add to requirements.txt if not present):
- pydantic>=2.7
- httpx>=0.27
- tenacity>=8.2
- python-slugify>=8.0  (optional, nice-to-have)
"""

from __future__ import annotations
from dataclasses import dataclass
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
from pydantic import BaseModel, Field, constr, ValidationError


# ---------- Config ----------

LAISER_ENABLED = os.getenv("USE_LAISER", "true").lower() in {"1", "true", "yes"}
LAISER_MODE = os.getenv("LAISER_MODE", "auto")     # "auto" | "lib" | "http"
LAISER_TIMEOUT_S = int(os.getenv("LAISER_TIMEOUT_S", "30"))
LAISER_HTTP_URL = os.getenv("LAISER_HTTP_URL", "") # e.g., http://localhost:8000/extract or hosted
LAISER_HTTP_KEY = os.getenv("LAISER_HTTP_KEY", "") # if your endpoint requires an API key

# If you have a Python package for LAiSER, we try to import it when LAISER_MODE in ("auto","lib")
_HAVE_LAISER_LIB = False
_laiser_lib = None
if LAISER_MODE in ("auto", "lib"):
    try:
        import laiser  # noqa: F401
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
    # Stable content signature to help dedupe/idempotent upserts down-pipeline
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

_MIN_CHARS = 280  # require some substance to avoid garbage calls

def _sanitize_text(raw: str) -> str:
    if not raw:
        return ""
    txt = textwrap.dedent(raw).strip()
    # remove markdown tables / code fences to reduce noise for extractors
    txt = re.sub(r"```.+?```", " ", txt, flags=re.DOTALL)
    txt = re.sub(r"\|.+\|\n", " ", txt)  # naive strip of table rows
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
    Very light heuristic stub. Keeps your existing behavior as a safety net.
    """
    # Example heuristics: look for bullet-ish lines and verbs/nouns
    bullets = re.findall(r"(?:^|\s)[•\-–]\s([^•\-\n\r]{8,120})", text)
    candidates = [b.strip().rstrip(".") for b in bullets]
    out: List[ItemDraft] = []

    # naive tag as 'skill' unless we detect "knowledge of" / "ability to"
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
            content_sig=ItemDraft.make_sig(c, t, tag="heuristic-v1")
        ))
    # If nothing matched, fall back to a couple of generic stubs to avoid empty set
    if not out:
        seeds = [
            ("Conduct multi-source analysis", ItemType.skill),
            ("Knowledge of intelligence cycle fundamentals", ItemType.knowledge),
            ("Ability to synthesize findings under time constraints", ItemType.ability)
        ]
        for c, t in seeds:
            out.append(ItemDraft(
                text=c,
                item_type=t,
                confidence=0.5,
                source="heuristic",
                content_sig=ItemDraft.make_sig(c, t, tag="heuristic-v1")
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
        Adjust to the real laiser API you have. This is a placeholder showing intent:
        Suppose laiser.extract(text) -> [{"type":"skill","text":"...","confidence":0.83, "esco_id": "ESCO:123"}]
        """
        # Replace this with the real call:
        # raw_items = self._client.extract(text, types=["knowledge","skill","ability"])
        # For demonstration, we simulate a plausible shape:
        raw_items = getattr(self._client, "extract", lambda _t: [])(text)  # if exists; else []
        items: List[ItemDraft] = []
        for r in raw_items:
            try:
                t = ItemType(r.get("type", "skill"))
            except Exception:
                t = ItemType.skill
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
                content_sig=ItemDraft.make_sig(itxt, t, tag="laiser-lib-v1")
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
            "types": ["knowledge", "skill", "ability"],  # adjust if your API expects different schema
            "return_esco": True
        }

        with httpx.Client(timeout=LAISER_TIMEOUT_S) as client:
            resp = client.post(self.url, headers=headers, content=json.dumps(payload))
            resp.raise_for_status()
            data = resp.json()

        # Expected: {"items":[{"type":"skill","text":"...","confidence":0.82,"esco_id":"ESCO:123"}]}
        items: List[ItemDraft] = []
        for r in data.get("items", []):
            try:
                t = ItemType(r.get("type", "skill"))
            except Exception:
                t = ItemType.skill
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
                content_sig=ItemDraft.make_sig(itxt, t, tag="laiser-http-v1")
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
        # If disabled entirely, client stays None

    def extract_items(self, afsc_text: str) -> ExtractResult:
        started = time.time()
        errors: List[str] = []
        sanitized = _sanitize_text(afsc_text)

        ok, reason = _validate_ready(sanitized)
        if not ok:
            # Don’t call remote; return small heuristic seed so pipeline can still run
            items = _heuristic_extract(sanitized)
            dur = int((time.time() - started) * 1000)
            return ExtractResult(items=items, errors=[f"input_invalid:{reason}"], used_fallback=True, duration_ms=dur)

        # Try LAiSER (if configured)
        if self._client is not None:
            try:
                items = self._client.extract(sanitized)
                # If LAiSER returns empty, fall back but record soft error
                if not items:
                    errors.append("laiser_empty")
                    fb = _heuristic_extract(sanitized)
                    dur = int((time.time() - started) * 1000)
                    return ExtractResult(items=fb, errors=errors, used_fallback=True, duration_ms=dur)
                dur = int((time.time() - started) * 1000)
                return ExtractResult(items=items, errors=errors, used_fallback=False, duration_ms=dur)
            except Exception as e:
                errors.append(f"laiser_error:{type(e).__name__}:{str(e)[:200]}")
                # graceful fallback
                items = _heuristic_extract(sanitized)
                dur = int((time.time() - started) * 1000)
                return ExtractResult(items=items, errors=errors, used_fallback=True, duration_ms=dur)

        # No LAiSER configured/enabled -> fallback
        items = _heuristic_extract(sanitized)
        dur = int((time.time() - started) * 1000)
        return ExtractResult(items=items, errors=errors, used_fallback=True, duration_ms=dur)


# ---------- Public helper for pipeline ----------

def extract_ksa_items(afsc_text: str) -> ExtractResult:
    """
    Pipeline entry point. Keep this stable for pipeline.py.
    """
    extractor = LaiserExtractor()
    return extractor.extract_items(afsc_text)
