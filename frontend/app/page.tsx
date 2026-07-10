"use client";

import {
  useState,
  useRef,
  useCallback,
  useEffect,
} from "react";
import {
  SessionState,
  ConversationTurn,
  QueryParams,
} from "@/lib/types";
import {
  ingestDocuments,
  getDemoScenarios,
  loadDemoScenario,
} from "@/lib/api";
import {
  ArrowUp,
  FileText,
  File,
  X,
  BookOpen,
  Plus,
  RotateCcw,
  Loader2,
  FilePlus,
  Hash,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  Database,
} from "lucide-react";

import MemoryPanel from "@/components/visualization/MemoryPanel";

const BASE = "http://localhost:8000";

const DEFAULT_PARAMS: QueryParams = {
  epsilon: 0.01,
  patience: 2,
  k_max: 12,
  k: 5,
};

// ─── File type icon helper ───────────────────────────────────────────────────

function DocIcon({
  filename,
  size = 13,
}: {
  filename: string;
  size?: number;
}) {
  const ext = filename.split(".").pop()?.toLowerCase();
  const cls = "shrink-0";

  if (ext === "pdf") {
    return (
      <FileText
        size={size}
        className={`${cls} text-red-400`}
      />
    );
  }

  if (ext === "docx" || ext === "doc") {
    return (
      <FileText
        size={size}
        className={`${cls} text-blue-400`}
      />
    );
  }

  if (ext === "md") {
    return (
      <Hash
        size={size}
        className={`${cls} text-purple-400`}
      />
    );
  }

  return (
    <File
      size={size}
      className={`${cls} text-slate-400`}
    />
  );
}

// ─── Turn Card ───────────────────────────────────────────────────────────────

