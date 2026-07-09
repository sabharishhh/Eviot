"use client";
import { Bot, AlertTriangle } from "lucide-react";

interface Props {
  answer: string;
  status?: string;   // aligned with RightPanel: "idle" | "running" | "streaming" | "done" | "error"
  error?: string;
}

export default function AnswerPanel({ answer, status, error }: Props) {
  const isStreaming = status === "running" || status === "streaming";

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/20 rounded-2xl p-5 flex items-start gap-3">
        <AlertTriangle size={16} className="text-red-400 mt-0.5 shrink-0" />
        <p className="text-sm text-red-200/90 leading-relaxed">{error}</p>
      </div>
    );
  }

  if (!answer && !isStreaming) {
    return (
      <div className="h-full min-h-[120px] flex items-center justify-center">
        <p className="text-sm text-slate-600">Run a query to generate a grounded answer.</p>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      {/* Bot avatar — round, blurple, like the reference's profile chips */}
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shrink-0 shadow-md shadow-indigo-500/25 mt-0.5">
        <Bot size={15} className="text-white" />
      </div>

      {/* Message bubble */}
      <div className="flex-1 bg-[#151823] border border-white/5 rounded-2xl rounded-tl-md p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-semibold text-indigo-300">Eviot</span>
          {isStreaming && <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />}
        </div>
        <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
          {answer}
          {isStreaming && (
            <span className="inline-block w-1.5 h-4 ml-1 bg-indigo-400 animate-pulse align-middle rounded-sm" />
          )}
        </div>
      </div>
    </div>
  );
}