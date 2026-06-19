import { useState, useCallback } from "react";
import { SelectionStepEvent } from "@/lib/types";

// Add secondaryContext to your state definition
export interface QueryState {
  status: "idle" | "encoding" | "selecting" | "answering" | "done" | "error";
  steps: SelectionStepEvent[];
  answer: string;
  error?: string;
  secondaryContext?: string[];
}

export const useQueryRunner = (session: any) => {
  const [queryState, setQueryState] = useState<QueryState>({
    status: "idle",
    steps: [],
    answer: "",
    secondaryContext: [],
  });

  const [comparison, setComparison] = useState<any>(null);

  const reset = useCallback(() => {
    setQueryState({ status: "idle", steps: [], answer: "", secondaryContext: [] });
    setComparison(null);
  }, []);

  const runQuery = async (query: string, mode: string, params: any, useDecomp: boolean = true) => {
    setQueryState((prev) => ({ ...prev, status: "encoding", steps: [], answer: "", secondaryContext: [] }));

    try {
      const response = await fetch("http://localhost:8000/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: session.sessionId,
          query,
          mode,
          use_decomposition: useDecomp,
          params: {
            epsilon: params.epsilon,
            patience: params.patience,
            k_max: params.k_max,
            k: params.k,
          },
        }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let done = false;

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const payloadString = line.replace("data: ", "").trim();
                if (!payloadString) continue;

                const data = JSON.parse(payloadString);
                const eventType = data.type || data.event;

                if (eventType === "selection_step") {
                  setQueryState((prev) => ({
                    ...prev,
                    status: "selecting",
                    steps: [...prev.steps, data],
                  }));
                } else if (eventType === "saturation_reached") {
                  setQueryState((prev) => {
                    const tail = data.tail_truncated || 0;
                    const newSteps = tail > 0 && prev.steps.length > tail + 1 
                      ? prev.steps.slice(0, -tail) 
                      : prev.steps;
                    return { ...prev, steps: newSteps, status: "answering" };
                  });
                } else if (eventType === "llm_token") {
                  setQueryState((prev) => ({
                    ...prev,
                    status: "answering",
                    answer: prev.answer + data.token,
                  }));
                } else if (eventType === "answer_complete") {
                  // NEW: Catch the secondary sentences here!
                  setQueryState((prev) => ({
                    ...prev,
                    status: "done",
                    secondaryContext: data.secondary_context_sentences || [],
                  }));
                } else if (eventType === "stream_error") {
                  setQueryState((prev) => ({ ...prev, status: "error", error: data.detail }));
                }
              } catch (e) {
                console.error("Parse error:", line, e);
              }
            }
          }
        }
      }
    } catch (err: any) {
      setQueryState((prev) => ({ ...prev, status: "error", error: err.message }));
    }
  };

  const runComparison = async (query: string) => {
    // ... your existing comparison code ...
  };

  return { queryState, comparison, runQuery, runComparison, reset };
};