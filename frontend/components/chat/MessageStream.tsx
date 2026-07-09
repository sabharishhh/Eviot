import { Bot } from "lucide-react";

export const MessageStream = ({ messages }) => {
  return (
    <div className="max-w-3xl mx-auto space-y-10 py-6">
      {messages.map((m, i) => (
        <div key={i} className="space-y-4">

          {/* User query — right-aligned blurple bubble, as in the reference chat */}
          <div className="flex justify-end">
            <div className="max-w-[75%] bg-indigo-500 text-white text-sm leading-relaxed px-4 py-2.5 rounded-2xl rounded-br-md shadow-md shadow-indigo-500/20">
              {m.query}
            </div>
          </div>

          {/* Answer — bot row with round avatar */}
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shrink-0 shadow-md shadow-indigo-500/25 mt-0.5">
              <Bot size={15} className="text-white" />
            </div>
            <div className="flex-1 bg-[#151823] border border-white/5 rounded-2xl rounded-tl-md px-4 py-3">
              <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
                {m.answer}
              </div>

              {/* Source context — nested card, kept inside the answer bubble */}
              {m.context_sentences && m.context_sentences.length > 0 && (
                <div className="mt-3 bg-[#0F1118] border border-white/5 rounded-xl p-3.5">
                  <h4 className="text-[10px] uppercase tracking-[0.18em] text-slate-500 font-semibold mb-2 flex items-center gap-1.5">
                    <span className="w-1 h-1 rounded-full bg-indigo-400" />
                    Source Context
                  </h4>
                  <ul className="space-y-1.5 text-xs text-slate-400 leading-relaxed">
                    {m.context_sentences.map((ctx, idx) => (
                      <li key={idx} className="flex gap-2">
                        <span className="text-indigo-400 shrink-0 font-semibold">{idx + 1}.</span>
                        <span>{ctx}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

        </div>
      ))}
    </div>
  );
};