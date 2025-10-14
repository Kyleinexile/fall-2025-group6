from typing import List, Dict
from .types import RunReport, AfscDoc, KsaItem
from .preprocess import AfscPreprocessor
from .extract_laiser import LaiserExtractor
from .enhance_llm import KsaEnhancer
from .dedupe import CanonicalizerDeduper
from .graph_writer import Neo4jWriter

class Pipeline:
    """
    Orchestrates: Preprocessor → LAiSER → (optional Enhancer) → (optional Dedupe) → Neo4jWriter.
    Single entrypoint: run(raw_text, enhance=True, dedupe=True) -> RunReport

    Usage for MVP:
      Pipeline().run(raw_text, enhance=False, dedupe=False)   # skills-only, quickest path
    """

    def __init__(self):
        self.pre = AfscPreprocessor()
        self.laiser = LaiserExtractor()
        self.enhancer = KsaEnhancer()
        self.deduper = CanonicalizerDeduper()
        self.db = Neo4jWriter()

    def run(self, raw_text: str, *, enhance: bool = True, dedupe: bool = True) -> RunReport:
        warnings: List[str] = []
        # 1) Preprocess AFSC text
        doc: AfscDoc = self.pre.process(raw_text)

        # 2) Skills via LAiSER
        skills: List[KsaItem] = self.laiser.extract(doc)

        items: List[KsaItem] = list(skills)

        # 3) (Optional) Knowledge & Abilities via LLM
        if enhance:
            try:
                ka_items = self.enhancer.enhance(doc, skills)
                items.extend(ka_items)
            except NotImplementedError:
                warnings.append("Enhancer not implemented; proceeding with skills only.")
            except Exception as e:
                warnings.append(f"Enhancer failed: {e}; proceeding with skills only.")

        # 4) (Optional) Canonicalize & dedupe
        if dedupe:
            try:
                items = self.deduper.dedupe(items)
            except NotImplementedError:
                warnings.append("Deduper not implemented; skipping dedupe.")
            except Exception as e:
                warnings.append(f"Deduper failed: {e}; continuing without dedupe.")

        # Safety filter: enforce valid types & non-empty names
        items = [
            it for it in items
            if (it.name or "").strip()
            and (it.type or "").strip().lower() in {"knowledge", "skill", "ability"}
        ]

        # 5) Upsert into Neo4j
        stats: Dict[str, int] = self.db.upsert(doc, items)

        # 6) Build report
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
            artifacts={},  # reserved for audit logger later
        )
        return report

    def close(self):
        self.db.close()
