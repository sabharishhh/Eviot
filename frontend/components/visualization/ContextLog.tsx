"use client";
import { useState } from "react";
import { SelectionStepEvent } from "@/lib/types";
import { motion, AnimatePresence } from "framer-motion";
import { FileText, ChevronDown, ChevronUp } from "lucide-react";

interface Props {
  steps: SelectionStepEvent[];
}

function rowColor(gain: number, maxGain: number) {
  if (maxGain === 0) return "border-slate-800 bg-slate-800/20 text-slate-300";
  const ratio = gain / maxGain;
  if (ratio > 0.6) return "border-emerald-500/40 bg-emerald-500/10 text-emerald-100";
  if (ratio > 0.2) return "border-yellow-500/40 bg-yellow-500/10 text-yellow-100";
  return "border-amber-600/40 bg-amber-600/10 text-amber-100";
}

export default function ContextLog({ steps }: Props) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const maxGain = Math.max(...steps.map((s) => s.marginal_gain), 0);

  if (steps.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-slate-500 text-sm border border-dashed border-slate-800 rounded-xl p-8">
        Awaiting context construction...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 overflow-y-auto max-h-[400px] pr-2 custom-scrollbar">
      <AnimatePresence>
        {steps.map((step, i) => {
          const isExpanded = expanded === i;
          
          return (
            <motion.div
              key={step.step}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className={`rounded-lg border px-4 py-3 cursor-pointer transition-all hover:brightness-110 ${rowColor(step.marginal_gain, maxGain)}`}
              onClick={() => setExpanded(isExpanded ? null : i)}
            >
              <div className="flex items-start gap-3">
                <div className="flex items-center justify-center w-6 h-6 rounded-full bg-slate-900/50 text-xs font-mono font-bold shrink-0 mt-0.5">
                  {step.step}
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="text-sm line-clamp-2 leading-relaxed">
                    {step.sentence_text}
                  </div>
                </div>

                <div className="flex flex-col items-end gap-1 shrink-0 ml-4">
                  <span className="text-[11px] font-mono opacity-70 whitespace-nowrap">
                    Δ {step.marginal_gain.toFixed(3)}
                  </span>
                  {isExpanded ? <ChevronUp size={14} className="opacity-50" /> : <ChevronDown size={14} className="opacity-50" />}
                </div>
              </div>

              <AnimatePresence>
                {isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="mt-3 pt-3 border-t border-white/10 text-xs opacity-80 leading-relaxed">
                      <p className="mb-3">{step.sentence_text}</p>
                      <div className="flex flex-wrap gap-4 font-mono text-[10px] bg-slate-900/40 p-2 rounded">
                        <span className="flex items-center gap-1">
                          <FileText size={12} /> {step.source_doc}
                        </span>
                        <span>Line: {step.source_line}</span>
                        <span>Cost: {step.ot_cost.toFixed(4)}</span>
                        <span>Tokens: {step.cumulative_tokens}</span>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}