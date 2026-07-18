const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export async function ingestDocuments(files: File[]): Promise<{
    session_id: string;
    documents: Array<{ filename: string; num_sentences: number }>;
    total_sentences: number;
}> {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    const res = await fetch(`${BASE}/ingest`, { method: "POST", body: form });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

export async function getDemoScenarios(): Promise<{
    scenarios: DemoScenario[];
}> {
    const res = await fetch(`${BASE}/demo-scenarios`);
    if (!res.ok) throw new Error("Failed to load scenarios");
    return res.json();
}

export async function loadDemoScenario(id: string): Promise<{
    session_id: string;
    documents: Array<{ filename: string; num_sentences: number }>;
    total_sentences: number;
}> {
    const res = await fetch(`${BASE}/demo-scenarios/${id}/load`, {
        method: "POST",
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

export async function getComparisonResult(
    sessionId: string,
    query: string,
    k: number,
): Promise<ComparisonResult> {
    const res = await fetch(`${BASE}/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, query, k }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

export async function listSessions() {
  const res = await fetch(`${BASE}/sessions`);
  if (!res.ok) throw new Error(`Request failed with status ${res.status}`);
  return res.json(); // { sessions: SessionSummary[] }
}
 
export async function getSessionInfo(sessionId: string) {
  const res = await fetch(`${BASE}/session/${sessionId}/info`);
  if (!res.ok) throw new Error(`Request failed with status ${res.status}`);
  return res.json();
}
 
export async function deleteSession(sessionId: string) {
  const res = await fetch(`${BASE}/session/${sessionId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Request failed with status ${res.status}`);
  return res.json();
}
 