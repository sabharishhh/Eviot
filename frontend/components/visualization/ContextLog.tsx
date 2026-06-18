"use client";
import { SelectionStepEvent } from "@/lib/types";
import { motion, AnimatePresence } from "framer-motion";

interface Props {
  steps: SelectionStepEvent[];
}

export default function ContextLog({ steps }: Props) {
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
        {steps.map((step) => (
          <motion.div
            key={step.step}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="rounded-lg border px-4 py-3 border-slate-700 bg-[#161b22] text-slate-200 shadow-sm"
          >
            <div className="flex items-start gap-3">
              <div className="flex items-center justify-center w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 text-xs font-mono font-bold shrink-0 mt-0.5">
                {step.step}
              </div>
              
              <div className="flex-1 min-w-0">
                {/* Removed line-clamp so the full sentence is always visible */}
                <div className="text-sm leading-relaxed">
                  {step.sentence_text}
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}