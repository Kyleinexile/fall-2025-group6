import re
from typing import List
from .types import KsaItem
from . import config

class CanonicalizerDeduper:
    """
    Build human-readable canonical strings (lowercase → strip punctuation → collapse spaces).
    Drop exact duplicates by canonical string, then (later) fuzzy-merge near-dupes at a threshold.
    """

    PUNCT_RE = re.compile(r"[^\w\s]")        # remove punctuation
    SPACE_RE = re.compile(r"\s+")            # collapse whitespace

    def _canonicalize(self, text: str) -> str:
        if not text:
            return ""
        t = text.lower().strip()
        t = self.PUNCT_RE.sub(" ", t)
        t = self.SPACE_RE.sub(" ", t)
        return t.strip()

    def dedupe(self, items: List[KsaItem]) -> List[KsaItem]:
        """
        Exact dedupe for now:
          - compute canonical_key
          - keep first occurrence per canonical_key
        TODO (later): add fuzzy matching at config.FUZZY_DUP_THRESHOLD (e.g., rapidfuzz).
        """
        seen = set()
        out: List[KsaItem] = []
        for it in items:
            key = self._canonicalize(it.name)
            it.canonical_key = key or None
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(it)
        return out
