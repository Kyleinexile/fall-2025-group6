from typing import List
from .types import AfscDoc, KsaItem

class LaiserExtractor:
    """
    Run LAiSER on doc.clean_text to extract Skills (with optional evidence/confidence).
    Returns a list of KsaItem where item.type == 'skill'.

    Implementation notes (to add later):
    - Call the existing LAiSER function(s) you used in your notebooks/scripts.
    - Normalize outputs to KsaItem(name, type='skill', evidence=?, confidence=?).
    - Guardrails: drop items with empty/short names, trim whitespace.
    - If LAiSER returns nothing, raise a ValueError so the pipeline can flag it.
    """

    def extract(self, doc: AfscDoc) -> List[KsaItem]:
        # TODO: wire LAiSER call and map outputs into KsaItem objects
        # Placeholder stub so the module imports cleanly:
        raise NotImplementedError("LaiserExtractor.extract() not implemented yet.")
