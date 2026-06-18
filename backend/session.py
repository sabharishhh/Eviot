from dataclasses import dataclass, field
from typing import Dict, List, Optional
import torch
import uuid
from datetime import datetime

@dataclass
class SentenceRecord:
    id: str              # "{doc_index}_s{sentence_index}"
    text: str
    source_doc: str
    source_line: int     # sentence index within its document
    embedding: torch.Tensor

@dataclass
class Session:
    session_id: str
    sentences: List[SentenceRecord] = field(default_factory=list)
    documents: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

# Module-level store — fine for single-demo use
_sessions: Dict[str, Session] = {}

def create_session() -> Session:
    sid = str(uuid.uuid4())[:8]
    session = Session(session_id=sid)
    _sessions[sid] = session
    return session

def get_session(session_id: str) -> Optional[Session]:
    return _sessions.get(session_id)

def store_sentences(session_id: str, sentences: List[SentenceRecord]):
    """
    Ensure all embeddings are moved to CPU before storage to avoid 
    CUDA/CPU tensor mismatches during OT calculations.
    """
    for s in sentences:
        s.embedding = s.embedding.cpu()
        
    _sessions[session_id].sentences = sentences