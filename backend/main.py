from dotenv import load_dotenv
load_dotenv()

import time
import json
import asyncio
import traceback
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from session import (
    create_session, store_sentences, append_sentences,
    get_session, SentenceRecord, ConversationTurn, append_turn
)
from ingestion.parser import parse_file
from ingestion.chunker import chunk_into_sentences

from retrieval.naive_rag import naive_top_k, compute_internal_redundancy
from retrieval.ot_engine import encode_query_plain, encode_query_decomposed, run_ot_selection_streaming
from retrieval.llm_engine import run_llm_selection_streaming

from llm.answer import get_llm_answer
from demo.scenarios import SCENARIOS

from eviot.encoders.encoder import Encoder

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
        for t in conversation[-3:]
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
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

@app.post("/query")
async def query_endpoint(req: QueryRequest):
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
                    event_stream = run_ot_selection_streaming(
                        query_embs=q_embs,
                        sentence_records=sentences,
                        mode=req.mode,
                        params=req.params,
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
            if session:
                turn = ConversationTurn(
                    turn_index=len(conversation) + 1,
                    original_query=req.query,
                    resolved_query=resolved_query,
                    retrieved_sentence_ids=selected_ids,
                    answer=full_answer
                )
                append_turn(req.session_id, turn)
 
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