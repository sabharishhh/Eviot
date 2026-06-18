export const MessageStream = ({ messages }) => {
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {messages.map((m, i) => (
        <div key={i} className="space-y-4">
          {/* User Query */}
          <div className="text-right text-sm text-slate-400">{m.query}</div>
          
          {/* Answer */}
          <div className="prose prose-invert text-sm leading-relaxed">
            {m.answer}
          </div>

          {/* Context Snippets */}
          {m.context_sentences && (
            <div className="bg-[#161b22] border border-slate-800 rounded-lg p-4">
              <h4 className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">Source Context</h4>
              <ul className="space-y-2 text-xs text-slate-400">
                {m.context_sentences.map((ctx, idx) => (
                  <li key={idx} className="flex gap-2">
                    <span className="text-indigo-500">•</span> {ctx}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};