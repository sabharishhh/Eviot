import os
import yaml
from datetime import datetime

MEMORY_DIR = ".eviot/memory/sessions"
ACTIVITY_LOG = ".eviot/memory/activity_log.txt"

def ensure_dirs():
    os.makedirs(MEMORY_DIR, exist_ok=True)
    if not os.path.exists(ACTIVITY_LOG):
        with open(ACTIVITY_LOG, "w") as f:
            f.write(f"--- Eviot Memory Activity Log Initialized ---\n")

def write_okf_memory(candidate: dict, session_id: str, turn_index: int):
    """
    Serializes a memory candidate into Open Knowledge Format (Markdown + YAML)
    """
    ensure_dirs()
    
    mem_id = candidate.get("candidate_id", f"mem_{datetime.now().timestamp()}")
    file_path = os.path.join(MEMORY_DIR, f"{session_id}_{mem_id}.md")
    
    # Construct YAML Frontmatter
    metadata = {
        "id": mem_id,
        "type": candidate.get("memory_type", "fact"),
        "status": "active",
        "confidence": candidate.get("confidence", 0.5),
        "created_at": datetime.now().isoformat(),
        "subject": candidate.get("subject"),
        "predicate": candidate.get("predicate"),
        "object": candidate.get("object"),
        "epistemic_state": candidate.get("epistemic_state"),
        "source": {
            "session_id": session_id,
            "turn_index": turn_index
        }
    }
    
    # Construct Markdown Body
    summary = candidate.get("summary", "")
    markdown_content = f"""---
{yaml.dump(metadata, default_flow_style=False).strip()}
---

# {candidate.get("subject", "Memory")} - {candidate.get("memory_type", "Entry")}

{summary}
"""
    
    with open(file_path, "w") as f:
        f.write(markdown_content)
        
    # Append to activity log
    with open(ACTIVITY_LOG, "a") as f:
        log_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] CREATED memory file {file_path} (Session: {session_id}, Turn: {turn_index})\n"
        f.write(log_entry)