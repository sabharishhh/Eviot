'use client';

import React, { useState, useEffect } from 'react';
import {
  Save,
  Activity,
  Database,
  FileText,
  Network,
  Code,
  Trash2,
} from 'lucide-react';

import dynamic from 'next/dynamic';

const KnowledgeGraph = dynamic(() => import('./KnowledgeGraph'), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full flex items-center justify-center text-zinc-500">
      Loading Graph...
    </div>
  ),
});

export default function MemoryPanel() {
  const [memories, setMemories] = useState<any[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [editorContent, setEditorContent] = useState<string>('');
  const [isSaving, setIsSaving] = useState(false);
  const [deletingFile, setDeletingFile] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'editor' | 'graph'>('graph');

  const fetchState = async () => {
    try {
      const res = await fetch('http://localhost:8000/memory/inspect');

      if (res.ok) {
        const data = await res.json();

        setMemories(data.memories || []);
        setLogs(data.logs || []);
      }
    } catch (error) {
      console.error('Failed to fetch memory state:', error);
    }
  };

  useEffect(() => {
    fetchState();

    const interval = setInterval(fetchState, 3000);

    return () => clearInterval(interval);
  }, []);

  const handleSelectFile = (memory: any) => {
    setActiveFile(memory.file_name);

    const fullText = `---\n${JSON.stringify(
      memory.metadata,
      null,
      2
    )}\n---\n\n${memory.body}`;

    setEditorContent(fullText);
    setViewMode('editor');
  };

  const handleSave = async () => {
    if (!activeFile) return;

    setIsSaving(true);

    try {
      const res = await fetch(
        'http://localhost:8000/memory/update',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            file_name: activeFile,
            new_content: editorContent,
          }),
        }
      );

      if (!res.ok) {
        const data = await res.json().catch(() => null);

        throw new Error(
          data?.detail || 'Failed to save memory'
        );
      }

      await fetchState();
    } catch (error) {
      console.error('Failed to save memory:', error);

      alert(
        error instanceof Error
          ? error.message
          : 'Failed to save memory'
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (
    event: React.MouseEvent<HTMLButtonElement>,
    fileName: string
  ) => {
    event.stopPropagation();

    const confirmed = window.confirm(
      `Delete "${fileName}" permanently?\n\nThis action cannot be undone.`
    );

    if (!confirmed) return;

    setDeletingFile(fileName);

    try {
      const res = await fetch(
        `http://localhost:8000/memory/${encodeURIComponent(fileName)}`,
        {
          method: 'DELETE',
        }
      );

      if (!res.ok) {
        const data = await res.json().catch(() => null);

        throw new Error(
          data?.detail || 'Failed to delete memory'
        );
      }

      /*
       * If the deleted file is currently open,
       * clear the editor and return to graph view.
       */
      if (activeFile === fileName) {
        setActiveFile(null);
        setEditorContent('');
        setViewMode('graph');
      }

      await fetchState();
    } catch (error) {
      console.error('Failed to delete memory:', error);

      alert(
        error instanceof Error
          ? error.message
          : 'Failed to delete memory'
      );
    } finally {
      setDeletingFile(null);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#0F0F0F] text-zinc-200">
      {/* Top Split */}
      <div className="flex flex-1 overflow-hidden border-b border-white/[0.08]">
        {/* Left Column: File List */}
        <div className="w-1/3 overflow-y-auto border-r border-white/[0.08] p-4 custom-scrollbar bg-[#141414]">
          <h3 className="text-[11px] font-bold text-zinc-200 mb-4 uppercase tracking-widest flex items-center gap-2">
            <Database size={14} />
            Compiled Brain
          </h3>

          {memories.length === 0 ? (
            <p className="text-xs text-zinc-500 italic">
              No persistent memory files found yet.
            </p>
          ) : (
            memories.map((memory) => {
              const isActive =
                activeFile === memory.file_name &&
                viewMode === 'editor';

              const isDeleting =
                deletingFile === memory.file_name;

              return (
                <div
                  key={memory.file_name}
                  onClick={() => {
                    if (!isDeleting) {
                      handleSelectFile(memory);
                    }
                  }}
                  className={`group w-full text-left p-3 mb-2 rounded-lg transition-all border cursor-pointer ${
                    isActive
                      ? 'bg-zinc-800/80 border-zinc-600 shadow-sm'
                      : 'bg-[#1e1e1e] border-transparent hover:bg-zinc-800/50'
                  } ${
                    isDeleting
                      ? 'opacity-50 pointer-events-none'
                      : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    {/* Memory Information */}
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                        <FileText
                          size={14}
                          className="text-zinc-400 shrink-0"
                        />

                        <span className="truncate">
                          {memory.metadata?.subject || 'Unknown'}
                        </span>
                      </div>

                      <div className="text-[11px] text-zinc-400 truncate mt-1.5 font-mono">
                        {memory.metadata?.predicate}{' '}
                        {memory.metadata?.object}
                      </div>
                    </div>

                    {/* Delete Button */}
                    <button
                      type="button"
                      onClick={(event) =>
                        handleDelete(
                          event,
                          memory.file_name
                        )
                      }
                      disabled={isDeleting}
                      className="
                        shrink-0
                        p-1.5
                        rounded-md
                        text-zinc-600
                        opacity-0
                        group-hover:opacity-100
                        hover:text-red-400
                        hover:bg-red-500/10
                        focus:opacity-100
                        focus:outline-none
                        focus:ring-1
                        focus:ring-red-500/40
                        disabled:opacity-50
                        transition-all
                      "
                      title="Delete memory"
                      aria-label={`Delete ${memory.file_name}`}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right Column: Dynamic Workspace */}
        <div className="w-2/3 p-4 flex flex-col bg-[#1A1A1A]">
          <div className="flex justify-between items-center mb-4">
            {/* View Toggles */}
            <div className="flex space-x-1 bg-black/40 p-1 rounded-lg border border-white/[0.05]">
              <button
                onClick={() => setViewMode('editor')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-[11px] font-bold uppercase tracking-widest transition-colors ${
                  viewMode === 'editor'
                    ? 'bg-[#e8e8e8] text-[#111111] shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-100'
                }`}
              >
                <Code size={14} />
                <span>EDIT</span>
              </button>
              <button
                onClick={() => setViewMode('graph')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-[11px] font-bold uppercase tracking-widest transition-colors ${
                  viewMode === 'graph'
                    ? 'bg-[#e8e8e8] text-[#111111] shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-100'
                }`}
              >
                <Network size={14} />
                <span>View</span>
              </button>

              
            </div>

            {/* Save Button */}
            {viewMode === 'editor' && (
              <button
                onClick={handleSave}
                disabled={!activeFile || isSaving}
                className="flex items-center space-x-2 bg-white text-black hover:bg-zinc-100 disabled:opacity-50 px-3 py-1.5 rounded-full text-xs font-semibold transition-all"
              >
                <Save size={14} />

                <span>
                  {isSaving
                    ? 'Saving...'
                    : 'Save Changes'}
                </span>
              </button>
            )}
          </div>

          {/* Workspace Content */}
          <div className="flex-1 overflow-hidden relative">
            {viewMode === 'graph' ? (
              <KnowledgeGraph memories={memories} />
            ) : (
              <textarea
                className="absolute inset-0 w-full h-full bg-[#111111] border border-white/[0.08] rounded-xl p-4 font-mono text-[13px] leading-relaxed resize-none focus:outline-none focus:border-zinc-400/50 text-zinc-200 custom-scrollbar shadow-inner"
                value={editorContent}
                onChange={(event) =>
                  setEditorContent(event.target.value)
                }
                disabled={!activeFile}
                placeholder="Select a memory file from the left to edit the raw OKF structure..."
              />
            )}
          </div>
        </div>
      </div>

      {/* Bottom Split: Activity Log */}
      <div className="h-48 flex flex-col bg-[#0A0A0A]">
        <div className="px-4 py-3 border-b border-white/[0.08] flex items-center space-x-2 text-zinc-200 bg-[#111111]">
          <Activity size={14} />

          <span className="text-[10px] font-bold uppercase tracking-widest">
            System Activity Log
          </span>
        </div>

        <div className="flex-1 p-4 overflow-y-auto font-mono text-[11px] text-amber-400/80 space-y-1.5 custom-scrollbar leading-relaxed">
          {logs.length === 0 ? (
            <div className="text-zinc-500">
              Waiting for memory operations...
            </div>
          ) : (
            logs.map((log, index) => (
              <div
                key={index}
                className="whitespace-pre-wrap"
              >
                {log.trim()}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}