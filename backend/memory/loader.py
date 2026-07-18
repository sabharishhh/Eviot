import os
import yaml

MEMORY_DIR = ".eviot/memory/sessions"

# Parsed memories cached against a directory signature (filenames + mtimes).
# Both the 3s panel poll and every /query hit this function, so re-reading and
# re-parsing the whole store each time is the single hottest path in the app.
_cache_signature = None
_cache_value: list[dict] = []


def _dir_signature(path: str):
    """Cheap stat-only fingerprint. Changes if any file is added, removed,
    or modified — including status flips written by the reconciler."""
    try:
        return tuple(sorted(
            (name, os.path.getmtime(os.path.join(path, name)))
            for name in os.listdir(path)
            if name.endswith(".md")
        ))
    except FileNotFoundError:
        return ()


def load_okf_memories() -> list[dict]:
    """
    Reads all active Open Knowledge Format memory files from the filesystem.
    """
    global _cache_signature, _cache_value

    signature = _dir_signature(MEMORY_DIR)
    if signature == _cache_signature:
        return _cache_value

    memories = []
    if not os.path.exists(MEMORY_DIR):
        _cache_signature, _cache_value = signature, memories
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

    _cache_signature, _cache_value = signature, memories
    return memories