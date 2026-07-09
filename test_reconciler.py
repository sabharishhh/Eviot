import os
import yaml
import shutil
from typing import Dict, Any

# 1. Override the directory for safe testing
TEST_DIR = ".eviot/test_sessions"
os.makedirs(TEST_DIR, exist_ok=True)

# Paste your functions here, but point them to TEST_DIR
def reconcile_memory_candidate(candidate: Dict[str, Any], memory_dir=TEST_DIR):
    candidate_subject = candidate.get("subject")
    candidate_predicate = candidate.get("predicate")
    candidate_object = candidate.get("object")
    
    for filename in os.listdir(memory_dir):
        if not filename.endswith(".md"): continue
        filepath = os.path.join(memory_dir, filename)
        
        with open(filepath, "r") as f:
            content = f.read()
            
        try:
            parts = content.split("---")
            if len(parts) < 3: continue
            metadata = yaml.safe_load(parts[1])
        except Exception:
            continue
            
        if (metadata.get("subject") == candidate_subject and 
            metadata.get("predicate") == candidate_predicate and 
            metadata.get("status") == "active"):
            
            if metadata.get("object") == candidate_object:
                metadata["confidence"] = min(1.0, float(metadata.get("confidence", 0.5)) + 0.05)
                existing_turns = metadata.get("source", {}).get("turn_ids", [])
                new_turns = candidate.get("evidence", {}).get("turn_ids", [])
                metadata["source"]["turn_ids"] = list(set(existing_turns + new_turns))
                metadata["updated_at"] = candidate.get("created_at")
                
                _write_okf_file(filepath, metadata, parts[2])
                return "REINFORCED"
            else:
                metadata["status"] = "superseded"
                metadata["epistemic_state"] = "superseded"
                metadata["updated_at"] = candidate.get("created_at")
                _write_okf_file(filepath, metadata, parts[2])
                return "CREATED"

    return "CREATED"

def _write_okf_file(filepath: str, metadata: dict, body: str):
    with open(filepath, "w") as f:
        f.write("---\n")
        yaml.safe_dump(metadata, f, default_flow_style=False)
        f.write("---\n")
        f.write(body)

# --- THE TEST SUITE ---
def run_tests():
    print("Initializing Test Environment...\n")
    
    # Setup: Create an initial OKF file
    initial_file = os.path.join(TEST_DIR, "test_framework.md")
    initial_metadata = {
        "status": "active",
        "confidence": 0.8,
        "subject": "backend",
        "predicate": "uses_framework",
        "object": "Flask",
        "source": {"turn_ids": ["turn_1"]}
    }
    _write_okf_file(initial_file, initial_metadata, "# We use Flask")

    # TEST 1: Reinforcement
    print("Running Test 1: Reinforcing an existing fact...")
    reinforce_candidate = {
        "subject": "backend", "predicate": "uses_framework", "object": "Flask",
        "evidence": {"turn_ids": ["turn_5"]}, "created_at": "2026-07-09T20:00:00Z"
    }
    result = reconcile_memory_candidate(reinforce_candidate)
    
    # Read back to verify
    with open(initial_file, "r") as f:
        content = f.read()
        meta = yaml.safe_load(content.split("---")[1])
        print(f"Result: {result} | New Confidence: {meta['confidence']} | Turns: {meta['source']['turn_ids']}")
        assert result == "REINFORCED", "Failed to reinforce"
        assert meta["confidence"] == 0.85, "Confidence did not increment correctly"
        assert "turn_5" in meta["source"]["turn_ids"], "Failed to append new turn_id"

    # TEST 2: Contradiction
    print("\nRunning Test 2: Contradicting a fact (changing to FastAPI)...")
    contradict_candidate = {
        "subject": "backend", "predicate": "uses_framework", "object": "FastAPI",
        "evidence": {"turn_ids": ["turn_10"]}, "created_at": "2026-07-09T20:05:00Z"
    }
    result = reconcile_memory_candidate(contradict_candidate)
    
    # Read back to verify old file was demoted
    with open(initial_file, "r") as f:
        meta = yaml.safe_load(f.read().split("---")[1])
        print(f"Result: {result} | Old File Status: {meta['status']} | Epistemic State: {meta['epistemic_state']}")
        assert result == "CREATED", "Failed to signal creation of new file"
        assert meta["status"] == "superseded", "Failed to demote old contradiction"
        
    print("\n✅ All OKF Reconciliation Tests Passed!")
    
    # Cleanup
    shutil.rmtree(TEST_DIR)

if __name__ == "__main__":
    run_tests()