"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { SessionState, ConversationTurn, SelectionStepEvent, QueryParams, AppMode } from "@/lib/types";
import { ingestDocuments, getDemoScenarios, loadDemoScenario } from "@/lib/api";
import {
  Send, FileText, File, X, Zap, Brain, Activity, BookOpen,
  Plus, RotateCcw, Loader2, AlertCircle, FilePlus, Image,
  FileCode, FileSpreadsheet, Hash, ChevronDown, ChevronUp, Settings,
  Menu, PanelLeftClose, PanelLeftOpen
} from "lucide-react";

const MAX_TURNS = 10;
const BASE = "http://localhost:8000";

const DEFAULT_PARAMS: QueryParams = { epsilon: 0.01, patience: 2, k_max: 12, k: 5 };

// ─── File type icon helper ───────────────────────────────────────────────────
function DocIcon({ filename, size = 13 }: { filename: string; size?: number }) {
  const ext = filename.split(".").pop()?.toLowerCase();
  const cls = `shrink-0`;
  if (ext === "pdf") return <FileText size={size} className={`${cls} text-red-400`} />;
  if (ext === "docx" || ext === "doc") return <FileText size={size} className={`${cls} text-blue-400`} />;
  if (ext === "md") return <Hash size={size} className={`${cls} text-purple-400`} />;
  return <File size={size} className={`${cls} text-slate-400`} />;
}