function TurnCard({
  turn,
}: {
  turn: ConversationTurn;
  isLast: boolean;
}) {
  const [selectedSource, setSelectedSource] = useState<
    number | null
  >(null);

  return (
    <div className="flex w-full flex-col gap-4 animate-fade-in">
      {/* User query */}
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-tr-none bg-gradient-to-r from-zinc-100 via-white to-zinc-100 px-5 py-3 text-zinc-900 shadow-md animate-fade-in">
          <p className="font-sans text-[15px] leading-relaxed">
            {turn.query}
          </p>

          {turn.resolvedQuery &&
            turn.resolvedQuery !== turn.query && (
              <p className="mt-1 font-sans text-xs italic text-zinc-500">
                ↳ {turn.resolvedQuery}
              </p>
            )}
        </div>
      </div>

      {/* Assistant response */}
      {(turn.answer ||
        turn.isStreaming ||
        turn.isRetrieving) && (
        <div className="flex w-full items-start gap-4">
          <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center">
            <div className="eviot-blob" />
          </div>

          <div className="flex-1 space-y-4">
            {turn.isRetrieving &&
            turn.contextSteps.length === 0 ? (
              <div className="flex items-center gap-2 py-2 text-xs text-text-secondary">
                <Loader2
                  size={12}
                  className="animate-spin text-accent"
                />

                <span>
                  Retrieving context chunks using Optimal
                  Transport...
                </span>
              </div>
            ) : (
              <>
                {turn.answer && (
                  <p className="whitespace-pre-wrap font-sans text-[15px] leading-relaxed text-zinc-100">
                    {turn.answer}

                    {turn.isStreaming && (
                      <span className="ml-1 inline-block h-4 w-1.5 animate-pulse bg-accent align-middle" />
                    )}
                  </p>
                )}

                {turn.contextSteps.length > 0 && (
                  <div className="mt-2 border-t border-border-default/40 pt-3">
                    <div className="mb-2 flex items-center gap-1.5">
                      <BookOpen
                        size={12}
                        className="text-text-tertiary"
                      />

                      <span className="text-[10px] font-bold uppercase tracking-wider text-text-tertiary">
                        Retrieved Sources
                      </span>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {turn.contextSteps.map(
                        (step, idx) => {
                          const docName =
                            step.source_doc
                              .split("/")
                              .pop() || step.source_doc;

                          const shortName =
                            docName.length > 20
                              ? `${docName.slice(0, 18)}...`
                              : docName;

                          const isSelected =
                            selectedSource === idx;

                          return (
                            <button
                              key={idx}
                              type="button"
                              onClick={() =>
                                setSelectedSource(
                                  isSelected ? null : idx,
                                )
                              }
                              className={`flex cursor-pointer select-none items-center gap-1.5 rounded-md border px-2.5 py-1 font-mono text-[11px] transition-all hover:border-accent hover:bg-surface-3 hover:text-text-primary ${
                                isSelected
                                  ? "border-accent bg-surface-2 text-text-primary"
                                  : "border-border-default bg-surface-2 text-text-secondary"
                              }`}
                            >
                              <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-accent/15 text-[9px] font-bold text-accent">
                                {idx + 1}
                              </span>

                              <span>{shortName}</span>

                              <span className="text-text-tertiary">
                                p.{step.source_line}
                              </span>
                            </button>
                          );
                        },
                      )}
                    </div>

                    {selectedSource !== null &&
                      turn.contextSteps[selectedSource] && (
                        <div className="mt-3 animate-fade-in rounded-lg border border-border-default bg-surface-2 p-3 font-sans text-xs leading-relaxed text-text-body">
                          <div className="mb-2 flex items-center justify-between border-b border-border-default pb-1.5 font-mono text-[10px] text-text-secondary">
                            <span className="truncate text-accent">
                              {
                                turn.contextSteps[
                                  selectedSource
                                ].source_doc
                              }{" "}
                              (p.{" "}
                              {
                                turn.contextSteps[
                                  selectedSource
                                ].source_line
                              }
                              )
                            </span>
                          </div>

                          <p className="italic text-text-body">
                            &quot;
                            {
                              turn.contextSteps[
                                selectedSource
                              ].sentence_text
                            }
                            &quot;
                          </p>
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
  session,
  onSessionUpdate,
  onNewSession,
  isSidebarOpen,
}: {
  session: SessionState;
  onSessionUpdate: (s: SessionState) => void;
  onNewSession: () => void;
  isSidebarOpen: boolean;
}) {
  const [isUploading, setIsUploading] =
    useState(false);
  const [scenarios, setScenarios] = useState<any[]>(
    [],
  );
  const [loadingDemo, setLoadingDemo] =
    useState(false);

  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getDemoScenarios()
      .then((r) => setScenarios(r.scenarios))
      .catch(() => {});
  }, []);

  const handleFiles = async (files: File[]) => {
    if (!files.length || isUploading) return;

    setIsUploading(true);

    try {
      const res = await ingestDocuments(
        files,
        session.sessionId,
      );

      onSessionUpdate({
        sessionId: res.session_id,
        documents: [
          ...session.documents,
          ...(res.documents || []),
        ],
        totalSentences: res.total_sentences,
      });
    } catch (e) {
      console.error("Sidebar upload failed:", e);
      alert(
        "Upload failed. Ensure the backend is running.",
      );
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadDemo = async (sc: any) => {
    setLoadingDemo(true);

    try {
      const res = await loadDemoScenario(sc.id);

      onSessionUpdate({
        sessionId: res.session_id,
        documents: res.documents,
        totalSentences: res.total_sentences,
      });
    } catch (e) {
      console.error("Demo loading failed:", e);
    } finally {
      setLoadingDemo(false);
    }
  };

  return (
    <aside
      className={`flex h-full shrink-0 flex-col border-r border-white/[0.055] bg-[#181818] transition-[width] duration-200 ease-out ${
        isSidebarOpen ? "w-[260px]" : "w-[56px]"
      }`}
    >
      {/* Brand */}
      <div
        className={`flex h-[58px] shrink-0 items-center ${
          isSidebarOpen
            ? "justify-between px-3"
            : "justify-center"
        }`}
      >
        <div className="flex min-w-0 items-center gap-2.5">
          <img
            src="/favicon.ico"
            alt="Eviot"
            className="h-[26px] w-[26px] shrink-0 object-contain"
          />

          {isSidebarOpen && (
            <div className="min-w-0 leading-tight">
              <div className="truncate text-[15px] font-semibold text-[#f2f2f2]">
                Eviot
              </div>

              <div className="mt-0.5 truncate text-[11px] text-[#8e8e8e]">
                Context That Works
              </div>
            </div>
          )}
        </div>
      </div>

      {/* New Session */}
      <div
        className={
          isSidebarOpen
            ? "px-2 pb-3 pt-3"
            : "flex justify-center pb-3 pt-3"
        }
      >
        <button
          type="button"
          onClick={onNewSession}
          title="New Session"
          className={`group flex items-center text-[#ececec] transition-colors hover:bg-[#2a2a2a] ${
            isSidebarOpen
              ? "h-10 w-full gap-3 rounded-lg px-3"
              : "h-10 w-10 justify-center rounded-lg"
          }`}
        >
          <Plus
            size={18}
            strokeWidth={1.8}
            className="shrink-0"
          />

          {isSidebarOpen && (
            <span className="text-[14px] font-medium">
              New Session
            </span>
          )}
        </button>
      </div>

      {/* Scrollable navigation */}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-2 pb-3 custom-scrollbar">
        {/* Documents */}
        <section className="mb-5">
          {isSidebarOpen && (
            <div className="mb-1 px-2">
              <span className="text-[12px] font-semibold text-[#b4b4b4]">
                Documents
              </span>
            </div>
          )}

          <div className="flex flex-col gap-0.5">
            {session.documents.length === 0 &&
              isSidebarOpen && (
                <div className="px-2 py-2 text-[13px] text-[#777777]">
                  No documents loaded
                </div>
              )}

            {session.documents.map((doc, i) => (
              <div
                key={`${doc.filename}-${i}`}
                title={doc.filename}
                className={`group flex h-9 items-center text-[#d4d4d4] transition-colors hover:bg-[#242424] ${
                  isSidebarOpen
                    ? "gap-3 rounded-lg px-2"
                    : "justify-center rounded-lg"
                }`}
              >
                <DocIcon
                  filename={doc.filename}
                  size={16}
                />

                {isSidebarOpen && (
                  <span className="min-w-0 flex-1 truncate text-[13px]">
                    {doc.filename}
                  </span>
                )}
              </div>
            ))}

            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={isUploading}
              title="Add Documents"
              className={`flex h-9 items-center text-[#b4b4b4] transition-colors hover:bg-[#242424] hover:text-[#ececec] disabled:opacity-50 ${
                isSidebarOpen
                  ? "gap-3 rounded-lg px-2"
                  : "justify-center rounded-lg"
              }`}
            >
              {isUploading ? (
                <Loader2
                  size={16}
                  strokeWidth={1.8}
                  className="shrink-0 animate-spin"
                />
              ) : (
                <FilePlus
                  size={16}
                  strokeWidth={1.8}
                  className="shrink-0"
                />
              )}

              {isSidebarOpen && (
                <span className="text-[13px]">
                  {isUploading
                    ? "Encoding…"
                    : "Add Documents"}
                </span>
              )}
            </button>
          </div>

          <input
            ref={fileRef}
            type="file"
            multiple
            accept=".pdf,.txt,.md,.docx"
            className="hidden"
            onChange={(e) => {
              const files = Array.from(
                e.target.files || [],
              );

              void handleFiles(files);
              e.target.value = "";
            }}
          />
        </section>

        {/* Quick Start */}
        <section>
          {isSidebarOpen && (
            <div className="mb-1 px-2">
              <span className="text-[12px] font-semibold text-[#b4b4b4]">
                Quick Start
              </span>
            </div>
          )}

          <div className="flex flex-col gap-0.5">
            {scenarios.map((sc) => (
              <button
                key={sc.id}
                type="button"
                onClick={() => handleLoadDemo(sc)}
                disabled={loadingDemo}
                title={sc.title}
                className={`group flex h-9 items-center text-left text-[#d4d4d4] transition-colors hover:bg-[#242424] disabled:opacity-50 ${
                  isSidebarOpen
                    ? "gap-3 rounded-lg px-2"
                    : "justify-center rounded-lg"
                }`}
              >
                <File
                  size={16}
                  strokeWidth={1.7}
                  className="shrink-0 text-[#b4b4b4]"
                />

                {isSidebarOpen && (
                  <span className="min-w-0 flex-1 truncate text-[13px]">
                    {sc.title}
                  </span>
                )}
              </button>
            ))}
          </div>
        </section>
      </div>

      {/* Settings */}
      <div
        className={
          isSidebarOpen
            ? "px-2 pb-2"
            : "flex justify-center pb-2"
        }
      >
        <button
          type="button"
          title="Settings"
          className={`flex h-10 items-center text-[#a7a7a7] transition-colors hover:bg-[#242424] hover:text-[#ececec] ${
            isSidebarOpen
              ? "w-full gap-3 rounded-lg px-3"
              : "w-10 justify-center rounded-lg"
          }`}
        >
          <Settings
            size={17}
            strokeWidth={1.7}
            className="shrink-0"
          />

          {isSidebarOpen && (
            <span className="text-[13px]">
              Settings
            </span>
          )}
        </button>
      </div>
    </aside>
  );
}

// ─── Input Bar ───────────────────────────────────────────────────────────────

function InputBar({
  onSend,
  onFileAttach,
  disabled,
  placeholder,
  attachedFiles,
  onRemoveFile,
}: {
  onSend: (text: string) => void;
  onFileAttach: (
    files: File[],
  ) => void | Promise<void>;
  disabled: boolean;
  placeholder: string;
  attachedFiles: File[];
  onRemoveFile: (index: number) => void;
}) {
  const [text, setText] = useState("");
  const [isMultiline, setIsMultiline] =
    useState(false);

  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef =
    useRef<HTMLTextAreaElement>(null);

  const hasContent =
    text.trim().length > 0 ||
    attachedFiles.length > 0;

  const resizeTextarea = useCallback(() => {
    const textarea = textareaRef.current;

    if (!textarea) return;

    const singleLineHeight = 28;
    const maxHeight = 200;

    /*
     * Reset to one line first. This allows the textarea
     * to shrink correctly when text is deleted.
     */
    textarea.style.height = `${singleLineHeight}px`;

    const contentHeight = textarea.scrollHeight;

    const nextHeight = Math.min(
      Math.max(contentHeight, singleLineHeight),
      maxHeight,
    );

    textarea.style.height = `${nextHeight}px`;

    textarea.style.overflowY =
      contentHeight > maxHeight ? "auto" : "hidden";

    setIsMultiline(nextHeight > singleLineHeight);
  }, []);

  useEffect(() => {
    resizeTextarea();
  }, [text, resizeTextarea]);

  const resetTextarea = useCallback(() => {
    const textarea = textareaRef.current;

    if (!textarea) return;

    textarea.style.height = "28px";
    textarea.style.overflowY = "hidden";

    setIsMultiline(false);
  }, []);

  const handleSend = () => {
    if (!text.trim() || disabled) return;

    onSend(text.trim());
    setText("");

    requestAnimationFrame(resetTextarea);
  };

  const handleKey = (
    e: React.KeyboardEvent<HTMLTextAreaElement>,
  ) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex w-full flex-col gap-2">
      {/* Attached files */}
      {attachedFiles.length > 0 && (
        <div className="mb-1 flex flex-wrap gap-1.5 animate-fade-in">
          {attachedFiles.map((file, index) => (
            <div
              key={`${file.name}-${index}`}
              className="flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-[#212121] px-2.5 py-1"
            >
              <DocIcon
                filename={file.name}
                size={11}
              />

              <span className="max-w-[140px] truncate text-xs text-[#d4d4d4]">
                {file.name}
              </span>

              <button
                type="button"
                onClick={() => onRemoveFile(index)}
                className="ml-0.5 text-[#8e8e8e] transition-colors hover:text-white"
              >
                <X size={11} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Auto-growing composer */}
      <div
        className={`
          flex
          min-h-[72px]
          w-full
          rounded-[36px]
          bg-[#212121]
          px-3
          py-3
          shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_6px_24px_rgba(0,0,0,0.18)]
          transition-colors
          duration-200
          focus-within:bg-[#242424]
          ${isMultiline ? "items-end" : "items-center"}
        `}
      >
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md,.docx"
          className="hidden"
          onChange={(e) => {
            const files = Array.from(
              e.target.files || [],
            );

            if (files.length > 0) {
              void onFileAttach(files);
            }

            e.target.value = "";
          }}
        />

        {/* Attachment button */}
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={disabled}
          title="Attach files"
          className="
            flex
            h-12
            w-12
            shrink-0
            items-center
            justify-center
            rounded-full
            text-[#f2f2f2]
            transition-colors
            hover:bg-white/[0.08]
            disabled:cursor-not-allowed
            disabled:opacity-50
          "
        >
          <Plus size={28} strokeWidth={1.6} />
        </button>

        {/* Auto-growing prompt textarea */}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
          }}
          onKeyDown={handleKey}
          disabled={disabled}
          placeholder={placeholder}
          rows={1}
          className="
            min-h-[28px]
            max-h-[200px]
            flex-1
            resize-none
            overflow-y-hidden
            bg-transparent
            px-2
            py-0
            text-[16px]
            leading-7
            text-[#f2f2f2]
            outline-none
            placeholder:text-[#9b9b9b]
            disabled:cursor-not-allowed
            custom-scrollbar
          "
          style={{
            height: "28px",
          }}
        />

        {/* Send button */}
        <button
          type="button"
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          title="Send prompt"
          className={`ml-2 flex h-12 w-12 shrink-0 items-center justify-center rounded-full transition-all duration-150 ${
            disabled || !text.trim()
              ? "bg-[#3a3a3a] text-[#777777]"
              : "bg-white text-black hover:scale-[1.03] hover:bg-[#e8e8e8]"
          }`}
        >
          <ArrowUp
            size={24}
            strokeWidth={2.6}
          />
        </button>
      </div>

      <p className="text-center text-[11px] text-text-tertiary">
        Eviot is AI and can make mistakes. Please
        double-check responses.
      </p>
    </div>
  );
}

// ─── Empty State ─────────────────────────────────────────────────────────────

function EmptyState({
  onSend,
  onFileAttach,
  disabled,
  hasSession,
  attachedFiles,
  onRemoveFile,
}: {
  onSend: (text: string) => void;
  onFileAttach: (
    files: File[],
  ) => void | Promise<void>;
  disabled: boolean;
  hasSession: boolean;
  attachedFiles: File[];
  onRemoveFile: (index: number) => void;
}) {
  return (
    <div className="flex flex-1 items-center justify-center">
      <div className="w-full max-w-4xl -translate-y-8 px-6">
        <div className="mb-10 text-center">
          <h1 className="text-3xl font-extrabold tracking-tight text-zinc-100 md:text-4xl">
            How can I help you today ?
          </h1>

          <p className="mx-auto mt-5 max-w-md text-sm leading-relaxed text-text-secondary">
            Add context. Build memory. Start the conversation.
          </p>
        </div>

        <InputBar
          onSend={onSend}
          onFileAttach={onFileAttach}
          disabled={disabled}
          placeholder={
            disabled
              ? "Uploading and encoding memory..."
              : hasSession
                ? "Start conversation..."
                : "Upload context files to get started..."
          }
          attachedFiles={attachedFiles}
          onRemoveFile={onRemoveFile}
        />
      </div>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function Home() {
  const [session, setSession] =
    useState<SessionState>({
      sessionId: null,
      documents: [],
      totalSentences: 0,
    });

  const [turns, setTurns] = useState<
    ConversationTurn[]
  >([]);

  const [pendingFiles, setPendingFiles] = useState<
    File[]
  >([]);

  const [isProcessing, setIsProcessing] =
    useState(false);

  const [isSidebarOpen, setIsSidebarOpen] =
    useState(true);

  const [isMemoryOpen, setIsMemoryOpen] = 
    useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [turns]);

  const handleSessionUpdate = useCallback(
    (updatedSession: SessionState) => {
      setSession(updatedSession);
    },
    [],
  );

  const handleNewSession = useCallback(() => {
    setSession({
      sessionId: null,
      documents: [],
      totalSentences: 0,
    });

    setTurns([]);
    setPendingFiles([]);
  }, []);

  const removePendingFile = useCallback(
    (index: number) => {
      setPendingFiles((prev) =>
        prev.filter((_, i) => i !== index),
      );
    },
    [],
  );

  // ─── Immediate composer upload ─────────────────────────────────────────────

  const handleFileAttach = useCallback(
    async (files: File[]) => {
      if (!files.length || isProcessing) return;

      setPendingFiles((prev) => [
        ...prev,
        ...files,
      ]);

      setIsProcessing(true);

      try {
        const res = await ingestDocuments(
          files,
          session.sessionId,
        );

        setSession((prev) => ({
          sessionId: res.session_id,
          documents: [
            ...prev.documents,
            ...(res.documents || []),
          ],
          totalSentences: res.total_sentences,
        }));

        setPendingFiles([]);
      } catch (e) {
        console.error(
          "Composer upload failed:",
          e,
        );

        alert(
          "Upload failed. Ensure the backend is running.",
        );

        setPendingFiles([]);
      } finally {
        setIsProcessing(false);
      }
    },
    [session.sessionId, isProcessing],
  );

  // ─── Query handling ────────────────────────────────────────────────────────

  const handleSend = useCallback(
    async (
      query: string,
      overrideSessionId?: string,
    ) => {
      if (isProcessing || !query.trim()) return;

      const finalSessionId =
        overrideSessionId || session.sessionId;

      if (!finalSessionId) {
        alert("Please upload a document first.");
        return;
      }

      const turnIndex = turns.length + 1;

      const newTurn: ConversationTurn = {
        turnIndex,
        query: query.trim(),
        resolvedQuery: undefined,
        contextSteps: [],
        answer: "",
        isStreaming: false,
        isRetrieving: true,
        coveragePct: 0,
        totalTokens: 0,
        docsUsed: [],
      };

      setTurns((prev) => [
        ...prev,
        newTurn,
      ]);

      setIsProcessing(true);

      try {
        const response = await fetch(
          `${BASE}/query`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              session_id: finalSessionId,
              query: query.trim(),
              mode: "adaptive",
              use_decomposition: true,
              retrieval_engine: "ot",
              params: DEFAULT_PARAMS,
            }),
          },
        );

        if (!response.ok) {
          throw new Error(
            `Request failed with status ${response.status}`,
          );
        }

        if (!response.body) {
          throw new Error("No stream body");
        }

        const reader =
          response.body.getReader();

        const decoder = new TextDecoder();

        let buffer = "";
        let done = false;

        while (!done) {
          const {
            value,
            done: readerDone,
          } = await reader.read();

          done = readerDone;

          if (value) {
            buffer += decoder.decode(value, {
              stream: !readerDone,
            });
          }

          const lines = buffer.split("\n");

          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) {
              continue;
            }

            const raw = line.slice(6).trim();

            if (!raw) continue;

            try {
              const data = JSON.parse(raw);
              const type =
                data.type || data.event;

              if (type === "query_resolved") {
                setTurns((prev) =>
                  prev.map((turn, i) =>
                    i === prev.length - 1
                      ? {
                          ...turn,
                          resolvedQuery:
                            data.resolved,
                        }
                      : turn,
                  ),
                );
              } else if (
                type === "selection_step"
              ) {
                setTurns((prev) =>
                  prev.map((turn, i) =>
                    i === prev.length - 1
                      ? {
                          ...turn,
                          contextSteps: [
                            ...turn.contextSteps,
                            data,
                          ],
                          coveragePct:
                            data.coverage_pct,
                          totalTokens:
                            data.cumulative_tokens,
                          docsUsed:
                            turn.docsUsed.includes(
                              data.source_doc,
                            )
                              ? turn.docsUsed
                              : [
                                  ...turn.docsUsed,
                                  data.source_doc,
                                ],
                        }
                      : turn,
                  ),
                );
              } else if (
                type === "saturation_reached"
              ) {
                setTurns((prev) =>
                  prev.map((turn, i) =>
                    i === prev.length - 1
                      ? {
                          ...turn,
                          isRetrieving: false,
                          isStreaming: true,
                        }
                      : turn,
                  ),
                );
              } else if (
                type === "llm_token"
              ) {
                setTurns((prev) =>
                  prev.map((turn, i) =>
                    i === prev.length - 1
                      ? {
                          ...turn,
                          isRetrieving: false,
                          isStreaming: true,
                          answer:
                            turn.answer +
                            (data.token || ""),
                        }
                      : turn,
                  ),
                );
              } else if (
                type === "answer_complete"
              ) {
                setTurns((prev) =>
                  prev.map((turn, i) =>
                    i === prev.length - 1
                      ? {
                          ...turn,
                          isStreaming: false,
                          isRetrieving: false,
                        }
                      : turn,
                  ),
                );
              } else if (
                type === "stream_error"
              ) {
                setTurns((prev) =>
                  prev.map((turn, i) =>
                    i === prev.length - 1
                      ? {
                          ...turn,
                          isStreaming: false,
                          isRetrieving: false,
                          answer: `Error: ${data.detail}`,
                        }
                      : turn,
                  ),
                );
              }
            } catch {
              console.warn(
                "Ignoring malformed SSE event:",
                raw,
              );
            }
          }
        }
      } catch (e: unknown) {
        const message =
          e instanceof Error
            ? e.message
            : "Unknown connection error";

        setTurns((prev) =>
          prev.map((turn, i) =>
            i === prev.length - 1
              ? {
                  ...turn,
                  isStreaming: false,
                  isRetrieving: false,
                  answer: `Connection error: ${message}`,
                }
              : turn,
          ),
        );
      } finally {
        setIsProcessing(false);
      }
    },
    [
      session.sessionId,
      turns.length,
      isProcessing,
    ],
  );

  const hasTurns = turns.length > 0;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-surface-0 font-sans text-text-body">
      <Sidebar
        session={session}
        onSessionUpdate={handleSessionUpdate}
        onNewSession={handleNewSession}
        isSidebarOpen={isSidebarOpen}
      />

      {/* Main Workspace (Split Pane) */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* Left Side: Chat Area */}
        <div
          className={`flex h-full flex-col overflow-hidden transition-all duration-300 ${
            isMemoryOpen ? "w-1/2 border-r border-border-default" : "w-full"
          }`}
        >
          {/* Header */}
          <div className="flex h-12 shrink-0 items-center gap-3 border-b border-border-default bg-surface-1/80 px-6 backdrop-blur-sm">
            <button
              type="button"
              onClick={() =>
                setIsSidebarOpen(
                  (value) => !value,
                )
              }
              title={
                isSidebarOpen
                  ? "Collapse sidebar"
                  : "Expand sidebar"
              }
              className="mr-1 shrink-0 rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-surface-2 hover:text-text-primary"
            >
              {isSidebarOpen ? (
                <PanelLeftClose size={16} />
              ) : (
                <PanelLeftOpen size={16} />
              )}
            </button>

            <span className="text-sm font-semibold text-text-primary">
              Chat
            </span>

            <div className="h-4 w-px bg-border-strong" />

            <span className="text-xs text-text-secondary">
              {session.sessionId
                ? `${session.totalSentences} items in search space`
                : "No active session"}
            </span>

            <div className="flex-1" />

            {/* NEW: Memory Panel Toggle Button */}
            <button
              type="button"
              onClick={() => setIsMemoryOpen((v) => !v)}
              title="Inspect OKF Memory"
              className={`flex items-center gap-2 rounded px-2 py-1.5 text-xs font-semibold transition-colors ${
                isMemoryOpen
                  ? 'bg-[#e8e8e8] text-[#181818]'
                  : "text-text-secondary hover:bg-surface-2 hover:text-text-primary"
              }`}
            >
              <Database size={14} />
              {isMemoryOpen && <span>Memory</span>}
            </button>

            <button
              type="button"
              onClick={handleNewSession}
              title="Reset session"
              className="rounded p-1.5 text-text-secondary transition-colors hover:bg-surface-2 hover:text-text-primary"
            >
              <RotateCcw size={14} />
            </button>
          </div>

          {!hasTurns ? (
            <EmptyState
              onSend={handleSend}
              onFileAttach={handleFileAttach}
              disabled={isProcessing}
              hasSession={Boolean(
                session.sessionId,
              )}
              attachedFiles={pendingFiles}
              onRemoveFile={removePendingFile}
            />
          ) : (
            <>
              {/* Messages */}
              <div className="flex flex-1 flex-col overflow-y-auto px-8 py-6 custom-scrollbar">
                <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
                  {turns.map((turn, i) => (
                    <TurnCard
                      key={turn.turnIndex}
                      turn={turn}
                      isLast={
                        i === turns.length - 1
                      }
                    />
                  ))}
                </div>

                <div ref={bottomRef} />
              </div>

              {/* Bottom composer */}
              <div className="shrink-0 bg-surface-0 px-8 pb-5 pt-3">
                <div className="mx-auto w-full max-w-4xl">
                  <InputBar
                    onSend={handleSend}
                    onFileAttach={
                      handleFileAttach
                    }
                    disabled={isProcessing}
                    placeholder="Ask about the retrieved documents..."
                    attachedFiles={pendingFiles}
                    onRemoveFile={
                      removePendingFile
                    }
                  />
                </div>
              </div>
            </>
          )}
        </div>

        {/* Right Side: Memory Panel */}
        {isMemoryOpen && (
          <div className="w-1/2 h-full flex flex-col bg-slate-950 animate-fade-in border-l border-border-default overflow-hidden">
            <MemoryPanel />
          </div>
        )}
      </div>
    </div>
  );
}