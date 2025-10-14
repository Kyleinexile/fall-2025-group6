from typing import List
from .types import AfscDoc, KsaItem

class KsaEnhancer:
    """
    Use Gemini (primary) to propose Knowledge & Abilities from AFSC context + Skills.
    Output must be a list of KsaItem with type in {'knowledge','ability'}.
    Later: enforce min lengths, dedupe within the batch, and flag weak outputs.
    """

    def enhance(self, doc: AfscDoc, skills: List[KsaItem]) -> List[KsaItem]:
        # TODO: call Gemini with a constrained prompt and map results to KsaItem
        # Keep this as a stub for now so imports pass.
        raise NotImplementedError("KsaEnhancer.enhance() not implemented yet.")
