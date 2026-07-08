from dataclasses import dataclass, field
from typing import Dict, List, Optional
import torch
import uuid
from datetime import datetime

@dataclass
class SentenceRecord:
    id: str 
    text: str
    source_doc: str
    source_line: int     
    embedding: torch.Tensor

@dataclass
class ConversationTurn:
    turn_index: int
    original_query: str
    resolved_query: str
    retrieved_sentence_ids: List[str]
    answer: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class Session:
    session_id: str
    sentences: List[SentenceRecord] = field(default_factory=list)
    documents: List[str] = field(default_factory=list)
    conversation: List[ConversationTurn] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

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

def append_sentences(session_id: str, new_sentences: List[SentenceRecord]):
    """
    Append new sentences to an existing session.
    """
    for s in new_sentences:
        s.embedding = s.embedding.cpu()
    _sessions[session_id].sentences.extend(new_sentences)

def append_turn(session_id: str, turn: ConversationTurn):
    _sessions[session_id].conversation.append(turn)

def turn_to_sentence_records(turn: ConversationTurn, encoder) -> List[SentenceRecord]:
    """
    Convert a completed turn into retrievable SentenceRecords.
    Splits into distinct Question and Answer records to prevent embedding dilution,
    improving single-hop retrieval accuracy.
    """
    time_str = turn.timestamp.strftime('%Y-%m-%d %H:%M')
    
    # We explicitly prepend the timestamp to ground the facts in time
    texts = [
        f"[{time_str}] User asked: {turn.resolved_query}",
        f"[{time_str}] Assistant answered: {turn.answer}"
    ]
    
    # Encode both strings
    embeddings = encoder.encode(texts)

    return [
        SentenceRecord(
            id=f"turn{turn.turn_index}_q",
            text=texts[0],
            source_doc="conversation_history",
            source_line=turn.turn_index,
            embedding=embeddings[0].cpu()
        ),
        SentenceRecord(
            id=f"turn{turn.turn_index}_a",
            text=texts[1],
            source_doc="conversation_history",
            source_line=turn.turn_index,
            embedding=embeddings[1].cpu()
        )
    ]