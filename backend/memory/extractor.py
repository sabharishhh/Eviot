import os
import json
from openai import OpenAI
try:
    # Works when running tests from the root directory
    from backend.session import ConversationTurn
except ModuleNotFoundError:
    # Works when running main.py directly from the backend directory
    from session import ConversationTurn

def extract_memory_candidates(turn: ConversationTurn, session_id: str) -> dict:
    """
    Evaluates a completed conversation turn to determine if it contains 
    persistent knowledge, decisions, or preferences.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"candidates": []}
        
    client = OpenAI(api_key=api_key)
    
    system_prompt = """
    You are the Eviot Memory Extractor.
    Your goal is to extract persistent knowledge, decisions, or preferences from the conversation.
    
    STRICT RULES FOR EXTRACTION:
    1. SOURCE AUTHORITY: Only extract information that is explicitly stated by the USER as an instruction, rule, or preference. 
    2. IGNORE REPETITIONS: If the Assistant is merely repeating back a decision previously established in the conversation, IGNORE IT. Do not create new memory candidates for facts already established.
    3. ASSISTANT LIMITATION: Only extract from the Assistant's response if it contains a NEW clarification or a complex technical derivation requested by the user. Do not extract facts the Assistant is simply regurgitating from the current context.
    
    Output a JSON object exactly matching this schema:
    {
      "candidates": [
        {
          "candidate_id": "<generate_unique_string>",
          "memory_type": "<decision|preference|semantic|episodic>",
          "subject": "<entity_name>",
          "predicate": "<verb>",
          "object": "<target_value>",
          "epistemic_state": "<decided|considered|preferred>",
          "summary": "<one_sentence_summary>",
          "confidence": <float_0_to_1>
        }
      ]
    }
    If the content is repetitive, conversational filler, or already known, return {"candidates": []}.
    """
    
    user_prompt = f"""
    Session: {session_id}
    Turn ID: {turn.turn_index}
    Query: {turn.resolved_query}
    Assistant Answer: {turn.answer}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Cost-effective for background structured extraction
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Memory extraction failed: {e}")
        return {"candidates": []}