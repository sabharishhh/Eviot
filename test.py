import requests
import json

FILE_PATH = r"C:\Users\tsabu\OneDrive\Desktop\makesense\backend\demo\data\bitcoin\consensus.txt"

# 1. Ingest the document
print("1. Ingesting document...")
with open(FILE_PATH, 'rb') as f:
    files = {'files': f}
    ingest_res = requests.post("http://localhost:8000/ingest", files=files)

if ingest_res.status_code != 200:
    print(f"Ingest failed: {ingest_res.text}")
    exit()

session_id = ingest_res.json()["session_id"]
print(f"✅ Ingested successfully. Session ID: {session_id}\n")

# 2. Run the Query Stream
print("2. Initiating Query Stream...")
payload = {
    "session_id": session_id,  
    "query": "How does Bitcoin achieve decentralized consensus?",
    "mode": "adaptive",
    "params": {"epsilon": 0.05, "patience": 2, "k_max": 12}
}

with requests.post("http://localhost:8000/query", json=payload, stream=True) as r:
    if r.status_code != 200:
        print(f"API Error ({r.status_code}): {r.text}")
        exit()

    for line in r.iter_lines():
        if line:
            data = line.decode().replace("data: ", "")
            try:
                event = json.loads(data)
                
                if event.get("type") == "selection_step":
                    print(f"Step {event['step']}: Selected line {event['source_line']} | Gain: {event['marginal_gain']}")
                elif event.get("type") == "saturation_reached":
                    print(f"\n--- SATURATION REACHED AT STEP {event['step']} ---\n")
                elif event.get("type") == "llm_token":
                    print(event.get("token", ""), end="", flush=True)
                elif event.get("type") == "answer_complete":
                    print("\n\n✅ Stream Finished!")
            except json.JSONDecodeError:
                print(f"\n[Could not parse JSON]: {data}")