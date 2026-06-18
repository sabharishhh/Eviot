import time
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from session import create_session, store_sentences, SentenceRecord
from ingestion.parser import parse_file
from ingestion.chunker import chunk_into_sentences

import json
import asyncio
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from retrieval.naive_rag import naive_top_k, compute_internal_redundancy
from demo.scenarios import SCENARIOS
from llm.answer import get_llm_answer

from session import get_session
from retrieval.ot_engine import encode_query_plain, encode_query_decomposed, run_ot_selection_streaming
from llm.answer import get_llm_answer

# We import your eviot library here!
from eviot.encoders.encoder import Encoder

# Global singleton for the encoder
encoder = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global encoder
    print("Loading BAAI/bge-base-en-v1.5 encoder... (This might take a moment)")
    encoder = Encoder(model_name="BAAI/bge-base-en-v1.5")
    
    # Pre-warm the encoder to prevent latency on the first query
    encoder.encode(["Warming up the encoder."])
    print("Encoder ready. FastAPI is up.")
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/ingest")
async def ingest_documents(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
        
    start_time = time.time()
    session = create_session()
    all_sentence_records = []
    doc_summaries = []

    for file_idx, file in enumerate(files):
        content = await file.read()
        
        try:
            text = parse_file(file.filename, content)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        sentences = chunk_into_sentences(text)

        if not sentences:
            continue

        # Bulk encode all sentences in this document for maximum speed
        embeddings = encoder.encode(sentences)

        for line_idx, (sent_text, emb) in enumerate(zip(sentences, embeddings)):
            record = SentenceRecord(
                id=f"doc{file_idx}_s{line_idx}",
                text=sent_text,
                source_doc=file.filename,
                source_line=line_idx + 1,
                embedding=emb
            )
            all_sentence_records.append(record)

        doc_summaries.append({
            "filename": file.filename,
            "num_sentences": len(sentences),
            "num_pages": 1, # simplified metadata for demo
            "status": "encoded"
        })

    # Store in memory cache (this implicitly moves tensors to CPU via our session.py)
    store_sentences(session.session_id, all_sentence_records)

    encoding_time_ms = int((time.time() - start_time) * 1000)

    return {
        "session_id": session.session_id,
        "documents": doc_summaries,
        "total_sentences": len(all_sentence_records),
        "encoding_time_ms": encoding_time_ms
    }

def make_sse_event(event_type: str, data: dict) -> str:
    payload = json.dumps({"type": event_type, **data})
    return f"data: {payload}\n\n"

class QueryRequest(BaseModel):
    session_id: str
    query: str
    mode: str = "adaptive"
    use_decomposition: bool = True
    params: dict = {}

@app.post("/query")
async def query_endpoint(req: QueryRequest):
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.sentences:
        raise HTTPException(status_code=400, detail="No documents ingested")

    async def event_generator():
        # 1. Embed query
        if req.use_decomposition:
            phrases, q_embs = encode_query_decomposed(req.query, encoder)
            yield make_sse_event("query_embedded", {
                "decomposed": True,
                "phrases": phrases,
            })
        else:
            q_embs = encode_query_plain(req.query, encoder)
            yield make_sse_event("query_embedded", {
                "decomposed": False,
                "phrases": None,
            })

        # 2. Stream selection steps (Optimal Transport)
        selected_texts = []
        for event in run_ot_selection_streaming(
            query_embs=q_embs,
            sentence_records=session.sentences,
            mode=req.mode,
            params=req.params,
        ):
            if event["event"] == "selection_step":
                selected_texts.append(event["sentence_text"])
            yield make_sse_event(event["event"], event)
            await asyncio.sleep(0)  # Yield control to flush buffer!

        # 3. Stream LLM answer
        full_answer = ""
        for token in get_llm_answer(selected_texts, req.query):
            full_answer += token
            yield make_sse_event("llm_token", {"token": token})
            await asyncio.sleep(0)

        yield make_sse_event("answer_complete", {
            "answer": full_answer,
            "context_sentences": selected_texts,
            "total_context_tokens": sum(len(t.split()) for t in selected_texts),
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
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
        sentences = chunk_into_sentences(text)
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