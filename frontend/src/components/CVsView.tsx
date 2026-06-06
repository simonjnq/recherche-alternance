import { useCallback, useEffect, useRef, useState } from "react";
import { Check, FileText, Trash2, Upload } from "lucide-react";
import {
  deleteCV,
  getCVContent,
  listCVs,
  setDefaultCV,
  uploadCV,
} from "../api";
import type { CV } from "../types";
import { cn, formatBytes, formatDate } from "../lib/utils";

export function CVsView() {
  const [cvs, setCVs] = useState<CV[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [previewName, setPreviewName] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);

  const reload = useCallback(() => {
    listCVs().then(setCVs).catch(console.error);
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      setError(null);
      setUploading(true);
      try {
        for (const f of Array.from(files)) {
          const name = f.name.toLowerCase();
          const okExt =
            name.endsWith(".html") ||
            name.endsWith(".pdf") ||
            name.endsWith(".png") ||
            name.endsWith(".jpg") ||
            name.endsWith(".jpeg") ||
            name.endsWith(".webp");
          const okMime =
            f.type === "text/html" ||
            f.type === "application/pdf" ||
            f.type.startsWith("image/");
          if (!okExt && !okMime) {
            setError(`${f.name} ignoré (HTML, PDF ou image attendu)`);
            continue;
          }
          await uploadCV(f);
        }
        reload();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setUploading(false);
      }
    },
    [reload]
  );

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
  };

  const handlePreview = async (cv: CV) => {
    try {
      const res = await getCVContent(cv.id);
      setPreviewHtml(res.html);
      setPreviewName(res.filename);
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  };

  const handleDelete = async (cv: CV) => {
    if (!confirm(`Supprimer ${cv.filename} ?`)) return;
    await deleteCV(cv.id);
    reload();
  };

  const handleSetDefault = async (cv: CV) => {
    await setDefaultCV(cv.id);
    reload();
  };

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-xl font-semibold mb-1">Mes CVs</h1>
      <p className="text-sm text-on-surface-variant mb-6">
        Dépose ici tes CVs (HTML, PDF ou image PNG/JPG). Les PDFs et images sont
        convertis en HTML via Claude. Le CV par défaut sera adapté à chaque
        offre.
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "border-2 border-dashed rounded-xl px-6 py-10 text-center cursor-pointer transition-colors",
          dragOver
            ? "border-navy bg-surface-container"
            : "border-outline-variant bg-surface-lowest hover:border-outline"
        )}
      >
        <div className="mx-auto w-10 h-10 rounded-full bg-surface-container flex items-center justify-center mb-3">
          <Upload size={16} className="text-on-surface-variant" />
        </div>
        <div className="text-sm font-medium text-on-surface">
          {uploading
            ? "Upload en cours… (extraction Claude si PDF/image)"
            : "Glisse un CV ici ou clique"}
        </div>
        <div className="text-xs text-on-surface-variant mt-1">
          Formats acceptés : .html, .pdf, .png, .jpg, .jpeg, .webp
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".html,text/html,.pdf,application/pdf,.png,.jpg,.jpeg,.webp,image/*"
          multiple
          className="hidden"
          onChange={(e) => e.target.files && handleFiles(e.target.files)}
        />
      </div>

      {error && (
        <div className="mt-3 text-sm text-on-error-container bg-error-container border border-error rounded-md px-3 py-2">
          {error}
        </div>
      )}

      <div className="mt-6 space-y-2">
        {cvs.map((cv) => (
          <div
            key={cv.id}
            className="flex items-center gap-3 border border-outline-variant bg-surface-lowest rounded-lg p-3 hover:shadow-sm transition-shadow"
          >
            <div className="w-9 h-9 rounded-md bg-surface-container flex items-center justify-center text-on-surface-variant">
              <FileText size={15} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm truncate">
                  {cv.filename}
                </span>
                {cv.is_default && (
                  <span className="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded bg-secondary-container text-secondary">
                    <Check size={10} /> Par défaut
                  </span>
                )}
              </div>
              <div className="text-xs text-on-surface-variant mt-0.5">
                {formatBytes(cv.size)} · {formatDate(cv.uploaded_at)}
              </div>
            </div>
            <button
              onClick={() => handlePreview(cv)}
              className="text-sm text-on-surface-variant hover:text-on-surface px-2 py-1"
            >
              Aperçu
            </button>
            {!cv.is_default && (
              <button
                onClick={() => handleSetDefault(cv)}
                className="text-sm text-on-surface-variant hover:text-on-surface px-2 py-1"
              >
                Définir par défaut
              </button>
            )}
            <button
              onClick={() => handleDelete(cv)}
              className="p-1.5 text-on-surface-variant hover:text-error"
              aria-label="Supprimer"
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>

      {previewHtml && (
        <div
          className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-6"
          onClick={() => setPreviewHtml(null)}
        >
          <div
            className="bg-surface-lowest rounded-xl w-full max-w-4xl h-[80vh] flex flex-col overflow-hidden shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-4 py-3 border-b border-outline-variant flex items-center">
              <span className="font-medium text-sm">{previewName}</span>
              <button
                onClick={() => setPreviewHtml(null)}
                className="ml-auto text-sm text-on-surface-variant hover:text-on-surface"
              >
                Fermer
              </button>
            </div>
            <iframe
              title="CV"
              srcDoc={previewHtml}
              sandbox=""
              className="flex-1 w-full bg-surface-container-low"
            />
          </div>
        </div>
      )}
    </div>
  );
}
