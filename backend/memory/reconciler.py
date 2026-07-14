import json
import os
from datetime import datetime
from openai import OpenAI
from backend.memory.loader import load_okf_memories
from backend.memory.okf_writer import write_okf_memory, ACTIVITY_LOG

def reconcile_and_save(candidate: dict, session_id: str, turn_index: int):
    existing = load_okf_memories()

    # If the database is empty, just write it
    if not existing:
        write_okf_memory(candidate, session_id, turn_index)
        return

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        write_okf_memory(candidate, session_id, turn_index)
        return

    client = OpenAI(api_key=api_key)

    # Condense existing active memory into a prompt context
    existing_context = "\n".join([
        f"ID: {m['metadata']['id']} | Subject: {m['metadata'].get('subject')} | "
        f"Predicate: {m['metadata'].get('predicate')} | Object: {m['metadata'].get('object')}"
        for m in existing
    ])

    system_prompt = """
    You are the Eviot Memory Reconciler. 
    Compare the NEW CANDIDATE against the EXISTING ACTIVE MEMORIES.
    If the new candidate represents the exact same fact, updates an existing rule, or contradicts an existing memory, it MUST supersede the old one.
    
    Output JSON exactly matching this schema:
    {
        "operation": "create" | "supersede",
        "existing_memory_id": "<id_of_the_memory_to_replace_if_supersede>"
    }
    """

    user_prompt = f"EXISTING MEMORIES:\n{existing_context}\n\nNEW CANDIDATE:\n{json.dumps(candidate)}"

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

        # Process the supersession
        if decision.get("operation") == "supersede" and decision.get("existing_memory_id"):
            target_id = decision.get("existing_memory_id")

            for m in existing:
                if m["metadata"]["id"] == target_id:
                    old_filepath = os.path.join(
                        ".eviot/memory/sessions",
                        m["file_name"]
                    )

                    with open(old_filepath, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Demote the old file
                    content = content.replace(
                        "status: active",
                        "status: superseded"
                    )

                    with open(old_filepath, "w", encoding="utf-8") as f:
                        f.write(content)

                    # Log the administrative change
                    with open(ACTIVITY_LOG, "a") as f:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        f.write(
                            f"[{timestamp}] SUPERSEDED memory {target_id} (Merged duplicate/update)\n"
                        )
                    break

        # Write the new definitive candidate to disk
        write_okf_memory(candidate, session_id, turn_index)

    except Exception as e:
        print(f"Reconciliation failed: {e}")
        write_okf_memory(candidate, session_id, turn_index)