"use client";
import { useEffect, useState } from "react";
import DocumentUpload from "../input/DocumentUpload";
import { SessionState, AppMode, QueryParams, DemoScenario } from "@/lib/types";
import { getDemoScenarios, loadDemoScenario } from "@/lib/api";
import { Play, Beaker } from "lucide-react";

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
    <div className="w-[35%] min-w-[320px] max-w-[450px] h-full bg-[#0f1117] border-r border-slate-800 p-6 flex flex-col gap-6 overflow-y-auto">
      
      {/* Demo Selector */}
      <div className="flex flex-col gap-2">
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-widest flex items-center gap-2">
          <Beaker size={14} /> Quick Start Demos
        </label>
        <select 
          className="bg-[#1a1d27] border border-slate-700 text-slate-200 text-sm rounded-lg p-2.5 outline-none focus:border-indigo-500"
          onChange={(e) => handleLoadDemo(e.target.value)}
          defaultValue=""
          disabled={loadingDemo || isRunning}
        >
          <option value="" disabled>Select a research scenario...</option>
          {scenarios.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}
        </select>
      </div>

      <DocumentUpload session={session} onSessionUpdate={onSessionUpdate} />

      <div className="flex flex-col gap-2 flex-1">
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-widest">
          User Prompt
        </label>
        <textarea 
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Enter your prompt here..."
          className="flex-1 bg-[#1a1d27] border border-slate-700 rounded-xl p-4 text-sm text-slate-200 outline-none focus:border-indigo-500 resize-none min-h-[150px]"
        />
      </div>

      <button 
        onClick={onRun}
        disabled={isRunning || !query.trim() || !session.sessionId}
        className={`w-full py-3 rounded-xl font-bold flex justify-center items-center gap-2 transition-all
          ${isRunning || !query.trim() || !session.sessionId 
            ? "bg-slate-800 text-slate-500 cursor-not-allowed" 
            : "bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20"}`}
      >
        {isRunning ? "Running Optimal Transport..." : <><Play size={16} /> Run</>}
      </button>
    </div>
  );
}