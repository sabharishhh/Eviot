"use client";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { UploadCloud, FileText, CheckCircle, Loader2 } from "lucide-react";
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
      <div 
        {...getRootProps()} 
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors
          ${isDragActive ? "border-indigo-500 bg-indigo-500/10" : "border-slate-700 hover:border-slate-500 bg-[#1a1d27]"}`}
      >
        <input {...getInputProps()} />
        {isUploading ? (
          <div className="flex flex-col items-center gap-2 text-slate-400">
            <Loader2 className="animate-spin text-indigo-400" size={28} />
            <span className="text-sm">Encoding documents...</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 text-slate-400">
            <UploadCloud size={28} className="text-slate-500" />
            <span className="text-sm">Drag & drop PDFs, TXT, DOCX</span>
            <span className="text-[10px] text-slate-500 uppercase tracking-widest">or click to browse</span>
          </div>
        )}
      </div>

      {session.documents.length > 0 && (
        <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold uppercase tracking-wider">
            <CheckCircle size={14} /> Memory Loaded
          </div>
          <div className="flex justify-between items-center text-xs text-emerald-100/70">
            <span className="truncate flex items-center gap-1">
              <FileText size={12} /> {session.documents.length} File(s)
            </span>
            <span className="font-mono">{session.totalSentences} Sentences</span>
          </div>
        </div>
      )}
    </div>
  );
}