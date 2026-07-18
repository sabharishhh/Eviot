from dataclasses import dataclass, field
from typing import Dict, List, Optional
import torch
import uuid
import sqlite3
import json
from pathlib import Path
from datetime import datetime
import os

# ─── Persistence locations ────────────────────────────────────────────────
# Mirrors the .eviot/ convention already used by the OKF memory subsystem.
DB_PATH = Path(".eviot/sessions.db").resolve()
SENTENCES_DIR = Path(".eviot/sessions").resolve()


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
    updated_at: datetime = field(default_factory=datetime.now)
    title: Optional[str] = None
    summary: Optional[str] = None
    summary_through_turn: int = 0


_sessions: Dict[str, Session] = {}


# ─── SQLite layer ───────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT,
                documents_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS turns (
                session_id TEXT NOT NULL,
                turn_index INTEGER NOT NULL,
                original_query TEXT NOT NULL,
                resolved_query TEXT,
                retrieved_sentence_ids TEXT NOT NULL DEFAULT '[]',
                answer TEXT,
                timestamp TEXT NOT NULL,
                PRIMARY KEY (session_id, turn_index)
            )
        """)

        # Migrate existing databases in place — CREATE TABLE IF NOT EXISTS is a
        # no-op once the table exists, so new columns must be added explicitly.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "summary" not in cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN summary TEXT")
        if "summary_through_turn" not in cols:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN summary_through_turn INTEGER NOT NULL DEFAULT 0"
            )

        conn.commit()
    finally:
        conn.close()


_init_db()


def _sentences_path(session_id: str) -> Path:
    SENTENCES_DIR.mkdir(parents=True, exist_ok=True)
    return SENTENCES_DIR / f"{session_id}.pt"


def _persist_sentences(session_id: str, sentences: List[SentenceRecord]):
    """Persist the sentence pool so a session can be re-queried (not just
    replayed) after a restart, without re-ingesting documents.

    Memory records are excluded deliberately: sync_memory_to_session() rebuilds
    them from .eviot/memory on every query. Persisting them would copy the whole
    memory store into every session file and leave stale snapshots behind when
    memories are superseded.
    """
    durable = [r for r in sentences if not r.id.startswith("mem_")]
    torch.save(durable, _sentences_path(session_id))

    docs = sorted(
        set(r.source_doc for r in durable if r.source_doc != "conversation_history")
    )
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE sessions SET documents_json = ?, updated_at = ? WHERE session_id = ?",
            (json.dumps(docs), datetime.now().isoformat(), session_id),
        )
        conn.commit()
    finally:
        conn.close()


def _load_sentences(session_id: str) -> List[SentenceRecord]:
    path = _sentences_path(session_id)
    if not path.exists():
        return []
    records: List[SentenceRecord] = torch.load(path, weights_only=False)
    for r in records:
        r.embedding = r.embedding.cpu()
    return records


def _persist_turn(session_id: str, turn: ConversationTurn):
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO turns
               (session_id, turn_index, original_query, resolved_query,
                retrieved_sentence_ids, answer, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                turn.turn_index,
                turn.original_query,
                turn.resolved_query,
                json.dumps(turn.retrieved_sentence_ids),
                turn.answer,
                turn.timestamp.isoformat(),
            ),
        )
        # Auto-title a session from its first query.
        row = conn.execute("SELECT title FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        title = row["title"] if row else None
        if not title and turn.turn_index == 1:
            title = turn.original_query.strip()[:60]
        conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ?",
            (title, datetime.now().isoformat(), session_id),
        )
        conn.commit()
    finally:
        conn.close()


def _load_turns(session_id: str) -> List[ConversationTurn]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM turns WHERE session_id = ? ORDER BY turn_index ASC",
            (session_id,),
        ).fetchall()
    finally:
        conn.close()
    return [
        ConversationTurn(
            turn_index=row["turn_index"],
            original_query=row["original_query"],
            resolved_query=row["resolved_query"],
            retrieved_sentence_ids=json.loads(row["retrieved_sentence_ids"]),
            answer=row["answer"] or "",
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
        for row in rows
    ]


# ─── Public API (same signatures as before, now persistence-backed) ───────

def create_session() -> Session:
    sid = str(uuid.uuid4())[:8]
    now = datetime.now()
    session = Session(session_id=sid, created_at=now, updated_at=now)
    _sessions[sid] = session

    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO sessions (session_id, title, documents_json, created_at, updated_at) VALUES (?, NULL, '[]', ?, ?)",
            (sid, now.isoformat(), now.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    return session


def get_session(session_id: str) -> Optional[Session]:
    """Returns the in-memory session, hydrating from disk on first access after
    a restart (e.g. resuming an old session from the sidebar)."""
    if session_id in _sessions:
        return _sessions[session_id]

    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    finally:
        conn.close()

    if not row:
        return None

    keys = row.keys()

    session = Session(
        session_id=session_id,
        sentences=_load_sentences(session_id),
        documents=json.loads(row["documents_json"] or "[]"),
        conversation=_load_turns(session_id),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        title=row["title"],
        summary=row["summary"] if "summary" in keys else None,
        summary_through_turn=(row["summary_through_turn"] if "summary_through_turn" in keys else 0) or 0,
    )
    _sessions[session_id] = session
    return session


def store_sentences(session_id: str, sentences: List[SentenceRecord]):
    """
    Ensure all embeddings are moved to CPU before storage to avoid
    CUDA/CPU tensor mismatches during OT calculations.
    """
    for s in sentences:
        s.embedding = s.embedding.cpu()

    _sessions[session_id].sentences = sentences
    _persist_sentences(session_id, sentences)


def append_sentences(session_id: str, new_sentences: List[SentenceRecord]):
    """
    Append new sentences to an existing session.
    """
    for s in new_sentences:
        s.embedding = s.embedding.cpu()
    _sessions[session_id].sentences.extend(new_sentences)
    _persist_sentences(session_id, _sessions[session_id].sentences)


def append_turn(session_id: str, turn: ConversationTurn):
    _sessions[session_id].conversation.append(turn)
    _sessions[session_id].updated_at = datetime.now()
    _persist_turn(session_id, turn)


def list_sessions() -> List[dict]:
    """Lightweight summaries for the sidebar — never touches the (potentially
    large) sentences .pt files."""
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM sessions ORDER BY updated_at DESC").fetchall()
        counts = {
            r["session_id"]: r["c"]
            for r in conn.execute("SELECT session_id, COUNT(*) as c FROM turns GROUP BY session_id").fetchall()
        }
    finally:
        conn.close()

    summaries = []
    for row in rows:
        docs = json.loads(row["documents_json"] or "[]")
        summaries.append({
            "session_id": row["session_id"],
            "title": row["title"] or (docs[0] if docs else "New session"),
            "documents": docs,
            "turn_count": counts.get(row["session_id"], 0),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        })
    return summaries


def delete_session(session_id: str) -> bool:
    conn = _get_conn()
    try:
        existed = conn.execute("SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()

    path = _sentences_path(session_id)
    if path.exists():
        path.unlink()

    _sessions.pop(session_id, None)
    return bool(existed)


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

# How many recent turns are handed to the LLM verbatim. These are excluded
# from retrieval — searching for text the model is already reading is pure
# duplication, and it lets a just-asked question match itself.
CONTEXT_WINDOW_TURNS = int(os.getenv("EVIOT_CONTEXT_WINDOW_TURNS", 6))


def split_conversation(conversation: List[ConversationTurn], window: int = None):
    """Split turns into (visible, archived).

    visible  -> sent to the LLM as chat history, NOT retrievable
    archived -> no longer sent, so retrieval is the only way to reach them
    """
    if window is None:
        window = CONTEXT_WINDOW_TURNS
    if window <= 0:
        return [], list(conversation)
    if len(conversation) <= window:
        return list(conversation), []
    return list(conversation[-window:]), list(conversation[:-window])


def visible_turn_record_ids(visible_turns: List[ConversationTurn]) -> set:
    """Record IDs to drop from the retrieval pool, matching the ID scheme in
    turn_to_sentence_records()."""
    ids = set()
    for t in visible_turns:
        ids.add(f"turn{t.turn_index}_q")
        ids.add(f"turn{t.turn_index}_a")
    return ids


def save_summary(session_id: str, summary: str, through_turn: int):
    if session_id in _sessions:
        _sessions[session_id].summary = summary
        _sessions[session_id].summary_through_turn = through_turn

    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE sessions SET summary = ?, summary_through_turn = ?, updated_at = ? WHERE session_id = ?",
            (summary, through_turn, datetime.now().isoformat(), session_id),
        )
        conn.commit()
    finally:
        conn.close()