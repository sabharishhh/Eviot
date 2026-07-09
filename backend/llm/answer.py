import os
from typing import Generator

def get_llm_answer(context_sentences: list[str], query: str, conversation: list = None) -> Generator[str, None, None]:
    """
    Stream LLM answer tokens with separate boundaries for document facts
    and literal conversation logs to prevent meta-history hallucinations.
    """
    # Build the document context block cleanly
    context_block = "\n".join([f"[{idx+1}] {s}" for idx, s in enumerate(context_sentences)])
    
    system_prompt = (
        "You are Eviot, a precise reasoning assistant equipped with a persistent Knowledge Graph and document retrieval.\n\n"
        "You are provided with two sources of data:\n"
        "1. DOCUMENT CONTEXT: Numbered lines extracted from knowledge documents and persistent system memory ([MEMORY: ...]).\n"
        "2. CONVERSATION HISTORY: A chronological log of recent chat turns between you and the user.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "- CONVERSATIONAL AWARENESS & SYSTEM RULES: If the user declares an architectural rule, decision, or preference (e.g., 'Our database is PostgreSQL', 'Enforce AES-256'), ACKNOWLEDGE IT NATURALLY and confirm the rule is set. DO NOT say 'I cannot confirm this from the document.' You are building the architecture WITH the user.\n"
        "- DOCUMENT QUESTIONS: Answer factual questions about the topic using ONLY the numbered DOCUMENT CONTEXT lines.\n"
        "- TRUST HIERARCHY: If a line in the DOCUMENT CONTEXT begins with [MEMORY: ...], it represents the CURRENT, VERIFIED TRUTH. If the CONVERSATION HISTORY contains older, contradictory information, the [MEMORY] statement STRICTLY OVERRIDES it. Never revert to outdated conversation history.\n"
        "- CHAT SUMMARIZATION: If the user asks you to summarize, list topics, or review what 'we have discussed/talked about so far in this chat', rely strictly on the literal messages present in the CONVERSATION HISTORY log, NOT the text inside the DOCUMENT CONTEXT.\n"
        "- TEMPORAL LOGIC: Pay strict attention to timestamps, session numbers, or dates mentioned. Translate relative time expressions (like 'yesterday' or 'last year') into exact dates based on surrounding timestamps.\n"
        "- FALLBACK: If both data sources are insufficient to answer a document-specific question, state that clearly.\n"
        "- Be concise. Do not introduce outside knowledge or facts missing from the provided inputs."
    )

    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        yield from _openai_stream(system_prompt, context_block, query, api_key, conversation)
    else:
        yield from _ollama_stream(system_prompt, context_block, query, conversation)


def _openai_stream(system_prompt: str, context_block: str, query: str, api_key: str, conversation: list = None):
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Process and append the FULL conversation log (no truncation)
    if conversation:
        for turn in conversation:
            # Safely fetch fields matching the ConversationTurn attributes found in main.py
            user_msg = getattr(turn, 'original_query', '')
            asst_msg = getattr(turn, 'answer', '')
            
            if user_msg:
                messages.append({"role": "user", "content": user_msg})
            if asst_msg:
                messages.append({"role": "assistant", "content": asst_msg})
                
    # Append the current active turn along with its retrieved Document Context
    current_prompt = (
        f"DOCUMENT CONTEXT:\n{context_block}\n\n"
        f"USER QUESTION: {query}"
    )
    messages.append({"role": "user", "content": current_prompt})
    
    response = client.chat.completions.create(
        model="gpt-5.4-mini",
        messages=messages,
        temperature=0.0,
        stream=True
    )
    
    for chunk in response:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

def _ollama_stream(system_prompt: str, context_block: str, query: str, conversation=None):
    import requests, json
    messages = _build_messages(system_prompt, context_block, query, conversation)
    payload = {"model": "llama3", "messages": messages, "stream": True}
    try:
        resp = requests.post(
            "http://localhost:11434/api/chat",
            json=payload, stream=True, timeout=60,
        )
        for line in resp.iter_lines():
            if line:
                data = json.loads(line)
                token = data.get("message", {}).get("content", "")
                if token:
                    yield token
    except Exception as e:
        yield f"[Ollama LLM unavailable: {e}]"