from dataclasses import dataclass, field
from typing import List, Optional, Dict

@dataclass
class AfscDoc:
    code: str
    title: str
    raw_text: str
    clean_text: str

@dataclass
class KsaItem:
    name: str
    type: str  # 'knowledge' | 'skill' | 'ability'
    evidence: Optional[str] = None
    confidence: Optional[float] = None
    esco_id: Optional[str] = None
    canonical_key: Optional[str] = None
    meta: Dict = field(default_factory=dict)

@dataclass
class RunReport:
    afsc_code: str
    afsc_title: str
    counts_by_type: Dict[str, int]
    created_items: int
    updated_items: int
    created_edges: int
    warnings: List[str] = field(default_factory=list)
    artifacts: Dict = field(default_factory=dict)
