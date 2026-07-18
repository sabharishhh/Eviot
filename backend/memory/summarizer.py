import os
from typing import List, Optional

from openai import OpenAI

try:
    from backend.session import ConversationTurn
except ModuleNotFoundError:
    from session import ConversationTurn


SYSTEM_PROMPT = (
    "You maintain a rolling summary of one conversation.\n\n"
    "You receive the summary so far (possibly empty) plus the turns that have just "
    "scrolled out of the assistant's visible context. Fold the new turns into the "
    "existing summary and return the updated version.\n\n"
    "RULES:\n"
    "- Keep it under 150 words. Compress older material harder as it accumulates.\n"
    "- Capture the thread of the conversation: what was being worked on, what was "
    "decided, what is unresolved. Narrative, not a bullet list of facts.\n"
    "- Do NOT catalogue discrete facts about the user (names, preferences, tool "
    "choices). A separate memory system stores those with reconciliation; "
    "duplicating them here creates two sources that can disagree.\n"
    "- Preserve open threads and anything the user asked for but has not received.\n"
    "- Write plain prose. No headers, no preamble, no meta-commentary.\n"
    "- Return only the summary text."
)


def build_session_summary(
    previous_summary: Optional[str],
    new_turns: List[ConversationTurn],
) -> Optional[str]:
    """Fold newly-archived turns into the rolling summary.

    Returns None on failure so the caller keeps the previous summary rather
    than overwriting good text with nothing.
    """
    if not new_turns:
        return previous_summary

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return previous_summary

    client = OpenAI(api_key=api_key)

    transcript = "\n\n".join(
        f"[turn {t.turn_index}]\nUser: {t.original_query}\nAssistant: {t.answer}"
        for t in new_turns
    )

    user_prompt = (
        f"SUMMARY SO FAR:\n{previous_summary or '(none yet)'}\n\n"
        f"NEW TURNS TO FOLD IN:\n{transcript}\n\n"
        "Return the updated summary."
    )

    try:
        response = client.responses.create(
            model="gpt-5.6-terra",
            instructions=SYSTEM_PROMPT,
            input=user_prompt,
            reasoning={"effort": "none"},
        )
        text = response.output_text.strip()
        return text or previous_summary
    except Exception as e:
        print(f"Summary generation failed: {e}")
        return previous_summary