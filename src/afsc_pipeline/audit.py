from __future__ import annotations
import json, csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from .types import RunReport, KsaItem, AfscDoc

class AuditLogger:
    """
    Write a compact run snapshot to runs/YYYY-MM-DD/<AFSC>/:
      - report.json (RunReport + basic stats)
      - items.csv   (final items sent to Neo4j)
      - doc.txt     (cleaned AFSC text for traceability)
    """

    def __init__(self, root: str = "runs"):
        self.root = Path(root)

    def _dir(self, afsc_code: str) -> Path:
        d = self.root / datetime.now().strftime("%Y-%m-%d") / afsc_code
        d.mkdir(parents=True, exist_ok=True)
        return d

    def log(self, doc: AfscDoc, items: List[KsaItem], report: RunReport) -> Path:
        d = self._dir(report.afsc_code)

        # report.json
        rep = {
            "afsc_code": report.afsc_code,
            "afsc_title": report.afsc_title,
            "counts_by_type": report.counts_by_type,
            "created_items": report.created_items,
            "created_edges": report.created_edges,
            "warnings": report.warnings,
        }
        (d / "report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")

        # items.csv
        with (d / "items.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["name","type","evidence","confidence","esco_id","canonical_key"])
            for it in items:
                w.writerow([it.name, it.type, it.evidence or "", it.confidence, it.esco_id or "", it.canonical_key or ""])

        # doc.txt (cleaned text only to keep size small)
        (d / "doc.txt").write_text(doc.clean_text, encoding="utf-8")

        return d
