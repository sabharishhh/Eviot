import { useState, useCallback } from "react";
import { useSSE } from "./useSSE";
import { getComparisonResult } from "@/lib/api";
import {
  QueryState, SessionState, AppMode, QueryParams,
  SelectionStepEvent, SaturationEvent, ComparisonResult
} from "@/lib/types";

const INITIAL_QUERY_STATE: QueryState = {
  status: "idle",
  steps: [],
  saturation: null,
  answerTokens: [],
  answer: "",
  contextSentences: [],
};

export function useQueryRunner(session: SessionState) {
  const [queryState, setQueryState] = useState<QueryState>(INITIAL_QUERY_STATE);
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const { stream, cancel } = useSSE();

  const runQuery = useCallback(
    async (query: string, mode: AppMode, params: QueryParams, useDecomposition: boolean) => {
      if (!session.sessionId) return;

      setQueryState({ ...INITIAL_QUERY_STATE, status: "encoding" });
      setComparison(null);

      const payload = {
        session_id: session.sessionId,
        query,
        mode,
        use_decomposition: useDecomposition,
        params: {
          epsilon: params.epsilon,
          patience: params.patience,
          k_max: params.k_max,
          k: params.k,
        },
      };

      await stream(
        payload,
        (event) => {
          switch (event.type) {
            case "selection_step":
              // Transition from 'encoding' to 'selecting' on the first step
              setQueryState((s) => ({
                ...s,
                status: "selecting",
                steps: [...s.steps, event as SelectionStepEvent],
              }));
              break;
            case "saturation_reached":
              setQueryState((s) => ({
                ...s,
                saturation: event as SaturationEvent,
                status: "answering",
              }));
              break;
            case "llm_token":
              setQueryState((s) => ({
                ...s,
                answerTokens: [...s.answerTokens, event.token],
              }));
              break;
            case "answer_complete":
              setQueryState((s) => ({
                ...s,
                status: "complete",
                answer: event.answer,
                contextSentences: event.context_sentences,
              }));
              break;
          }
        },
        () => {}, // onComplete
        (e) => {
          setQueryState((s) => ({ ...s, status: "error" }));
          console.error("Stream error:", e);
        }
      );
    },
    [session.sessionId, stream]
  );

  const runComparison = useCallback(
    async (query: string) => {
      if (!session.sessionId || !queryState.saturation) return;
      
      // Use the exact number of sentences OT selected so the comparison is fair
      const k = queryState.saturation.total_sentences_selected;
      
      try {
        const result = await getComparisonResult(session.sessionId, query, k);
        setComparison(result);
      } catch (e) {
        console.error("Comparison failed", e);
      }
    },
    [session.sessionId, queryState.saturation]
  );

  const reset = useCallback(() => {
    cancel();
    setQueryState(INITIAL_QUERY_STATE);
    setComparison(null);
  }, [cancel]);

  return { queryState, comparison, runQuery, runComparison, reset };
}