import os
import json
import uuid
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
    1. SOURCE AUTHORITY: Extract instructions, rules, preferences, AND definitive project facts stated by the user (e.g., "Our database is X", "We use Y framework").
    2. IGNORE REPETITIONS: If a fact is already established in current memory, IGNORE IT. Do not create new memory candidates for facts already known.
    3. ASSISTANT LIMITATION: Do not extract facts the Assistant is simply regurgitating. Only extract if the Assistant is providing new, validated technical derivations requested by the user.
    4. ENTITY LENGTH: The 'subject' and 'object' fields MUST be 1 to 3 words maximum (e.g., 'PostgreSQL', 'FastAPI', 'Backend Database'). Never use full sentences.
    5. USER COMMANDS ONLY: ONLY extract decisions explicitly declared by the User. Ignore the Assistant's summaries of the uploaded documents.
    
    Output a JSON object exactly matching this schema:
    {
      "candidates": [
        {
          "memory_type": "<decision|preference|semantic|episodic>",
          "subject": "<entity_name_1_to_3_words>",
          "predicate": "<verb>",
          "object": "<target_value_1_to_3_words>",
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

    Respond with a json object matching the required schema.
    """
    
    try:
        response = client.responses.create(
            model="gpt-5.6-terra",
            instructions=system_prompt,
            input=user_prompt,
            reasoning={"effort": "none"},
            text={
                "format": {
                    "type": "json_object"
                }
            },
        )

        decision = json.loads(response.output_text)

        # Inject guaranteed unique IDs
        if "candidates" in decision:
            for candidate in decision["candidates"]:
                candidate["candidate_id"] = uuid.uuid4().hex[:8]

        return decision

    except Exception as e:
        print(f"Memory extraction failed: {e}")
        return {"candidates": []}