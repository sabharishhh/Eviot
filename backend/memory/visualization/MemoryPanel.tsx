"use client";

import React, { useEffect, useState } from "react";
import { Activity, Save } from "lucide-react";

export default function MemoryPanel() {
  const [memories, setMemories] = useState<any[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [activeFile, setActiveFile] = useState<string | null>(
    null,
  );
  const [editorContent, setEditorContent] =
    useState<string>("");

  const fetchState = async () => {
    const res = await fetch(
      "http://localhost:8000/memory/inspect",
    );

    const data = await res.json();

    setMemories(data.memories);
    setLogs(data.logs);
  };

  useEffect(() => {
    fetchState();
  }, []);

  const handleSelectFile = (memory: any) => {
    setActiveFile(memory.file_name);

    // Combine frontmatter and body for full free-text control
    const fullText = `---
${JSON.stringify(memory.metadata, null, 2)}
---

${memory.body}`;

    setEditorContent(fullText);
  };

  const handleSave = async () => {
    if (!activeFile) return;

    await fetch(
      "http://localhost:8000/memory/update",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          file_name: activeFile,
          new_content: editorContent,
        }),
      },
    );

    // Refresh logs to show the manual edit
    fetchState();
  };

  return (
    <div className="flex h-full flex-col border-l border-slate-700 bg-slate-900 text-slate-200">
      {/* Top Split: Memory Files and Free-Text Editor */}
      <div className="flex flex-1 overflow-hidden border-b border-slate-700">
        {/* Left Column: File List */}
        <div className="w-1/3 overflow-y-auto border-r border-slate-700 p-4">
          <h3 className="mb-4 text-sm font-bold uppercase tracking-wider text-slate-400">
            Compiled Brain
          </h3>

          {memories.map((memory, index) => {
            const isActive =
              activeFile === memory.file_name;

            return (
              <button
                key={index}
                type="button"
                onClick={() =>
                  handleSelectFile(memory)
                }
                className={`mb-2 w-full rounded-lg p-3 text-left transition-colors ${
                  isActive
                    ? "bg-[#e8e8e8] text-[#181818]"
                    : "bg-slate-800 text-slate-200 hover:bg-slate-700"
                }`}
              >
                <div className="truncate text-sm font-semibold">
                  {memory.metadata.subject}
                </div>

                <div
                  className={`mt-1 truncate text-xs ${
                    isActive
                      ? "text-[#5f5f5f]"
                      : "text-slate-400"
                  }`}
                >
                  {memory.metadata.predicate}{" "}
                  {memory.metadata.object}
                </div>
              </button>
            );
          })}
        </div>

        {/* Right Column: Free-Text Editor */}
        <div className="flex w-2/3 flex-col bg-slate-950 p-4">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">
              File Editor
            </h3>

            <button
              type="button"
              onClick={handleSave}
              disabled={!activeFile}
              className="flex items-center space-x-2 rounded bg-[#e8e8e8] px-3 py-1.5 text-sm text-[#181818] transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Save size={14} />

              <span>Save Changes</span>
            </button>
          </div>

          <textarea
            className="flex-1 w-full resize-none rounded-lg border border-slate-700 bg-slate-900 p-4 font-mono text-sm text-slate-200 outline-none transition-colors placeholder:text-slate-500 focus:border-[#b4b4b4] disabled:cursor-not-allowed disabled:opacity-60"
            value={editorContent}
            onChange={(e) =>
              setEditorContent(e.target.value)
            }
            disabled={!activeFile}
            placeholder="Select a memory file to edit the raw OKF structure..."
          />
        </div>
      </div>

      {/* Bottom Split: Activity Log */}
      <div className="flex h-48 flex-col bg-slate-950">
        <div className="flex items-center space-x-2 border-b border-slate-800 p-2 text-slate-400">
          <Activity size={14} />

          <span className="text-xs font-bold uppercase tracking-wider">
            Brain Activity Log
          </span>
        </div>

        <div className="flex-1 space-y-1 overflow-y-auto p-4 font-mono text-xs text-emerald-400/80">
          {logs.map((log, index) => (
            <div key={index}>{log.trim()}</div>
          ))}
        </div>
      </div>
    </div>
  );
}