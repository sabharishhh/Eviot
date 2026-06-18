"use client";
import { useState } from "react";
import LeftPanel from "@/components/layout/LeftPanel";
import RightPanel from "@/components/layout/RightPanel";
import { useQueryRunner } from "@/hooks/useQueryRunner";
import { SessionState, AppMode, QueryParams } from "@/lib/types";
import { BookOpen } from "lucide-react";

const DEFAULT_PARAMS: QueryParams = {
  epsilon: 0.05,
  patience: 2,
  k_max: 12,
  k: 5,
};

export default function Home() {
  const [session, setSession] = useState<SessionState>({
    sessionId: null,
    documents: [],
    totalSentences: 0,
  });

  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<AppMode>("adaptive");
  const [params, setParams] = useState<QueryParams>(DEFAULT_PARAMS);
  
  const { queryState, comparison, runQuery, runComparison, reset } = useQueryRunner(session);

  const handleRun = async () => {
    if (!query.trim() || !session.sessionId) return;
    reset();
    await runQuery(query, mode, params, true);
  };

  return (
    <div className="h-screen w-screen bg-[#0f1117] text-slate-100 flex flex-col font-sans overflow-hidden">
      
      {/* Sleek Top Navbar */}
      <div className="h-14 border-b border-slate-800 bg-[#12141c] flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-indigo-600 flex items-center justify-center font-bold text-white tracking-tighter">
            MS
          </div>
          <span className="font-bold text-lg tracking-tight">MakeSense</span>
          <span className="text-xs text-slate-500 font-mono ml-2 border border-slate-700 px-2 py-0.5 rounded-full">
            v1.0 • OT Research Preview
          </span>
        </div>
        <a 
          href="#" 
          className="flex items-center gap-2 text-sm text-slate-400 hover:text-indigo-400 transition-colors"
        >
          <BookOpen size={16} /> Read the Paper
        </a>
      </div>

      {/* Two-Panel Layout */}
      <div className="flex flex-1 overflow-hidden">
        <LeftPanel
          session={session}
          onSessionUpdate={setSession}
          query={query}
          onQueryChange={setQuery}
          mode={mode}
          onRun={handleRun}
          isRunning={["encoding", "selecting", "answering"].includes(queryState.status)}
        />
        <RightPanel
          queryState={queryState}
          comparison={comparison}
          showComparison={false}
          onRequestComparison={() => runComparison(query)}
          params={params}
        />
      </div>
    </div>
  );
}