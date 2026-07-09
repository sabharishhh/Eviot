"use client";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { UploadCloud, FileText, Loader2 } from "lucide-react";
import { ingestDocuments } from "@/lib/api";
import { SessionState } from "@/lib/types";

interface Props {
  session: SessionState;
  onSessionUpdate: (session: SessionState) => void;
}

export default function DocumentUpload({ session, onSessionUpdate }: Props) {
  const [isUploading, setIsUploading] = useState(false);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    setIsUploading(true);
    try {
      const res = await ingestDocuments(acceptedFiles);
      onSessionUpdate({
        sessionId: res.session_id,
        documents: res.documents,
        totalSentences: res.total_sentences,
      });
    } catch (e) {
      console.error("Upload failed", e);
      alert("Upload failed. Ensure backend is running.");
    } finally {
      setIsUploading(false);
    }
  }, [onSessionUpdate]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

  return (
    <div className="flex flex-col gap-3">
      <label className="text-[10px] font-semibold text-slate-500 uppercase tracking-[0.18em]">
        Knowledge Base
      </label>

      <div
        {...getRootProps()}
        className={`border border-dashed rounded-2xl p-6 text-center cursor-pointer transition-all
          ${isDragActive
            ? "border-indigo-500/70 bg-indigo-500/10 shadow-lg shadow-indigo-500/10"
            : "border-white/10 hover:border-white/25 bg-[#1A1E2B]"}`}
      >
        <input {...getInputProps()} />
        {isUploading ? (
          <div className="flex flex-col items-center gap-2 text-slate-400">
            <Loader2 className="animate-spin text-indigo-400" size={26} />
            <span className="text-sm">Encoding documents…</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <div className="w-10 h-10 rounded-full bg-indigo-500/15 flex items-center justify-center">
              <UploadCloud size={19} className="text-indigo-400" />
            </div>
            <span className="text-sm text-slate-300">Drag &amp; drop PDFs, TXT, DOCX</span>
            <span className="text-[10px] text-slate-600 uppercase tracking-[0.18em]">or click to browse</span>
          </div>
        )}
      </div>

      {/* Loaded state — status pill styled like the reference's green "On" badges */}
      {session.documents.length > 0 && (
        <div className="bg-[#1A1E2B] border border-white/5 rounded-2xl px-4 py-3 flex items-center justify-between">
          <span className="flex items-center gap-2 text-xs text-slate-300 truncate">
            <FileText size={13} className="text-slate-500 shrink-0" />
            {session.documents.length} file{session.documents.length > 1 ? "s" : ""} · {session.totalSentences} sentences
          </span>
          <span className="shrink-0 ml-3 px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 text-[10px] font-semibold uppercase tracking-wider flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Loaded
          </span>
        </div>
      )}
    </div>
  );
}