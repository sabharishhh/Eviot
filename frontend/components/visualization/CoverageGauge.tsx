"use client";
import { motion } from "framer-motion";

interface Props {
  coverage: number;  // 0.0 to 1.0
}

export default function CoverageGauge({ coverage }: Props) {
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.min(Math.max(coverage, 0), 1);
  const offset = circumference * (1 - pct);
  const displayPct = Math.round(pct * 100);

  // Color logic based on coverage thresholds
  const strokeColor = pct > 0.85 ? "#22c55e" : pct > 0.5 ? "#22d3ee" : "#818cf8";

  return (
    <div className="flex flex-col items-center gap-2 bg-[#1a1d27] p-4 rounded-xl border border-slate-800 shadow-lg">
      <div className="relative">
        <svg width={100} height={100} viewBox="0 0 100 100" className="transform -rotate-90">
          {/* Background Track */}
          <circle 
            cx={50} cy={50} r={radius} 
            fill="none" stroke="#2d3148" strokeWidth={8} 
          />
          {/* Animated Progress */}
          <motion.circle
            cx={50} cy={50} r={radius} 
            fill="none"
            stroke={strokeColor}
            strokeWidth={8}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            animate={{ strokeDashoffset: offset, stroke: strokeColor }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          />
        </svg>
        
        {/* Center Percentage Text */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl font-bold font-mono text-slate-100">
            {displayPct}%
          </span>
        </div>
      </div>
      
      <div className="text-center">
        <span className="text-[10px] text-slate-400 font-mono uppercase tracking-wider block">
          Semantic
        </span>
        <span className="text-xs text-slate-300 font-semibold uppercase tracking-widest">
          Coverage
        </span>
      </div>
    </div>
  );
}