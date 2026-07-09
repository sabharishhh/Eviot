import os
import yaml

MEMORY_DIR = ".eviot/memory/sessions"

def load_okf_memories() -> list[dict]:
    """
    Reads all active Open Knowledge Format memory files from the filesystem.
    """
    memories = []
    if not os.path.exists(MEMORY_DIR):
        return memories

    for file_name in os.listdir(MEMORY_DIR):
        if file_name.endswith(".md"):
            filepath = os.path.join(MEMORY_DIR, file_name)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Parse the OKF structure: YAML Frontmatter + Markdown Body
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    try:
                        metadata = yaml.safe_load(parts[1])
                        body = parts[2].strip()
                        
                        # Only load active memory (ignore superseded/archived)
                        if metadata.get("status") == "active":
                            memories.append({
                                "metadata": metadata,
                                "body": body,
                                "file_name": file_name
                            })
                    except Exception as e:
                        print(f"Error parsing memory file {file_name}: {e}")
                        
    return memories