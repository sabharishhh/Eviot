"use client";
import AnswerPanel from "../answer/AnswerPanel";
import ContextLog from "../visualization/ContextLog";
import { QueryState } from "@/lib/types";

interface Props {
  queryState: QueryState;
  comparison: any;
  showComparison: boolean;
  onRequestComparison: () => void;
  params: any;
}

export default function RightPanel({ queryState }: Props) {
  const isRunning = queryState.status === "running" || queryState.status === "streaming";

  return (
    <main className="flex-1 h-full bg-[#0A0C12] flex flex-col p-8 gap-6 overflow-y-auto">

      {/* Generated response */}
      <section className="flex flex-col min-h-[40%] bg-[#0F1118] border border-white/5 rounded-2xl p-6">
        <header className="flex items-center justify-between mb-4">
          <h3 className="text-[10px] font-semibold text-slate-500 uppercase tracking-[0.18em] flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
            Generated Response
          </h3>
          {isRunning && (
            <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
              Streaming
            </span>
          )}
        </header>
        <div className="flex-1 overflow-y-auto">
          <AnswerPanel
            status={queryState.status}
            answer={queryState.answer}
            error={queryState.error}
          />
        </div>
      </section>

      {/* Retrieved contexts */}
      <section className="flex flex-col min-h-[40%] bg-[#0F1118] border border-white/5 rounded-2xl p-6">
        <header className="flex items-center justify-between mb-4">
          <h3 className="text-[10px] font-semibold text-slate-500 uppercase tracking-[0.18em] flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
            Retrieved Semantic Contexts
          </h3>
          {queryState.steps?.length > 0 && (
            <span className="px-2.5 py-0.5 rounded-full bg-white/5 border border-white/5 text-slate-400 text-[10px] font-semibold tracking-wider">
              {queryState.steps.length} selected
            </span>
          )}
        </header>
        <div className="flex-1">
          <ContextLog steps={queryState.steps} />
        </div>
      </section>

    </main>
  );
}