import os
import asyncio
from backend.session import ConversationTurn
from backend.memory.extractor import extract_memory_candidates
from backend.memory.okf_writer import write_okf_memory
from backend.memory.loader import load_okf_memories

async def test_pipeline():
    print("🚀 Starting OKF Memory Architecture Component Test...\n")
    
    # 1. Mock a completed turn where a user makes a definitive decision
    mock_turn = ConversationTurn(
        turn_index=1,
        original_query="I want to use framer-motion for animations because it handles layout changes smoothly.",
        resolved_query="I want to use framer-motion for animations because it handles layout changes smoothly.",
        retrieved_sentence_ids=[],
        answer="Got it. We will use framer-motion for handling smooth layout animations."
    )
    
    # 2. Test Stage: Extraction
    print("1️⃣ Testing LLM Candidate Extraction...")
    candidates_json = extract_memory_candidates(mock_turn, session_id="test_session_99")
    print(f"   Extracted JSON: {candidates_json}\n")
    
    if not candidates_json.get("candidates"):
        print("❌ Failed: No candidates extracted. Check your OPENAI_API_KEY.")
        return

    # 3. Test Stage: Disk Persistence
    print("2️⃣ Testing OKF Serialization & File Writing...")
    candidate = candidates_json["candidates"][0]
    write_okf_memory(candidate, session_id="test_session_99", turn_index=1)
    print("   ✅ Memory written to disk and logged in activity_log.txt.\n")
    
    # 4. Test Stage: Loader
    print("3️⃣ Testing OKF File Loading...")
    loaded_memories = load_okf_memories()
    print(f"   Found {len(loaded_memories)} active memory structures on disk.")
    
    match_found = any(m["metadata"].get("source", {}).get("session_id") == "test_session_99" for m in loaded_memories)
    if match_found:
        print("\n🎉 SUCCESS: The closed-loop architecture passes component validation!")
    else:
        print("\n❌ Failure: The file was written but could not be parsed back by the loader.")

if __name__ == "__main__":
    # Ensure environment is set up
    from dotenv import load_dotenv
    load_dotenv()
    
    asyncio.run(test_pipeline())