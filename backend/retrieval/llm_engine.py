import json
from typing import Generator, List
from session import SentenceRecord
from openai import OpenAI

client = OpenAI()

def run_llm_selection_streaming(
    query: str, 
    sentence_records: List[SentenceRecord]
) -> Generator[dict, None, None]:
    """
    Passes all candidate sentences to gpt-5.4-mini and asks it to select 
    the relevant ones. Formats the output to mimic the OT event stream.
    """
    
    # 1. Format candidates for the LLM
    candidates_json = json.dumps(
        [{"id": s.id, "text": s.text} for s in sentence_records], 
        indent=2
    )
    
    prompt = f"""
    You are a retrieval engine. Analyze the user's query and the list of candidate sentences.
    Select the absolute minimum set of sentences required to fully answer the query.
    
    Query: "{query}"
    
    Candidates:
    {candidates_json}
    
    Output STRICT JSON containing a 'selected_ids' array with the IDs of the necessary sentences.
    """
    
    # 2. Call OpenAI synchronously
    try:
        response = client.chat.completions.create(
            model="gpt-5.4-mini",
            messages=[
                {"role": "system", "content": "You output strict JSON in the format: {'selected_ids': ['id1', 'id2']}"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        data = json.loads(response.choices[0].message.content)
        selected_ids = data.get("selected_ids", [])
    except Exception as e:
        print(f"LLM Retrieval failed: {e}")
        selected_ids = []

    # 3. Map selected IDs back to actual records
    selected_records = [s for s in sentence_records if s.id in selected_ids]
    cumulative_tokens = 0
    total = max(len(selected_records), 1)

    # 4. Stream fake events to the UI so the Context Log and Gauge still animate
    for step_idx, record in enumerate(selected_records):
        cumulative_tokens += len(record.text.split())
        
        # We fake the math metrics since LLMs don't have OT costs
        fake_coverage = round((step_idx + 1) / total, 4)
        fake_gain = round(1.0 / total, 4)
        
        yield {
            "event": "selection_step",
            "step": step_idx + 1,
            "sentence_id": record.id,
            "sentence_text": record.text,
            "source_doc": record.source_doc,
            "source_line": record.source_line,
            "ot_cost": 0.0, 
            "marginal_gain": fake_gain,
            "coverage_pct": fake_coverage,
            "cumulative_tokens": cumulative_tokens,
        }

    # 5. Yield Saturation
    yield {
        "event": "saturation_reached",
        "step": len(selected_records),
        "final_ot_cost": 0.0,
        "final_coverage_pct": 1.0 if selected_records else 0.0,
        "total_sentences_selected": len(selected_records),
        "total_tokens": cumulative_tokens,
        "stopping_reason": "llm_selection_complete",
        "tail_truncated": 0
    }