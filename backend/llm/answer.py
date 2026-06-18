import os
from typing import Generator

def get_llm_answer(context_sentences: list[str], query: str) -> Generator[str, None, None]:
    """
    Stream LLM answer tokens. Tries OpenAI first, falls back to Ollama.
    """
    context_block = "\n".join(
        f"[{i+1}] {s}" for i, s in enumerate(context_sentences)
    )
    system_prompt = (
        "You are a precise reasoning assistant. "
        "Answer the question using ONLY the numbered context sentences provided. "
        "If the context is insufficient to answer, state that clearly. "
        "Be concise. Do not add information not present in the context."
    )
    user_message = f"Context:\n{context_block}\n\nQuestion: {query}"

    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        yield from _openai_stream(system_prompt, user_message, api_key)
    else:
        yield from _ollama_stream(system_prompt, user_message)

def _openai_stream(system_prompt: str, user_message: str, api_key: str):
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    try:
        stream = client.chat.completions.create(
            model="gpt-5.4-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            stream=True,
            max_completion_tokens=512,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception as e:
        yield f"[OpenAI Error — Answer generation unavailable: {e}]"

def _ollama_stream(system_prompt: str, user_message: str):
    import requests, json
    payload = {
        "model": "llama3",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": True,
    }
    try:
        resp = requests.post(
            "http://localhost:11434/api/chat",
            json=payload,
            stream=True,
            timeout=60,
        )
        for line in resp.iter_lines():
            if line:
                data = json.loads(line)
                token = data.get("message", {}).get("content", "")
                if token:
                    yield token
    except Exception as e:
        yield f"[Ollama LLM unavailable: {e}]"