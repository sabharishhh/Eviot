import { useCallback, useRef } from "react";
import { SSEEvent } from "@/lib/types";

export function useSSE() {
  const controllerRef = useRef<AbortController | null>(null);

  const stream = useCallback(
    async (
      payload: object,
      onEvent: (event: SSEEvent) => void,
      onComplete: () => void,
      onError: (e: Error) => void
    ) => {
      // Cancel any in-progress stream
      controllerRef.current?.abort();
      controllerRef.current = new AbortController();
      const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

      try {
        const res = await fetch(`${BASE}/query`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          signal: controllerRef.current.signal,
        });

        if (!res.ok || !res.body) {
          throw new Error(`HTTP ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          // Keep the last partial chunk in the buffer
          buffer = lines.pop() ?? "";

          for (const chunk of lines) {
            const line = chunk.replace(/^data: /, "").trim();
            if (!line) continue;
            try {
              const parsed = JSON.parse(line) as SSEEvent;
              if (parsed.type === "stream_error") {
                // @ts-ignore
                onError(new Error(parsed.detail));
                return;
              }
              onEvent(parsed);
            } catch {
              // malformed event, skip
            }
          }
        }
        onComplete();
      } catch (e: unknown) {
        if ((e as Error).name !== "AbortError") {
          onError(e as Error);
        }
      }
    },
    []
  );

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  return { stream, cancel };
}