import re
from .types import AfscDoc

class AfscPreprocessor:
    """
    Parse and normalize an AFSC section (AFOCD/AFECD).
    - Extracts AFSC code/title from headings.
    - Cleans PDF artifacts (bullets, tables, weird glyphs).
    - Returns AfscDoc with raw_text and clean_text.
    Raises ValueError if code/title cannot be found.
    """

    # Examples it will match:
    #  "1N0X1 – Intelligence Analyst"
    #  "AFSC 1N0X1: Intelligence Analyst"
    #  "AFSC: 1N0X1 (Intelligence Analyst)"
    CODE_TITLE_PATTERNS = [
        r"AFSC[:\s]+(?P<code>[0-9A-Z]{3,5}[A-Z]?)\s*[-–:]\s*(?P<title>.+)",
        r"(?P<code>[0-9A-Z]{3,5}[A-Z]?)\s*[-–:]\s*(?P<title>.+)",
        r"AFSC[:\s]+(?P<code>[0-9A-Z]{3,5}[A-Z]?)\s*\((?P<title>.+?)\)",
    ]

    def _extract_header(self, text: str) -> tuple[str, str]:
        head = text.splitlines()[0:5]  # look in first few lines
        snippet = "\n".join(head)
        for pat in self.CODE_TITLE_PATTERNS:
            m = re.search(pat, snippet, flags=re.IGNORECASE)
            if m:
                code = m.group("code").strip().upper()
                title = m.group("title").strip()
                return code, title
        raise ValueError("Could not parse AFSC code/title from header.")

    def _clean_text(self, text: str) -> str:
        t = text

        # Normalize bullets/dashes and odd glyphs
        t = t.replace("•", "- ").replace("·", "- ").replace("–", "-").replace("—", "-")
        t = re.sub(r"[“”]", '"', t)
        t = re.sub(r"[’]", "'", t)

        # Drop obvious table-like lines (lots of pipes/tabs)
        t = "\n".join(
            ln for ln in t.splitlines()
            if ln.count("|") < 3 and ln.count("\t") < 4
        )

        # Collapse excessive whitespace
        t = re.sub(r"\s+\n", "\n", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        t = re.sub(r"[ \t]{2,}", " ", t)

        # Keep only the section after the header (heuristic)
        # Find first blank line after header; keep from there
        lines = t.splitlines()
        start = 0
        # skip first 1–2 lines (header area)
        start = min(2, max(0, len(lines)-1))
        clean = "\n".join(lines[start:]).strip()

        return clean

    def process(self, raw_text: str) -> AfscDoc:
        if not raw_text or len(raw_text.strip()) < 40:
            raise ValueError("Input AFSC text too short.")
        code, title = self._extract_header(raw_text)
        clean = self._clean_text(raw_text)
        return AfscDoc(code=code, title=title, raw_text=raw_text.strip(), clean_text=clean)