// ─── Turn Card ──────────────────────────────────────────────────────────────
// ─── Turn Card ──────────────────────────────────────────────────────────────
function TurnCard({ turn, isLast }: { turn: ConversationTurn; isLast: boolean }) {
  const [selectedSource, setSelectedSource] = useState<number | null>(null);

  return (
    <div className="flex flex-col gap-4 w-full animate-fade-in">

      {/* User query pill — shown first, right-aligned */}
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-gradient-to-r from-zinc-700 via-zinc-600 to-zinc-700 text-white rounded-2xl rounded-tr-none px-5 py-3 shadow-md animate-fade-in">
          <p className="text-[15px] leading-relaxed font-sans">{turn.query}</p>
          {turn.resolvedQuery && turn.resolvedQuery !== turn.query && (
            <p className="text-xs text-indigo-100/70 mt-1 italic font-sans">
              ↳ {turn.resolvedQuery}
            </p>
          )}
        </div>
      </div>

      {/* Answer content (Claude style - direct on canvas with an AI avatar) */}
      {(turn.answer || turn.isStreaming || turn.isRetrieving) && (
        <div className="flex gap-4 items-start w-full">
          {/* Assistant Avatar */}
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-zinc-400 to-zinc-200 flex items-center justify-center shadow-lg shrink-0 mt-1">
            <Brain size={16} className="text-white animate-pulse" />
          </div>

          {/* Response text & Citations */}
          <div className="flex-1 space-y-4">
            {turn.isRetrieving && turn.contextSteps.length === 0 ? (
              <div className="flex items-center gap-2 text-xs text-text-secondary py-2">
                <Loader2 size={12} className="text-accent animate-spin" />
                <span>Retrieving context chunks using Optimal Transport...</span>
              </div>
            ) : (
              <>
                {turn.answer && (
                  <p className="text-[15px] text-text-body leading-relaxed whitespace-pre-wrap font-sans">
                    {turn.answer}
                    {turn.isStreaming && (
                      <span className="inline-block w-1.5 h-4 ml-1 bg-accent animate-pulse align-middle" />
                    )}
                  </p>
                )}

                {/* Sources section */}
                {turn.contextSteps.length > 0 && (
                  <div className="pt-3 border-t border-border-default/40 mt-2">
                    <div className="flex items-center gap-1.5 mb-2">
                      <BookOpen size={12} className="text-text-tertiary" />
                      <span className="text-[10px] font-bold text-text-tertiary uppercase tracking-wider">
                        Retrieved Sources
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {turn.contextSteps.map((step, idx) => {
                        const docName = step.source_doc.split("/").pop() || step.source_doc;
                        const shortName = docName.length > 20 ? docName.slice(0, 18) + "..." : docName;
                        const isSelected = selectedSource === idx;

                        return (
                          <button
                            key={idx}
                            onClick={() => setSelectedSource(isSelected ? null : idx)}
                            className={`border text-[11px] rounded-md px-2.5 py-1 hover:border-accent hover:text-text-primary hover:bg-surface-3 transition-all cursor-pointer flex items-center gap-1.5 font-mono select-none ${isSelected
                              ? 'bg-surface-2 border-accent text-text-primary'
                              : 'bg-surface-2 border-border-default text-text-secondary'
                              }`}
                          >
                            <span className="w-3.5 h-3.5 rounded-full bg-accent/15 text-accent text-[9px] flex items-center justify-center font-bold">
                              {idx + 1}
                            </span>
                            <span>{shortName}</span>
                            <span className="text-text-tertiary">p.{step.source_line}</span>
                          </button>
                        );
                      })}
                    </div>

                    {/* Source context detail block */}
                    {selectedSource !== null && turn.contextSteps[selectedSource] && (
                      <div className="mt-3 p-3 rounded-lg bg-surface-2 border border-border-default text-xs text-text-body font-sans leading-relaxed animate-fade-in">
                        <div className="flex items-center justify-between border-b border-border-default pb-1.5 mb-2 font-mono text-[10px] text-text-secondary">
                          <span className="text-accent truncate">
                            {turn.contextSteps[selectedSource].source_doc} (p. {turn.contextSteps[selectedSource].source_line})
                          </span>
                        </div>
                        <p className="italic text-text-body">"{turn.contextSteps[selectedSource].sentence_text}"</p>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

    </div>
  );
}

// ─── Sidebar ─────────────────────────────────────────────────────────────────
function Sidebar({
  session, onSessionUpdate, onNewSession, isSidebarOpen
}: {
  session: SessionState;
  onSessionUpdate: (s: SessionState) => void;
  onNewSession: () => void;
  isSidebarOpen: boolean;
}) {
  const [isUploading, setIsUploading] = useState(false);
  const [scenarios, setScenarios] = useState<any[]>([]);
  const [loadingDemo, setLoadingDemo] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getDemoScenarios().then(r => setScenarios(r.scenarios)).catch(() => { });
  }, []);

  const handleFiles = async (files: File[]) => {
    if (!files.length) return;
    setIsUploading(true);
    try {
      const res = await ingestDocuments(files, session.sessionId);
      onSessionUpdate({
        sessionId: res.session_id,
        documents: [...session.documents, ...res.documents],
        totalSentences: res.total_sentences,
      });
    } catch (e) {
      console.error(e);
      alert("Upload failed. Ensure the backend is running.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadDemo = async (sc: any) => {
    setLoadingDemo(true);
    try {
      const res = await loadDemoScenario(sc.id);
      onSessionUpdate({ sessionId: res.session_id, documents: res.documents, totalSentences: res.total_sentences });
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDemo(false);
    }
  };

  return (
    <div className={`shrink-0 h-full flex flex-col bg-surface-1 border-r border-border-default transition-all duration-300 ${isSidebarOpen ? "w-56" : "w-14"}`}>

      {/* Logo */}
      {isSidebarOpen ? (
        <div className="px-4 py-4 flex items-center gap-2.5">
          <div className="w-6 h-6 rounded bg-accent flex items-center justify-center shrink-0">
            <div className="grid grid-cols-2 gap-0.5">
              {[0, 1, 2, 3].map(i => (
                <div key={i} className="w-1 h-1 rounded-sm bg-[#0F0F0F]" />
              ))}
            </div>
          </div>
          <div>
            <div className="font-bold text-base text-text-primary leading-none">Eviot</div>
            <div className="text-[11px] text-text-secondary mt-0.5">OT-powered RAG</div>
          </div>
        </div>
      ) : (
        <div className="py-4 flex justify-center">
          <div className="w-6 h-6 rounded bg-accent flex items-center justify-center shrink-0" title="Eviot OT RAG">
            <div className="grid grid-cols-2 gap-0.5">
              {[0, 1, 2, 3].map(i => (
                <div key={i} className="w-1 h-1 rounded-sm bg-[#0F0F0F]" />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* New Session button */}
      <div className="px-3 pb-4 flex justify-center w-full">
        {isSidebarOpen ? (
          <button
            onClick={onNewSession}
            className="w-full flex items-center justify-center gap-2 bg-accent hover:bg-accent-hover text-surface-0 text-sm font-semibold py-2.5 rounded-md transition-colors animate-fade-in"
          >
            <Plus size={13} />
            New Session
          </button>
        ) : (
          <button
            onClick={onNewSession}
            title="New Session"
            className="w-8 h-8 flex items-center justify-center bg-accent hover:bg-accent-hover text-surface-0 rounded-full transition-colors"
          >
            <Plus size={14} />
          </button>
        )}
      </div>

      {/* Documents section */}
      <div className="px-3 pb-2 flex flex-col">
        {isSidebarOpen ? (
          <>
            <p className="text-[10px] text-text-tertiary uppercase tracking-widest font-semibold mb-1.5 px-1">Documents</p>
            <div className="flex flex-col">
              {session.documents.length === 0 && (
                <div className="px-2 py-1.5 text-xs text-text-disabled italic">No documents loaded</div>
              )}
              {session.documents.map((doc, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-2 group transition-colors"
                >
                  <DocIcon filename={doc.filename} size={12} />
                  <span className="text-xs text-text-body truncate flex-1" title={doc.filename}>
                    {doc.filename.length > 18 ? doc.filename.slice(0, 16) + "…" : doc.filename}
                  </span>
                </div>
              ))}

              {/* Add Documents row */}
              <button
                onClick={() => fileRef.current?.click()}
                disabled={isUploading}
                className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-2 transition-colors text-left w-full mt-0.5"
              >
                {isUploading
                  ? <Loader2 size={12} className="text-accent animate-spin shrink-0" />
                  : <FilePlus size={12} className="text-text-secondary shrink-0" />
                }
                <span className="text-xs text-text-secondary">
                  {isUploading ? "Encoding…" : "Add Documents"}
                </span>
              </button>
            </div>
          </>
        ) : (
          <div className="flex flex-col gap-2 items-center">
            {session.documents.map((doc, i) => (
              <div key={i} className="p-1.5 rounded hover:bg-surface-2 transition-colors cursor-help" title={doc.filename}>
                <DocIcon filename={doc.filename} size={14} />
              </div>
            ))}
            <button
              onClick={() => fileRef.current?.click()}
              disabled={isUploading}
              title="Add Documents"
              className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-surface-2 transition-colors text-text-secondary"
            >
              {isUploading
                ? <Loader2 size={14} className="text-accent animate-spin" />
                : <FilePlus size={14} />
              }
            </button>
          </div>
        )}
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md,.docx"
          className="hidden"
          onChange={(e) => handleFiles(Array.from(e.target.files || []))}
        />
      </div>

      <div className="mx-3 h-px bg-border-default my-2" />

      {/* Quick Start section */}
      <div className="px-3 flex-1 overflow-y-auto custom-scrollbar flex flex-col">
        {isSidebarOpen ? (
          <>
            <p className="text-[10px] text-text-tertiary uppercase tracking-widest font-semibold mb-1.5 px-1">Quick Start</p>
            <div className="flex flex-col">
              {scenarios.map((sc) => (
                <button
                  key={sc.id}
                  onClick={() => handleLoadDemo(sc)}
                  disabled={loadingDemo}
                  className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-2 transition-colors text-left w-full group"
                >
                  <Activity size={12} className="text-text-secondary shrink-0 group-hover:text-accent transition-colors" />
                  <span className="text-xs text-text-body group-hover:text-text-primary transition-colors truncate">
                    {sc.title}
                  </span>
                </button>
              ))}
            </div>
          </>
        ) : (
          <div className="flex flex-col gap-2 items-center">
            {scenarios.map((sc) => (
              <button
                key={sc.id}
                onClick={() => handleLoadDemo(sc)}
                disabled={loadingDemo}
                title={sc.title}
                className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-surface-2 transition-colors text-text-secondary hover:text-accent"
              >
                <Activity size={14} />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-3 py-3 border-t border-border-default flex justify-center w-full">
        {isSidebarOpen ? (
          <button className="flex items-center gap-1.5 text-xs text-text-tertiary hover:text-text-secondary transition-colors w-full text-left">
            <Settings size={12} /> Settings
          </button>
        ) : (
          <button title="Settings" className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-surface-2 text-text-secondary hover:text-text-primary transition-colors">
            <Settings size={14} />
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Input Bar ────────────────────────────────────────────────────────────────
function InputBar({
  onSend, onFileAttach, disabled, placeholder, attachedFiles, onRemoveFile
}: {
  onSend: (text: string) => void;
  onFileAttach: (files: File[]) => void;
  disabled: boolean;
  placeholder: string;
  attachedFiles: File[];
  onRemoveFile: (i: number) => void;
}) {
  const [text, setText] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (!text.trim() && attachedFiles.length === 0) return;
    onSend(text.trim());
    setText("");
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col gap-2">
      {/* Attached files preview */}
      {attachedFiles.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-1 animate-fade-in">
          {attachedFiles.map((f, i) => (
            <div key={i} className="flex items-center gap-1.5 bg-surface-2 border border-border-default rounded-lg px-2.5 py-1">
              <DocIcon filename={f.name} size={11} />
              <span className="text-xs text-text-body max-w-[120px] truncate">{f.name}</span>
              <button onClick={() => onRemoveFile(i)} className="text-text-tertiary hover:text-text-primary ml-0.5 transition-colors">
                <X size={10} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input container pill */}
      <div className={`flex flex-col bg-surface-1 border border-border-default rounded-2xl px-4 py-3 shadow-2xl transition-all duration-200 focus-within:border-accent focus-within:ring-1 focus-within:ring-accent/30 ${disabled ? "opacity-50" : ""}`}>

        {/* Hidden file input */}
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md,.docx"
          className="hidden"
          onChange={(e) => {
            onFileAttach(Array.from(e.target.files || []));
            e.target.value = "";
          }}
        />

        {/* Textarea + button row */}
        <div className="flex items-end gap-2.5">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKey}
            disabled={disabled}
            placeholder={placeholder}
            rows={1}
            className="flex-1 bg-transparent text-[15px] text-text-body placeholder-text-disabled outline-none resize-none leading-relaxed max-h-36 overflow-y-auto custom-scrollbar disabled:opacity-50 py-1"
            style={{ scrollbarWidth: "thin" }}
          />

          <button
            onClick={handleSend}
            disabled={disabled || (!text.trim() && attachedFiles.length === 0)}
            className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-all mb-0.5 ${disabled || (!text.trim() && attachedFiles.length === 0)
              ? "bg-surface-3 text-text-disabled"
              : "bg-accent hover:bg-accent-hover text-surface-0 hover:scale-105"
              }`}
          >
            <Send size={13} className="ml-0.5" />
          </button>
        </div>
      </div>

      <p className="text-[11px] text-text-tertiary text-center">
        Eviot uses context retrieval. Verify outputs using the cited chunks.
      </p>
    </div>
  );
}

// ─── Empty state ──────────────────────────────────────────────────────────────
function EmptyState({
  hasSession,
  onSelectScenario,
  scenarios,
  loadingDemo
}: {
  hasSession: boolean;
  onSelectScenario: (sc: any) => void;
  scenarios: any[];
  loadingDemo: boolean;
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] max-w-2xl mx-auto px-4 gap-8 select-none my-auto">
      <div className="flex flex-col items-center text-center gap-3">
        <div className="w-14 h-14 rounded-full bg-gradient-to-tr from-zinc-400 to-zinc-200 flex items-center justify-center shadow-xl animate-pulse">
          <Brain size={28} className="text-white" />
        </div>
        <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-zinc-100 via-zinc-400 to-zinc-100 bg-clip-text text-transparent mt-2 pb-1">
          How can I help you today?
        </h1>
        <p className="text-sm text-text-secondary max-w-md leading-relaxed mt-1">
          {hasSession
            ? "Ask a question below. Eviot will retrieve semantically relevant context from your documents using Optimal Transport."
            : "Upload your documents in the sidebar to get started, then ask questions about them below."}
        </p>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function Home() {
  const [session, setSession] = useState<SessionState>({
    sessionId: null, documents: [], totalSentences: 0,
  });
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [scenarios, setScenarios] = useState<any[]>([]);
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  const turnsUsed = turns.filter(t => !t.isStreaming && !t.isRetrieving).length;

  useEffect(() => {
    getDemoScenarios().then(r => setScenarios(r.scenarios)).catch(() => { });
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const handleSessionUpdate = useCallback((s: SessionState) => {
    setSession(s);
  }, []);

  const handleNewSession = useCallback(() => {
    setSession({ sessionId: null, documents: [], totalSentences: 0 });
    setTurns([]);
    setPendingFiles([]);
  }, []);

  const handleSend = useCallback(async (query: string, overrideSessionId?: string) => {
    if (isProcessing) return;

    let currentSession = session;
    const activeSessionId = overrideSessionId || session.sessionId;

    if (pendingFiles.length > 0 || !activeSessionId) {
      if (pendingFiles.length > 0) {
        setIsProcessing(true);
        try {
          const filesToUpload = pendingFiles;
          setPendingFiles([]);

          const res = await ingestDocuments(
            filesToUpload.length > 0 ? filesToUpload : [],
            activeSessionId
          );

          currentSession = {
            sessionId: res.session_id,
            documents: [...session.documents, ...(res.documents || [])],
            totalSentences: res.total_sentences,
          };
          setSession(currentSession);
        } catch (e) {
          console.error("Ingest error", e);
          setIsProcessing(false);
          return;
        }
      } else {
        alert("Please upload a document first.");
        return;
      }
    }

    const finalSessionId = currentSession.sessionId || activeSessionId;
    if (!finalSessionId) {
      alert("Please upload a document first.");
      setIsProcessing(false);
      return;
    }

    if (!query) {
      setIsProcessing(false);
      return;
    }

    const turnIndex = turns.length + 1;

    const newTurn: ConversationTurn = {
      turnIndex,
      query,
      resolvedQuery: undefined,
      contextSteps: [],
      answer: "",
      isStreaming: false,
      isRetrieving: true,
      coveragePct: 0,
      totalTokens: 0,
      docsUsed: [],
    };
    setTurns(prev => [...prev, newTurn]);
    setIsProcessing(true);

    try {
      const response = await fetch(`${BASE}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: finalSessionId,
          query,
          mode: "adaptive",
          use_decomposition: true,
          retrieval_engine: "ot",
          params: DEFAULT_PARAMS,
        }),
      });

      if (!response.body) throw new Error("No stream body");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;

      while (!done) {
        const { value, done: rd } = await reader.read();
        done = rd;
        if (!value) continue;

        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          try {
            const data = JSON.parse(raw);
            const t = data.type || data.event;

            if (t === "query_resolved") {
              setTurns(prev => prev.map((turn, i) =>
                i === prev.length - 1 ? { ...turn, resolvedQuery: data.resolved } : turn
              ));
            } else if (t === "selection_step") {
              setTurns(prev => prev.map((turn, i) =>
                i === prev.length - 1
                  ? {
                    ...turn,
                    contextSteps: [...turn.contextSteps, data],
                    coveragePct: data.coverage_pct,
                    totalTokens: data.cumulative_tokens,
                    docsUsed: turn.docsUsed.includes(data.source_doc) ? turn.docsUsed : [...turn.docsUsed, data.source_doc],
                  }
                  : turn
              ));
            } else if (t === "saturation_reached") {
              setTurns(prev => prev.map((turn, i) =>
                i === prev.length - 1
                  ? { ...turn, isRetrieving: false, isStreaming: true }
                  : turn
              ));
            } else if (t === "llm_token") {
              setTurns(prev => prev.map((turn, i) =>
                i === prev.length - 1
                  ? { ...turn, isStreaming: true, answer: turn.answer + data.token }
                  : turn
              ));
            } else if (t === "answer_complete") {
              setTurns(prev => prev.map((turn, i) =>
                i === prev.length - 1
                  ? { ...turn, isStreaming: false, isRetrieving: false }
                  : turn
              ));
            } else if (t === "stream_error") {
              setTurns(prev => prev.map((turn, i) =>
                i === prev.length - 1
                  ? { ...turn, isStreaming: false, isRetrieving: false, answer: `Error: ${data.detail}` }
                  : turn
              ));
            }
          } catch { }
        }
      }
    } catch (e: any) {
      setTurns(prev => prev.map((turn, i) =>
        i === prev.length - 1
          ? { ...turn, isStreaming: false, isRetrieving: false, answer: `Connection error: ${e.message}` }
          : turn
      ));
    } finally {
      setIsProcessing(false);
    }
  }, [session, turns, pendingFiles, isProcessing]);

  const handleSelectScenario = async (sc: any) => {
    setLoadingDemo(true);
    try {
      const res = await loadDemoScenario(sc.id);
      const newSession = {
        sessionId: res.session_id,
        documents: res.documents,
        totalSentences: res.total_sentences,
      };
      setSession(newSession);
      await handleSend(sc.query, res.session_id);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDemo(false);
    }
  };

  const handleFileAttach = useCallback((files: File[]) => {
    setPendingFiles(prev => [...prev, ...files]);
  }, []);

  const inputPlaceholder = !session.sessionId
    ? "Upload documents from the sidebar first…"
    : "Ask about the retrieved documents...";

  return (
    <div className="h-screen w-screen bg-surface-0 text-text-body flex overflow-hidden font-sans">
      <Sidebar
        session={session}
        onSessionUpdate={handleSessionUpdate}
        onNewSession={handleNewSession}
        isSidebarOpen={isSidebarOpen}
      />

      {/* Main area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">

        {/* Header */}
        <div className="h-12 shrink-0 border-b border-border-default flex items-center px-6 gap-3 bg-surface-1/80 backdrop-blur-sm">
          <button
            onClick={() => setIsSidebarOpen(v => !v)}
            title={isSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
            className="p-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-2 transition-colors mr-1 shrink-0"
          >
            {isSidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
          </button>
          <span className="text-sm font-semibold text-text-primary">Chat</span>
          <div className="h-4 w-px bg-border-strong" />
          <span className="text-xs text-text-secondary">
            {session.sessionId
              ? `${session.totalSentences} sentences in search space`
              : "No active session"}
          </span>
          <div className="flex-1" />
          <button
            onClick={handleNewSession}
            title="Reset session"
            className="p-1.5 rounded hover:bg-surface-2 text-text-secondary hover:text-text-primary transition-colors"
          >
            <RotateCcw size={14} />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto custom-scrollbar px-8 py-6 flex flex-col">
          {turns.length === 0 ? (
            <EmptyState
              hasSession={!!session.sessionId}
              onSelectScenario={handleSelectScenario}
              scenarios={scenarios}
              loadingDemo={loadingDemo}
            />
          ) : (
            <div className="max-w-2xl mx-auto flex flex-col gap-6 w-full">
              {turns.map((turn, i) => (
                <TurnCard key={turn.turnIndex} turn={turn} isLast={i === turns.length - 1} />
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <div className="shrink-0 px-8 pb-5 pt-3 border-t border-border-default bg-surface-0">
          <div className="max-w-2xl mx-auto">
            <InputBar
              onSend={handleSend}
              onFileAttach={handleFileAttach}
              disabled={isProcessing || !session.sessionId}
              placeholder={inputPlaceholder}
              attachedFiles={pendingFiles}
              onRemoveFile={(i) => setPendingFiles(prev => prev.filter((_, idx) => idx !== i))}
            />
          </div>
        </div>
      </div>
    </div>
  );
}