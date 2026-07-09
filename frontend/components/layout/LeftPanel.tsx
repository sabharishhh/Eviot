"use client";
import { useEffect, useState } from "react";
import DocumentUpload from "../input/DocumentUpload";
import { SessionState, AppMode, QueryParams, DemoScenario } from "@/lib/types";
import { getDemoScenarios, loadDemoScenario } from "@/lib/api";
import { Play, Beaker, ChevronDown } from "lucide-react";

/* ------------------------------------------------------------------
   Design tokens (shared across the restyled UI)
   bg base     #0A0C12   panel  #0F1118   card  #151823   raised #1A1E2B
   border      white/5   accent #6366F1 (blurple)          text  slate-200
   Cards: rounded-2xl · Buttons/badges: rounded-full pills
------------------------------------------------------------------- */

interface Props {
  session: SessionState;
  onSessionUpdate: (s: SessionState) => void;
  query: string;
  onQueryChange: (q: string) => void;
  mode: AppMode;
  onRun: () => void;
  isRunning: boolean;
}

export default function LeftPanel({ session, onSessionUpdate, query, onQueryChange, mode, onRun, isRunning }: Props) {
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [loadingDemo, setLoadingDemo] = useState(false);

  useEffect(() => {
    getDemoScenarios().then(res => setScenarios(res.scenarios)).catch(console.error);
  }, []);

  const handleLoadDemo = async (id: string) => {
    const sc = scenarios.find(s => s.id === id);
    if (!sc) return;
    setLoadingDemo(true);
    try {
      const res = await loadDemoScenario(id);
      onSessionUpdate({ sessionId: res.session_id, documents: res.documents, totalSentences: res.total_sentences });
      onQueryChange(sc.query);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDemo(false);
    }
  };

  return (
    <aside className="w-[35%] min-w-[320px] max-w-[450px] h-full bg-[#0F1118] border-r border-white/5 flex flex-col overflow-y-auto">

      {/* Brand header — mirrors the reference's compact top identity row */}
      <div className="flex items-center gap-3 px-6 pt-6 pb-4">
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white font-bold text-sm shadow-lg shadow-indigo-500/25">
          E
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold text-slate-100">Eviot</p>
          <p className="text-[11px] text-slate-500">OT context engine</p>
        </div>
      </div>

      <div className="px-6 pb-6 flex flex-col gap-5 flex-1">

        {/* Quick Start Demos */}
        <section className="bg-[#151823] border border-white/5 rounded-2xl p-4 flex flex-col gap-3">
          <label className="text-[10px] font-semibold text-slate-500 uppercase tracking-[0.18em] flex items-center gap-2">
            <Beaker size={13} className="text-indigo-400" /> Quick Start Demos
          </label>
          <div className="relative">
            <select
              className="w-full appearance-none bg-[#1A1E2B] border border-white/5 text-slate-200 text-sm rounded-full pl-4 pr-10 py-2.5 outline-none focus:border-indigo-500/60 focus:ring-2 focus:ring-indigo-500/20 transition-all cursor-pointer disabled:opacity-50"
              onChange={(e) => handleLoadDemo(e.target.value)}
              defaultValue=""
              disabled={loadingDemo || isRunning}
            >
              <option value="" disabled>Select a research scenario…</option>
              {scenarios.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}
            </select>
            <ChevronDown size={15} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
          </div>
        </section>

        {/* Document upload */}
        <section className="bg-[#151823] border border-white/5 rounded-2xl p-4">
          <DocumentUpload session={session} onSessionUpdate={onSessionUpdate} />
        </section>

        {/* Prompt */}
        <section className="bg-[#151823] border border-white/5 rounded-2xl p-4 flex flex-col gap-3 flex-1">
          <label className="text-[10px] font-semibold text-slate-500 uppercase tracking-[0.18em]">
            User Prompt
          </label>
          <textarea
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Ask something across your documents…"
            className="flex-1 bg-[#1A1E2B] border border-white/5 rounded-2xl p-4 text-sm text-slate-200 placeholder:text-slate-600 outline-none focus:border-indigo-500/60 focus:ring-2 focus:ring-indigo-500/20 transition-all resize-none min-h-[150px] leading-relaxed"
          />
        </section>

        {/* Run — pill CTA with reference-style glow */}
        <button
          onClick={onRun}
          disabled={isRunning || !query.trim() || !session.sessionId}
          className={`w-full py-3 rounded-full font-semibold text-sm flex justify-center items-center gap-2 transition-all
            ${isRunning || !query.trim() || !session.sessionId
              ? "bg-[#1A1E2B] text-slate-600 cursor-not-allowed border border-white/5"
              : "bg-indigo-500 hover:bg-indigo-400 active:scale-[0.99] text-white shadow-lg shadow-indigo-500/30"}`}
        >
          {isRunning ? (
            <>
              <span className="w-2 h-2 rounded-full bg-white/80 animate-pulse" />
              Running Optimal Transport…
            </>
          ) : (
            <><Play size={15} fill="currentColor" /> Run</>
          )}
        </button>
      </div>
    </aside>
  );
}