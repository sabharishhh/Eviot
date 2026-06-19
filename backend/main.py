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

from session import create_session, store_sentences, get_session, SentenceRecord
from ingestion.parser import parse_file
from ingestion.chunker import chunk_into_sentences

from retrieval.naive_rag import naive_top_k, compute_internal_redundancy
from retrieval.ot_engine import encode_query_plain, encode_query_decomposed, run_ot_selection_streaming
from retrieval.llm_engine import run_llm_selection_streaming

from llm.answer import get_llm_answer
from demo.scenarios import SCENARIOS

from eviot.encoders.encoder import Encoder

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
            
        sentences = chunk_into_sentences(text, encoder)

        if not sentences:
            continue

        # Bulk encode
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
            "num_pages": 1,
            "status": "encoded"
        })

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
    retrieval_engine: str = "ot"  
    params: dict = {}

@app.post("/query")
async def query_endpoint(req: QueryRequest):
    session = get_session(req.session_id)
    sentences = session.sentences if session else []

    async def event_generator():
        try:
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

            selected_texts = []
            selected_ids = []

            if sentences:
                if req.retrieval_engine == "llm":
                    event_stream = run_llm_selection_streaming(req.query, sentences)
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

            final_context_texts = selected_texts
            secondary_context_texts = []

            full_answer = ""
            for token in get_llm_answer(final_context_texts, req.query):
                full_answer += token
                yield make_sse_event("llm_token", {"token": token})
                await asyncio.sleep(0)

            yield make_sse_event("answer_complete", {
                "answer": full_answer,
                "context_sentences": selected_texts,
                "secondary_context_sentences": secondary_context_texts,
                "total_context_tokens": sum(len(t.split()) for t in final_context_texts),
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield make_sse_event("stream_error", {"detail": str(e)})

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