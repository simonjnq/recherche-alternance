import { useEffect, useState } from "react";
import { Download, MessageSquare, RefreshCw } from "lucide-react";
import { getInterview, makeInterview } from "../api";

/** Rendu markdown minimal (titres ##, gras **, puces). Le projet n'embarque pas
 *  de lib markdown — pour une fiche de 10 000 caractères structurée en sections,
 *  le texte brut serait illisible, mais une dépendance serait disproportionnée. */
function renderMarkdown(md: string) {
  const bold = (line: string) =>
    line.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
      part.startsWith("**") && part.endsWith("**") ? (
        <strong key={i} className="text-on-surface">
          {part.slice(2, -2)}
        </strong>
      ) : (
        <span key={i}>{part}</span>
      )
    );

  return md.split("\n").map((line, i) => {
    if (line.startsWith("## ")) {
      return (
        <h4 key={i} className="section-label mt-4 mb-1.5 first:mt-0">
          {line.slice(3)}
        </h4>
      );
    }
    if (/^[-*]\s/.test(line)) {
      return (
        <li key={i} className="ml-4 list-disc text-body-md text-on-surface-variant">
          {bold(line.replace(/^[-*]\s/, ""))}
        </li>
      );
    }
    if (!line.trim()) return <div key={i} className="h-2" />;
    return (
      <p key={i} className="text-body-md text-on-surface-variant mb-1">
        {bold(line)}
      </p>
    );
  });
}

/** Prépa entretien. Comme la fiche entreprise : le chargement est gratuit, la
 *  génération est explicite. */
export function InterviewPrep({ offerId, title }: { offerId: number; title: string }) {
  const [md, setMd] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setMd(null);
    setOpen(false);
    setError(null);
    getInterview(offerId)
      .then((r) => {
        if (!("missing" in r)) {
          setMd(r.markdown);
          setOpen(true);
        }
      })
      .catch(() => undefined);
  }, [offerId]);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await makeInterview(offerId);
      setMd(r.markdown);
      setOpen(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Génération impossible");
    } finally {
      setLoading(false);
    }
  };

  const download = () => {
    if (!md) return;
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `prepa-entretien-${title.slice(0, 40).replace(/[^\w]+/g, "-").toLowerCase()}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="mb-5">
      <h4 className="section-label mb-2">Préparation d'entretien</h4>

      {!md && (
        <>
          <button onClick={run} disabled={loading} className="btn-secondary btn-sm">
            <MessageSquare size={14} className={loading ? "animate-pulse" : ""} />
            {loading ? "Préparation… (~1 min)" : "Préparer l'entretien"}
          </button>
          <p className="mt-2 text-label-sm text-on-surface-variant">
            Questions probables, tes angles faibles, ce qu'il ne faut pas ignorer sur
            eux, et les questions à leur poser. Plus riche si la fiche entreprise a
            été recherchée.
          </p>
        </>
      )}

      {error && <p className="mt-2 text-body-md text-on-error-container">{error}</p>}

      {md && (
        <div className="rounded-lg border border-outline-variant bg-surface-c p-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setOpen((o) => !o)}
              className="text-body-md text-on-surface hover:underline"
            >
              {open ? "Replier la fiche" : "Afficher la fiche"}
            </button>
            <button onClick={download} className="ml-auto btn-secondary btn-sm">
              <Download size={12} /> .md
            </button>
            <button onClick={run} disabled={loading} className="btn-secondary btn-sm">
              <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
              {loading ? "…" : "Refaire"}
            </button>
          </div>
          {open && <div className="mt-3">{renderMarkdown(md)}</div>}
        </div>
      )}
    </div>
  );
}
