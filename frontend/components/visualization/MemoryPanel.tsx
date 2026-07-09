'use client';

import React, { useState, useEffect } from 'react';
import { Save, Activity, Database, FileText } from 'lucide-react';

export default function MemoryPanel() {
  const [memories, setMemories] = useState<any[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [editorContent, setEditorContent] = useState<string>('');
  const [isSaving, setIsSaving] = useState(false);

  const fetchState = async () => {
    try {
      const res = await fetch('http://localhost:8000/memory/inspect');
      if (res.ok) {
        const data = await res.json();
        setMemories(data.memories || []);
        setLogs(data.logs || []);
      }
    } catch (error) {
      console.error("Failed to fetch memory state:", error);
    }
  };

  useEffect(() => {
    fetchState();
    // Refresh periodically to catch background updates
    const interval = setInterval(fetchState, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectFile = (memory: any) => {
    setActiveFile(memory.file_name);
    // Combine frontmatter and body to give you full free-text control over the OKF format
    const fullText = `---\n${JSON.stringify(memory.metadata, null, 2)}\n---\n\n${memory.body}`;
    setEditorContent(fullText);
  };

  const handleSave = async () => {
    if (!activeFile) return;
    setIsSaving(true);
    
    try {
      await fetch('http://localhost:8000/memory/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_name: activeFile,
          new_content: editorContent
        })
      });
      await fetchState(); // Refresh logs to show the manual edit
    } catch (error) {
      console.error("Failed to save memory:", error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#0F0F0F] text-slate-200">
      
      {/* Top Split: Memory Files and Free-Text Editor */}
      <div className="flex flex-1 overflow-hidden border-b border-white/[0.08]">
        
        {/* Left Column: File List */}
        <div className="w-1/3 overflow-y-auto border-r border-white/[0.08] p-4 custom-scrollbar bg-[#141414]">
          <h3 className="text-[11px] font-bold text-slate-400 mb-4 uppercase tracking-widest flex items-center gap-2">
            <Database size={14} /> Compiled Brain
          </h3>
          {memories.length === 0 ? (
            <p className="text-xs text-slate-500 italic">No persistent memory files found yet.</p>
          ) : (
            memories.map((m, idx) => (
              <button 
                key={idx}
                onClick={() => handleSelectFile(m)}
                className={`w-full text-left p-3 mb-2 rounded-lg transition-colors border ${
                  activeFile === m.file_name 
                    ? 'bg-zinc-800/80 border-zinc-600 shadow-sm' 
                    : 'bg-[#1e1e1e] border-transparent hover:bg-zinc-800/50'
                }`}
              >
                <div className="text-sm font-semibold truncate text-zinc-200 flex items-center gap-2">
                  <FileText size={14} className="text-purple-400 shrink-0" />
                  {m.metadata.subject || 'Unknown'}
                </div>
                <div className="text-[11px] text-zinc-400 truncate mt-1.5 font-mono">
                  {m.metadata.predicate} {m.metadata.object}
                </div>
              </button>
            ))
          )}
        </div>

        {/* Right Column: Free Text Editor */}
        <div className="w-2/3 p-4 flex flex-col bg-[#1A1A1A]">
          <div className="flex justify-between items-center mb-4">
             <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">
               Memory Editor
             </h3>
             <button 
                onClick={handleSave}
                disabled={!activeFile || isSaving}
                className="flex items-center space-x-2 bg-white text-black hover:bg-zinc-200 disabled:opacity-50 px-3 py-1.5 rounded-full text-xs font-semibold transition-all"
             >
                <Save size={14} />
                <span>{isSaving ? 'Saving...' : 'Save Changes'}</span>
             </button>
          </div>
          <textarea 
            className="flex-1 w-full bg-[#111111] border border-white/[0.08] rounded-xl p-4 font-mono text-[13px] leading-relaxed resize-none focus:outline-none focus:border-purple-500/50 text-zinc-300 custom-scrollbar shadow-inner"
            value={editorContent}
            onChange={(e) => setEditorContent(e.target.value)}
            disabled={!activeFile}
            placeholder="Select a memory file from the left to edit the raw OKF structure..."
          />
        </div>
      </div>

      {/* Bottom Split: Activity Log */}
      <div className="h-48 flex flex-col bg-[#0A0A0A]">
        <div className="px-4 py-3 border-b border-white/[0.08] flex items-center space-x-2 text-slate-400 bg-[#111111]">
          <Activity size={14} />
          <span className="text-[10px] font-bold uppercase tracking-widest">Brain Activity Log</span>
        </div>
        <div className="flex-1 p-4 overflow-y-auto font-mono text-[11px] text-emerald-400/80 space-y-1.5 custom-scrollbar leading-relaxed">
          {logs.length === 0 ? (
            <div className="text-zinc-600">Waiting for memory operations...</div>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="whitespace-pre-wrap">{log.trim()}</div>
            ))
          )}
        </div>
      </div>

    </div>
  );
}