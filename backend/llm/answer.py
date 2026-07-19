import os
from typing import Generator

_GROUNDED_PROMPT = (
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

_OPEN_PROMPT = (
    "You are Eviot, a precise reasoning assistant equipped with a persistent Knowledge Graph and document retrieval.\n\n"
    "OPEN CONVERSATION MODE: nothing in the user's workspace (documents or persistent memory) was relevant to this "
    "question, so no DOCUMENT CONTEXT is supplied. Answer normally, using your own knowledge and the CONVERSATION HISTORY.\n\n"
    "CRITICAL INSTRUCTIONS:\n"
    "- Answer directly and helpfully. Do NOT say you cannot find this in the documents, and do NOT mention retrieval, "
    "context, or the absence of sources unless the user asks about them.\n"
    "- DECLARATIONS: If the user states a fact, decision, or preference, acknowledge it naturally. It will be persisted "
    "to long-term memory and available in later sessions.\n"
    "- CHAT SUMMARIZATION: If asked what has been discussed, rely strictly on the literal CONVERSATION HISTORY log.\n"
    "- TEMPORAL LOGIC: Translate relative time expressions into exact dates where surrounding timestamps allow.\n"
    "- Never fabricate citations, document references, or claims of retrieval support you do not have.\n"
    "- Be concise."
)

def get_llm_answer(
    context_sentences: list[str],
    query: str,
    conversation: list = None,
    grounded: bool = None,
    summary: str = None,
    standing: list[str] = None,
) -> Generator[str, None, None]:
    """
    Stream LLM answer tokens with separate boundaries for document facts
    and literal conversation logs to prevent meta-history hallucinations.

    `grounded` selects the prompt mode. Defaults to whether any context
    survived the relevance gate.
    """
    if grounded is None:
        grounded = bool(context_sentences)

    context_block = "\n".join(
        [f"[{idx+1}] {s}" for idx, s in enumerate(context_sentences)]
    )
    system_prompt = _GROUNDED_PROMPT if grounded else _OPEN_PROMPT

    # Standing instructions apply to every reply, so they belong in the system
    # prompt rather than the retrieved-context block. Placed last so they take
    # precedence over the generic formatting guidance above.
    if standing:
        print(f"[standing] {len(standing)} injected: {standing}")
        rules = "\n".join(f"- {s}" for s in standing)
        system_prompt += (
            "\n\nSTANDING USER INSTRUCTIONS (persist across all sessions; follow "
            "them unless the current message overrides them):\n" + rules
        )

    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        yield from _openai_stream(system_prompt, context_block, query, api_key, conversation, grounded, summary)
    else:
        yield from _ollama_stream(system_prompt, context_block, query, conversation, grounded, summary)

def _openai_stream(
    system_prompt: str,
    context_block: str,
    query: str,
    api_key: str,
    conversation: list = None,
    grounded: bool = True,
    summary: str = None,
):
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    input_items = []

    # Earlier context that has scrolled out of the verbatim window. Injected as
    # a user/assistant exchange rather than appended to instructions so it sits
    # chronologically before the visible turns, which is where it belongs.
    if summary:
        input_items.append({
            "role": "user",
            "content": f"SUMMARY OF EARLIER CONVERSATION:\n{summary}",
        })
        input_items.append({
            "role": "assistant",
            "content": "Understood — I have the earlier context.",
        })

    if conversation:
        for turn in conversation:
            user_msg = getattr(turn, "original_query", "")
            asst_msg = getattr(turn, "answer", "")

            if user_msg:
                input_items.append({"role": "user", "content": user_msg})
            if asst_msg:
                input_items.append({"role": "assistant", "content": asst_msg})

    # In open mode, omit the DOCUMENT CONTEXT header entirely — an empty
    # labelled block reads as "the documents were checked and were blank",
    # which nudges the model toward refusing.
    if grounded and context_block:
        content = f"DOCUMENT CONTEXT:\n{context_block}\n\nUSER QUESTION: {query}"
    else:
        content = query

    input_items.append({"role": "user", "content": content})

    stream = client.responses.create(
        model="gpt-5.6-terra",
        instructions=system_prompt,
        input=input_items,
        reasoning={"effort": "none"},
        stream=True,
    )

    for event in stream:
        if event.type == "response.output_text.delta":
            yield event.delta

def _ollama_stream(system_prompt: str, context_block: str, query: str, conversation=None, grounded: bool = True):
    import requests, json
    if grounded and context_block:
        user_content = f"DOCUMENT CONTEXT:\n{context_block}\n\nUSER QUESTION: {query}"
    else:
        user_content = query
    messages = _build_messages(system_prompt, user_content, "", conversation)
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