"use client";
import MarginalGainCurve from "../visualization/MarginalGainCurve";
import CoverageGauge from "../visualization/CoverageGauge";
import ContextLog from "../visualization/ContextLog";
import AnswerPanel from "../answer/AnswerPanel";
import { QueryState, QueryParams, ComparisonResult } from "@/lib/types";

interface Props {
  queryState: QueryState;
  comparison: ComparisonResult | null;
  showComparison: boolean;
  onRequestComparison: () => void;
  params: QueryParams;
}

export default function RightPanel({ queryState, showComparison, onRequestComparison, params }: Props) {
  const isIdle = queryState.status === "idle";

  if (isIdle) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-500 p-10 text-center">
        <div className="w-16 h-16 rounded-full bg-slate-800/50 flex items-center justify-center mb-4">
          <span className="text-2xl font-mono opacity-50">OT</span>
        </div>
        <h2 className="text-xl font-semibold text-slate-300 mb-2">Awaiting Query</h2>
        <p className="max-w-md text-sm leading-relaxed">
          Upload documents and submit a query. MakeSense will dynamically construct a 
          semantically sufficient context set in real-time.
        </p>
      </div>
    );
  }

  // Current coverage percentage based on the latest step or saturation event
  const currentCoverage = queryState.saturation 
    ? queryState.saturation.final_coverage_pct 
    : (queryState.steps[queryState.steps.length - 1]?.coverage_pct || 0);

  return (
    <div className="flex-1 bg-[#0f1117] p-6 flex flex-col gap-6 overflow-y-auto">
      
      {/* Top Visualizations Row */}
      <div className="flex gap-6 h-[240px]">
        <div className="flex-1 min-w-0">
          <MarginalGainCurve 
            steps={queryState.steps} 
            saturation={queryState.saturation} 
            epsilon={params.epsilon} 
          />
        </div>
        <div className="w-[180px] shrink-0">
          <CoverageGauge coverage={currentCoverage} />
        </div>
      </div>

      {/* Middle Context Log */}
      <div className="flex-1 min-h-[250px] bg-[#1a1d27] border border-slate-800 rounded-xl p-4 flex flex-col">
        <div className="flex justify-between items-center mb-3">
          <span className="text-xs text-slate-400 font-mono uppercase tracking-wider">
            Context Selection Trace
          </span>
          <span className="text-xs text-slate-500 font-mono">
            {queryState.steps.length} sentences retrieved
          </span>
        </div>
        <div className="flex-1 overflow-hidden">
          <ContextLog steps={queryState.steps} />
        </div>
      </div>

      {/* Answer Panel */}
      <AnswerPanel 
        answer={queryState.answerTokens.join("")} 
        isStreaming={queryState.status === "answering"} 
      />
    </div>
  );
}