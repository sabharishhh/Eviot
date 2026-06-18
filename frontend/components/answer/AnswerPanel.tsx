"use client";
import { Bot } from "lucide-react";

interface Props {
  answer: string;
  isStreaming: boolean;
}

export default function AnswerPanel({ answer, isStreaming }: Props) {
  if (!answer && !isStreaming) return null;

  return (
    <div className="bg-[#1a1d27] border border-indigo-500/30 rounded-xl p-5 shadow-lg relative overflow-hidden">
      <div className="absolute top-0 left-0 w-1 h-full bg-indigo-500" />
      
      <div className="flex items-center gap-2 mb-3 text-indigo-400 font-semibold text-sm">
        <Bot size={18} />
        <span>LLM Response</span>
        {isStreaming && <span className="flex w-2 h-2 rounded-full bg-indigo-400 animate-pulse ml-2" />}
      </div>
      
      <div className="text-slate-200 text-sm leading-relaxed whitespace-pre-wrap font-sans">
        {answer}
        {isStreaming && <span className="inline-block w-1.5 h-4 ml-1 bg-indigo-400 animate-pulse align-middle" />}
      </div>
    </div>
  );
}