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
  return (
    <div className="flex-1 h-full bg-[#0d1117] flex flex-col p-8 gap-8 overflow-y-auto">
      
      {/* Top Half: The Generated LLM Answer */}
      <div className="flex flex-col min-h-[40%] bg-[#12141c] border border-slate-800 rounded-xl p-6 shadow-sm">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-4 flex items-center gap-2">
          Generated Response
        </h3>
        <div className="flex-1 overflow-y-auto">
          <AnswerPanel 
            status={queryState.status} 
            answer={queryState.answer} 
            error={queryState.error} 
          />
        </div>
      </div>

      {/* Bottom Half: Clean Context Log */}
      <div className="flex flex-col min-h-[40%] bg-[#12141c] border border-slate-800 rounded-xl p-6 shadow-sm">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-4 flex items-center gap-2">
          Retrieved Semantic Contexts
        </h3>
        <div className="flex-1">
          <ContextLog steps={queryState.steps} />
        </div>
      </div>

    </div>
  );
}