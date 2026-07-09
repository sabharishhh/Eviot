from dotenv import load_dotenv
load_dotenv()

import torch
import time
import json
import asyncio
import traceback
from contextlib import asynccontextmanager
from typing import List, Optional
import asyncio
from backend.memory.loader import load_okf_memories

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.memory.reconciler import reconcile_and_save

import sys
import os
# Force Python to include the project root in the search path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from session import (
    create_session, store_sentences, append_sentences,
    get_session, SentenceRecord, ConversationTurn, append_turn,
    turn_to_sentence_records,
)
from ingestion.parser import parse_file
from ingestion.chunker import chunk_into_sentences

from retrieval.naive_rag import naive_top_k, compute_internal_redundancy
from retrieval.ot_engine import encode_query_plain, encode_query_decomposed, run_ot_selection_streaming
from retrieval.llm_engine import run_llm_selection_streaming

from llm.answer import get_llm_answer
from demo.scenarios import SCENARIOS

from eviot.encoders.encoder import Encoder
from backend.memory.extractor import extract_memory_candidates
from backend.memory.okf_writer import write_okf_memory

MAX_TURNS = 10

encoder = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global encoder
    print("Loading BAAI/bge-base-en-v1.5 encoder...")
    encoder = Encoder(model_name="text-embedding-3-small")
    
    encoder.encode(["Preparing the encoder."])
    print("Encoder ready. FastAPI is up.")
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def resolve_query_with_history(query: str, conversation: list) -> str:
    """Expand elliptical/referential queries using prior turns."""
    if not conversation:
        return query
    
    import os
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return query
    
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    
    history_text = "\n".join(
        f"Q{t.turn_index}: {t.original_query}\nA{t.turn_index}: {t.answer[:300]}..."
        for t in conversation[-8:]
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-5.4-mini",
            messages=[{
                "role": "user",
                "content": (
                    f"Conversation so far:\n{history_text}\n\n"
                    f"New user query: '{query}'\n\n"
                    "Rewrite the query to be fully self-contained, resolving any pronouns "
                    "or references to previous turns. If it's already self-contained, "
                    "return it unchanged. Return ONLY the rewritten query."
                )
            }],
            temperature=0.0,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return query

@app.post("/ingest")
async def ingest_documents(
    files: List[UploadFile] = File(...),
    session_id: Optional[str] = None
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
        
    start_time = time.time()
    
    # If session_id provided, add to existing session; else create new
    if session_id:
        session = get_session(session_id)
        if not session:
            session = create_session()
        is_new_session = False
    else:
        session = create_session()
        is_new_session = True
    
    # Track existing doc count for unique IDs
    existing_count = len(set(r.source_doc for r in session.sentences))
    
    new_sentence_records = []
    doc_summaries = []
 
    for file_idx, file in enumerate(files):
        content = await file.read()
        
        try:
            text = parse_file(file.filename, content)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        sentences = chunk_into_sentences(text, encoder)
        if not sentences:
            continue
 
        embeddings = encoder.encode(sentences)
        doc_key = existing_count + file_idx
 
        for line_idx, (sent_text, emb) in enumerate(zip(sentences, embeddings)):
            record = SentenceRecord(
                id=f"doc{doc_key}_s{line_idx}",
                text=sent_text,
                source_doc=file.filename,
                source_line=line_idx + 1,
                embedding=emb
            )
            new_sentence_records.append(record)
 
        doc_summaries.append({
            "filename": file.filename,
            "num_sentences": len(sentences),
            "num_pages": 1,
            "status": "encoded"
        })
 
    if is_new_session:
        store_sentences(session.session_id, new_sentence_records)
    else:
        append_sentences(session.session_id, new_sentence_records)
 
    encoding_time_ms = int((time.time() - start_time) * 1000)
 
    return {
        "session_id": session.session_id,
        "documents": doc_summaries,
        "total_sentences": len(session.sentences),
        "encoding_time_ms": encoding_time_ms,
        "is_new_session": is_new_session
    }

def make_sse_event(event_type: str, data: dict) -> str:
    payload = json.dumps({"type": event_type, **data})
    return f"data: {payload}\n\n"

class QueryRequest(BaseModel):
    session_id: str
    query: str
    mode: str = "adaptive"
    use_decomposition: bool = True
    retrieval_engine: str = "ot"  
    params: dict = {}
    is_eval: bool = False

@app.post("/query")
async def query_endpoint(req: QueryRequest):
    sync_memory_to_session(req.session_id)
    session = get_session(req.session_id)
    sentences = session.sentences if session else []
    conversation = session.conversation if session else []
 
    async def event_generator():
        try:
            # 1. Resolve query against conversation history
            resolved_query = resolve_query_with_history(req.query, conversation)
            
            if resolved_query != req.query:
                yield make_sse_event("query_resolved", {
                    "original": req.query,
                    "resolved": resolved_query
                })
 
            # 2. Embed
            if req.use_decomposition:
                phrases, q_embs = encode_query_decomposed(resolved_query, encoder)
                yield make_sse_event("query_embedded", {
                    "decomposed": True,
                    "phrases": phrases,
                })
            else:
                q_embs = encode_query_plain(resolved_query, encoder)
                yield make_sse_event("query_embedded", {
                    "decomposed": False,
                    "phrases": None,
                })
 
            selected_texts = []
            selected_ids = []
 
            if sentences:
                if req.retrieval_engine == "llm":
                    event_stream = run_llm_selection_streaming(resolved_query, sentences)
                else:
                    # Merge default hyperparameters with incoming evaluation overrides
                    runtime_params = {
                        "epsilon": 0.01,
                        "patience": 2,
                        "k_max": 12,
                    }
                    if req.params:
                        runtime_params.update(req.params)

                    event_stream = run_ot_selection_streaming(
                        query_embs=q_embs,
                        sentence_records=sentences,
                        mode=req.mode,
                        params=runtime_params, # <-- Pass the merged dictionary here
                    )
 
                for event in event_stream:
                    if event["event"] == "selection_step":
                        selected_texts.append(event["sentence_text"])
                        selected_ids.append(event["sentence_id"])
                    elif event["event"] == "saturation_reached":
                        tail = event.get("tail_truncated", 0)
                        if tail > 0 and len(selected_texts) > tail + 1:
                            selected_texts = selected_texts[:-tail]
                            selected_ids = selected_ids[:-tail]
 
                    yield make_sse_event(event["event"], event)
                    
                    if req.retrieval_engine == "llm":
                        await asyncio.sleep(0.3) 
                    else:
                        await asyncio.sleep(0)
            else:
                yield make_sse_event("saturation_reached", {
                    "step": 0, "final_ot_cost": 0.0, "final_coverage_pct": 0.0,
                    "total_sentences_selected": 0, "total_tokens": 0,
                    "stopping_reason": "no_documents", "tail_truncated": 0
                })
 
            # 3. Generate answer with conversation history
            full_answer = ""
            for token in get_llm_answer(selected_texts, resolved_query, conversation):
                full_answer += token
                yield make_sse_event("llm_token", {"token": token})
                await asyncio.sleep(0)
 
            # 4. Store the turn
            # 4. Store the turn
            if session:
                turn = ConversationTurn(
                    turn_index=len(conversation) + 1,
                    original_query=req.query,
                    resolved_query=resolved_query,
                    retrieved_sentence_ids=selected_ids,
                    answer=full_answer
                )
                append_turn(req.session_id, turn)
                if not req.is_eval:
                    turn_records = turn_to_sentence_records(turn, encoder)
                    append_sentences(req.session_id, turn_records)
                    
                # ---------------------------------------------------
                # NEW: Trigger asynchronous shadow extraction
                # ---------------------------------------------------
                if not req.is_eval:
                    asyncio.create_task(background_memory_extraction(turn, req.session_id))
 
            yield make_sse_event("answer_complete", {
                "answer": full_answer,
                "context_sentences": selected_texts,
                "secondary_context_sentences": [],
                "total_context_tokens": sum(len(t.split()) for t in selected_texts),
                "turn_index": len(conversation) + 1,
                "turns_remaining": MAX_TURNS - len(conversation) - 1,
                "resolved_query": resolved_query,
            })
            
        except Exception as e:
            traceback.print_exc()
            yield make_sse_event("stream_error", {"detail": str(e)})
 
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

class CompareRequest(BaseModel):
    session_id: str
    query: str
    k: int

@app.post("/compare")
async def compare_endpoint(req: CompareRequest):
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    q_embs = encode_query_plain(req.query, encoder)
    
    # 1. Get Top-K naive sentences
    top_k_results = naive_top_k(q_embs, session.sentences, req.k)
    
    # 2. Compute redundancy
    selected_embeddings = [
        rec.embedding for rec in session.sentences 
        if rec.id in [r["sentence_id"] for r in top_k_results]
    ]
    redundancy = compute_internal_redundancy(selected_embeddings)
    
    # 3. Get LLM Answer for naive context
    selected_texts = [r["sentence_text"] for r in top_k_results]
    total_tokens = sum(len(t.split()) for t in selected_texts)
    
    # We consume the generator entirely for the comparison response
    naive_answer_tokens = list(get_llm_answer(selected_texts, req.query))
    naive_answer = "".join(naive_answer_tokens)
    
    return {
        "selected_sentences": top_k_results,
        "total_tokens": total_tokens,
        "internal_redundancy": redundancy,
        "llm_answer": naive_answer
    }

@app.get("/session/{session_id}/info")
async def get_session_info(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    docs = list(set(r.source_doc for r in session.sentences))
    return {
        "session_id": session_id,
        "documents": docs,
        "total_sentences": len(session.sentences),
        "turn_count": len(session.conversation),
        "turns_remaining": MAX_TURNS - len(session.conversation),
        "conversation": [
            {
                "turn_index": t.turn_index,
                "query": t.original_query,
                "resolved_query": t.resolved_query,
                "answer": t.answer,
                "retrieved_count": len(t.retrieved_sentence_ids),
            }
            for t in session.conversation
        ]
    }

@app.get("/demo-scenarios")
async def get_demo_scenarios():
    return {
        "scenarios": [
            {
                "id": s.id,
                "title": s.title,
                "description": s.description,
                "domain": s.domain,
                "query": s.query,
                "optimal_mode": s.mode
            }
            for s in SCENARIOS.values()
        ]
    }

@app.post("/demo-scenarios/{scenario_id}/load")
async def load_scenario(scenario_id: str):
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail="Scenario not found")
        
    scenario = SCENARIOS[scenario_id]
    session = create_session()
    all_sentence_records = []
    doc_summaries = []
    
    file_idx = 0
    for display_name, file_path in scenario.doc_files:
        if not file_path.exists():
            continue
            
        with open(file_path, "rb") as f:
            content = f.read()
            
        text = parse_file(file_path.name, content)
        sentences = chunk_into_sentences(text, encoder)
        embeddings = encoder.encode(sentences)
        
        for line_idx, (sent_text, emb) in enumerate(zip(sentences, embeddings)):
            all_sentence_records.append(SentenceRecord(
                id=f"doc{file_idx}_s{line_idx}",
                text=sent_text,
                source_doc=display_name,
                source_line=line_idx + 1,
                embedding=emb
            ))
            
        doc_summaries.append({
            "filename": display_name,
            "num_sentences": len(sentences),
            "status": "encoded"
        })
        file_idx += 1
        
    store_sentences(session.session_id, all_sentence_records)
    
    return {
        "session_id": session.session_id,
        "documents": doc_summaries,
        "total_sentences": len(all_sentence_records)
    }

class LocomoSentenceIn(BaseModel):
    id: str
    text: str
    source_doc: str
    source_line: int
    embedding: List[float]

class LocomoLoadRequest(BaseModel):
    sentences: List[LocomoSentenceIn]

@app.post("/eval/locomo/load")
async def load_locomo_session(req: LocomoLoadRequest):
    """
    Eval-only endpoint: loads pre-embedded LoCoMo conversation turns into a
    fresh session, bypassing /ingest and its chunker so dia_ids from the
    LoCoMo annotations survive intact for evidence-recall scoring.
    """
    session = create_session()
    records = [
        SentenceRecord(
            id=s.id,
            text=s.text,
            source_doc=s.source_doc,
            source_line=s.source_line,
            embedding=torch.tensor(s.embedding, dtype=torch.float32),
        )
        for s in req.sentences
    ]
    store_sentences(session.session_id, records)
    return {"session_id": session.session_id, "total_sentences": len(records)}

def sync_memory_to_session(session_id: str):
    """
    Loads OKF memory files, converts them into SentenceRecords, 
    and synchronizes them with the current session context pool.
    """
    session = get_session(session_id)
    if not session or not encoder:
        return

    memories = load_okf_memories()
    new_memory_records = []
    
    # Get a list of IDs currently in the session to prevent duplication
    existing_ids = {rec.id for rec in session.sentences}

    for mem in memories:
        meta = mem["metadata"]
        mem_id = meta.get("id")
        record_id = f"mem_{mem_id}"
        
        # Skip if this memory is already loaded in the session context
        if record_id in existing_ids:
            continue
            
        # Construct a dense text representation for the OT Engine and LLM
        mem_type = meta.get('type', 'fact').upper()
        subject = meta.get('subject', 'System')
        predicate = meta.get('predicate', 'stated')
        obj = meta.get('object', '')
        
        dense_text = (
            f"[MEMORY: {mem_type}] {subject} {predicate} {obj}. "
            f"{mem['body']}"
        )
        
        # Embed the memory
        emb = encoder.encode([dense_text])[0].cpu()
        
        new_memory_records.append(
            SentenceRecord(
                id=record_id,
                text=dense_text,
                source_doc=f"Memory Store ({mem['file_name']})",
                source_line=1,
                embedding=emb
            )
        )
        
    if new_memory_records:
        append_sentences(session_id, new_memory_records)


async def background_memory_extraction(turn: ConversationTurn, session_id: str):
    def run_sync_pipeline():
        result = extract_memory_candidates(turn, session_id)
        candidates = result.get("candidates", [])
        for candidate in candidates:
            # Replaces the old write_okf_memory call
            reconcile_and_save(candidate, session_id, turn.turn_index) 
            
    await asyncio.to_thread(run_sync_pipeline)

class MemoryUpdateRequest(BaseModel):
    file_name: str
    new_content: str

@app.get("/memory/inspect")
async def inspect_memory():
    from backend.memory.loader import load_okf_memories
    from backend.memory.okf_writer import ACTIVITY_LOG
    
    memories = load_okf_memories()
    log_lines = []
    
    import os
    if os.path.exists(ACTIVITY_LOG):
        with open(ACTIVITY_LOG, "r") as f:
            log_lines = f.readlines()[-20:] # Get last 20 operations
            
    return {"memories": memories, "logs": log_lines}

@app.post("/memory/update")
async def update_memory(req: MemoryUpdateRequest):
    import os
    from datetime import datetime
    from backend.memory.okf_writer import ACTIVITY_LOG
    
    filepath = os.path.join(".eviot/memory/sessions", req.file_name)
    if not os.path.exists(filepath):
        return {"error": "File not found"}
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(req.new_content)
        
    with open(ACTIVITY_LOG, "a") as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{timestamp}] EDITED rule file {req.file_name} via UI\n")
        
    return {"status": "success"}