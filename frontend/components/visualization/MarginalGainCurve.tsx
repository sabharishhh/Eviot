"use client";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Label
} from "recharts";
import { motion, AnimatePresence } from "framer-motion";
import { SelectionStepEvent, SaturationEvent } from "@/lib/types";

interface Props {
  steps: SelectionStepEvent[];
  saturation: SaturationEvent | null;
  epsilon: number;
}

export default function MarginalGainCurve({ steps, saturation, epsilon }: Props) {
  const data = steps.map((s) => ({
    step: s.step,
    gain: s.marginal_gain,
    cost: s.ot_cost,
  }));

  const hasSaturated = saturation !== null;

  return (
    <div className="relative w-full h-56 bg-[#1a1d27] rounded-xl p-4 border border-slate-800 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs text-slate-400 font-mono uppercase tracking-wider">
          Marginal Semantic Gain (Δt)
        </span>
        <AnimatePresence>
          {hasSaturated && (
            <motion.span
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-xs font-semibold text-amber-400 bg-amber-400/10 
                         px-3 py-1 rounded-full border border-amber-400/30 flex items-center gap-2"
            >
              <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
              Semantic Saturation Reached
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      {/* We must specify a height for Recharts to render properly */}
      <div className="w-full h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 24, bottom: 4, left: -16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2d3148" vertical={false} />
            <XAxis
              dataKey="step"
              stroke="#475569"
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              stroke="#475569"
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              domain={['auto', 'auto']}
            />
            <Tooltip
              contentStyle={{ background: "#1e2130", border: "1px solid #334155", borderRadius: 8, color: "#f8fafc" }}
              itemStyle={{ color: "#22d3ee", fontWeight: "bold" }}
              labelStyle={{ color: "#94a3b8", marginBottom: 4 }}
              formatter={(v: number) => [v.toFixed(4), "Gain"]}
              labelFormatter={(l) => `Selection Step ${l}`}
            />
            <ReferenceLine
              y={epsilon}
              stroke="#f59e0b"
              strokeDasharray="4 4"
            >
              <Label value={`ε = ${epsilon}`} fill="#f59e0b" fontSize={11} position="insideTopRight" offset={10} />
            </ReferenceLine>
            <Line
              type="monotone"
              dataKey="gain"
              stroke="#22d3ee"
              strokeWidth={3}
              dot={{ fill: "#0f1117", stroke: "#22d3ee", strokeWidth: 2, r: 4 }}
              activeDot={{ r: 6, fill: "#22d3ee", stroke: "#0f1117", strokeWidth: 2 }}
              isAnimationActive={true}
              animationDuration={400}
              animationEasing="ease-out"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}