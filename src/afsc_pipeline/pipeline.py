from typing import List, Dict
from .types import RunReport, AfscDoc, KsaItem
from .preprocess import AfscPreprocessor
from .extract_laiser import LaiserExtractor
from .enhance_llm import KsaEnhancer
from .dedupe import CanonicalizerDeduper
from .graph_writer import Neo4jWriter
from .audit import AuditLogger

class Pipeline:
    """
    Orchestrates: Preprocessor → LAiSER → (optional Enhancer) → (optional Dedupe) → Neo4jWriter.
    Single entrypoint: run(raw_text, enhance=True, dedupe=True) -> RunReport
    """
    def __init__(self):
        self.pre = AfscPreprocessor()
        self.laiser = LaiserExtractor()
        self.enhancer = KsaEnhancer()
        self.deduper = CanonicalizerDeduper()
        self.db = Neo4jWriter()
        self.logr = AuditLogger()

    def run(self, raw_text: str, *, enhance: bool = True, dedupe: bool = True) -> RunReport:
        warnings: List[str] = []

        doc: AfscDoc = self.pre.process(raw_text)
        skills: List[KsaItem] = self.laiser.extract(doc)
        items: List[KsaItem] = list(skills)

        if enhance:
            try:
                ka_items = self.enhancer.enhance(doc, skills)
                items.extend(ka_items)
            except NotImplementedError:
                warnings.append("Enhancer not implemented; proceeding with skills only.")
            except Exception as e:
                warnings.append(f"Enhancer failed: {e}; proceeding with skills only.")

        if dedupe:
            try:
                items = self.deduper.dedupe(items)
            except NotImplementedError:
                warnings.append("Deduper not implemented; skipping dedupe.")
            except Exception as e:
                warnings.append(f"Deduper failed: {e}; continuing without dedupe.")

        items = [
            it for it in items
            if (it.name or "").strip()
            and (it.type or "").strip().lower() in {"knowledge", "skill", "ability"}
        ]

        stats: Dict[str, int] = self.db.upsert(doc, items)

        counts_by_type: Dict[str, int] = {"knowledge": 0, "skill": 0, "ability": 0}
        for it in items:
            t = it.type.strip().lower()
            if t in counts_by_type:
                counts_by_type[t] += 1

        report = RunReport(
            afsc_code=doc.code,
            afsc_title=doc.title,
            counts_by_type=counts_by_type,
            created_items=stats.get("created_items", 0),
            updated_items=stats.get("updated_items", 0),
            created_edges=stats.get("created_edges", 0),
            warnings=warnings,
            artifacts={},
        )

        # NEW: persist artifacts
        try:
            self.logr.log(doc, items, report)
        except Exception as e:
            warnings.append(f"Audit log failed: {e}")

        return report

    def close(self):
        self.db.close()
