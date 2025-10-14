import re
from typing import List
from .types import AfscDoc, KsaItem

class LaiserExtractor:
    """
    TEMPORARY heuristic extractor so the pipeline runs end-to-end.
    - Treats bullet-like lines as candidate skills.
    - Strips punctuation/whitespace, enforces a minimal token length.
    - Returns KsaItem objects with type='skill'.
    Replace this with the real LAiSER call when ready.
    """

    BULLET_RE = re.compile(r"^\s*([-*•]|[0-9]+[.)])\s+")
    MIN_TOKENS = 3

    def _is_skill_line(self, line: str) -> bool:
        if not line or len(line.strip()) < 4:
            return False
        if self.BULLET_RE.match(line):
            return True
        # Also allow lines that look like short statements
        if line.strip() and line.strip()[0].islower():
            return True
        return False

    def extract(self, doc: AfscDoc) -> List[KsaItem]:
        skills: List[KsaItem] = []
        for raw in doc.clean_text.splitlines():
            ln = raw.strip().rstrip(";-•")
            if not self._is_skill_line(ln):
                continue
            # remove bullet markers
            ln = self.BULLET_RE.sub("", ln).strip()
            # basic length guard
            if len(ln.split()) < self.MIN_TOKENS:
                continue
            # capitalize first letter for nicer display
            name = ln[0].upper() + ln[1:] if ln else ln
            skills.append(KsaItem(name=name, type="skill"))
        if not skills:
            # still return an empty list (don’t crash pipeline), but you can raise if preferred
            # raise ValueError("No skills detected by heuristic extractor.")
            pass
        return skills
