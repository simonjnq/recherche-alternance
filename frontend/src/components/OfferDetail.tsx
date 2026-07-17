import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  Copy,
  Download,
  Eye,
  ExternalLink,
  EyeOff,
  Mail,
  Maximize2,
  Pencil,
  RefreshCw,
  Send,
  Square,
  CheckSquare,
  Star,
  X,
} from "lucide-react";
import {
  downloadCVPdfUrl,
  downloadLetterPdfUrl,
  generateOffer,
  getGeneratedCV,
  getGeneratedLetter,
  getOffer,
  hideOffer,
  setFavorite,
  setOfferStatus,
  updateOfferTracking,
  type OfferTracking,
} from "../api";
import { CompanyCard } from "./CompanyCard";
import { InterviewPrep } from "./InterviewPrep";
import type { OfferDetail as OfferDetailType } from "../types";
import { SOURCE_LABEL } from "../types";
import { cn, scoreColor } from "../lib/utils";

interface Props {
  offerId: number;
  onClose: () => void;
  onChanged: () => void;
  onEdit: (offerId: number) => void;
  onOpenFull: (offerId: number) => void;
}

const CHECKLIST_STEPS = [
  { key: "cv", label: "CV & lettre prêts" },
  { key: "applied", label: "Candidature envoyée" },
  { key: "relance", label: "Relance envoyée" },
  { key: "test", label: "Test technique" },
  { key: "entretien", label: "Entretien" },
  { key: "reponse", label: "Réponse reçue" },
];

export function OfferDetail({ offerId, onClose, onChanged, onEdit, onOpenFull }: Props) {
  const [data, setData] = useState<OfferDetailType | null>(null);
  const [generating, setGenerating] = useState(false);
  const [tracking, setTracking] = useState<OfferTracking>({});
  const [checklist, setChecklist] = useState<Record<string, boolean>>({});
  const [preview, setPreview] = useState<{ tab: "cv" | "letter"; cv: string; letter: string } | null>(null);

  const reload = () => {
    getOffer(offerId).then(setData).catch(console.error);
  };

  useEffect(() => {
    setData(null);
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offerId]);

  // Synchronise le brouillon de suivi quand l'offre chargée change
  useEffect(() => {
    if (data?.offer) {
      setTracking({
        applied_at: data.offer.applied_at ?? "",
        follow_up_at: data.offer.follow_up_at ?? "",
        notes: data.offer.notes ?? "",
        contact: data.offer.contact ?? "",
      });
      setChecklist(data.offer.checklist ?? {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.offer?.id]);

  const toggleCheck = (key: string) => {
    const next = { ...checklist, [key]: !checklist[key] };
    setChecklist(next);
    updateOfferTracking(offerId, { checklist: next }).then(onChanged).catch(console.error);
  };

  const openPreview = async (tab: "cv" | "letter") => {
    try {
      const [cv, letter] = await Promise.all([
        getGeneratedCV(offerId),
        getGeneratedLetter(offerId),
      ]);
      setPreview({ tab, cv: cv.html, letter: letter.markdown });
    } catch (e) {
      alert("Aperçu indisponible : " + (e instanceof Error ? e.message : e));
    }
  };

  const copyCvText = async () => {
    try {
      const { html } = await getGeneratedCV(offerId);
      const text = new DOMParser().parseFromString(html, "text/html").body.textContent || "";
      await navigator.clipboard.writeText(text.replace(/\n{3,}/g, "\n\n").trim());
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      alert("Copie impossible : " + (e instanceof Error ? e.message : e));
    }
  };

  const commitTracking = async () => {
    try {
      await updateOfferTracking(offerId, tracking);
      onChanged();
    } catch (e) {
      console.error(e);
    }
  };

  const [copied, setCopied] = useState(false);
  const copyLetter = async () => {
    try {
      const { markdown } = await getGeneratedLetter(offerId);
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      alert("Impossible de copier la lettre : " + (e instanceof Error ? e.message : e));
    }
  };

  const markApplied = async () => {
    try {
      await setOfferStatus(offerId, "applied");
      reload();
      onChanged();
    } catch (e) {
      console.error(e);
    }
  };

  if (!data) {
    return (
      <div className="w-[480px] shrink-0 border-l border-outline-variant bg-surface-lowest p-6 text-body-md text-on-surface-variant">
        Chargement…
      </div>
    );
  }

  const { offer, docs } = data;
  const color = scoreColor(offer.score);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await generateOffer(offer.id);
      reload();
      onChanged();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setGenerating(false);
    }
  };

  const handleFav = async () => {
    await setFavorite(offer.id, !offer.is_favorite);
    reload();
    onChanged();
  };

  const handleHide = async () => {
    if (!confirm("Masquer cette offre ?")) return;
    await hideOffer(offer.id);
    onChanged();
    onClose();
  };

  return (
    <aside className="w-[480px] shrink-0 border-l border-outline-variant bg-surface-lowest flex flex-col overflow-hidden shadow-level-3">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-outline-variant">
        <button
          onClick={onClose}
          className="p-1 rounded text-on-surface-variant hover:text-on-surface hover:bg-surface-c"
        >
          <X size={16} />
        </button>
        <span className="badge badge-neutral">{SOURCE_LABEL[offer.source]}</span>
        <button
          onClick={() => onOpenFull(offer.id)}
          className="inline-flex items-center gap-1 text-label-sm text-tertiary hover:underline"
          title="Ouvrir en pleine page (fiche entreprise, prépa entretien)"
        >
          <Maximize2 size={12} /> Ouvrir en grand
        </button>
        <a
          href={offer.url}
          target="_blank"
          rel="noreferrer"
          className="ml-auto inline-flex items-center gap-1 text-label-sm text-tertiary hover:underline"
        >
          Voir l'offre <ExternalLink size={12} />
        </a>
      </div>

      <div className="overflow-y-auto flex-1 p-5">
        <div className="flex items-start gap-3 mb-4">
          <div
            className={cn(
              "shrink-0 w-14 h-14 rounded-lg flex items-center justify-center ring-1",
              color.bg,
              color.text,
              color.ring
            )}
          >
            <span className="text-headline-md tabular-nums">
              {offer.score}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-headline-md text-[20px] leading-snug text-on-surface">
              {offer.title}
            </h2>
            <div className="mt-1 text-body-md text-on-surface-variant">
              {offer.company && <span>{offer.company}</span>}
              {offer.location && (
                <>
                  {offer.company && <span className="text-outline-variant"> · </span>}
                  <span>{offer.location}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 flex-wrap mb-4">
          {offer.contract && (
            <span className="badge badge-info">{offer.contract}</span>
          )}
          {offer.salary && (
            <span className="badge badge-neutral">{offer.salary}</span>
          )}
        </div>

        <div className="flex items-center gap-2 mb-5">
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="btn-primary btn-sm"
          >
            <RefreshCw
              size={14}
              className={generating ? "animate-spin" : ""}
            />
            {docs ? "Régénérer" : "Générer candidature"}
          </button>
          {docs && (
            <>
              <button
                onClick={() => onEdit(offer.id)}
                className="btn-secondary btn-sm"
              >
                <Pencil size={14} /> Éditer
              </button>
              <a
                href={downloadCVPdfUrl(offer.id)}
                target="_blank"
                rel="noreferrer"
                className="btn-secondary btn-sm"
              >
                <Download size={14} /> CV PDF
              </a>
              <a
                href={downloadLetterPdfUrl(offer.id)}
                target="_blank"
                rel="noreferrer"
                className="btn-secondary btn-sm"
              >
                <Download size={14} /> Lettre PDF
              </a>
            </>
          )}
          <button
            onClick={handleFav}
            className="ml-auto p-1.5 rounded text-on-surface-variant hover:text-secondary hover:bg-surface-c"
            aria-label="Sauvegarder"
          >
            <Star
              size={16}
              fill={offer.is_favorite ? "currentColor" : "none"}
              className={offer.is_favorite ? "text-secondary" : ""}
            />
          </button>
          <button
            onClick={handleHide}
            className="p-1.5 rounded text-on-surface-variant hover:text-on-surface hover:bg-surface-c"
            aria-label="Masquer"
            title="Masquer cette offre"
          >
            <EyeOff size={16} />
          </button>
        </div>

        {/* Workflow postuler en 1 clic */}
        <div className="flex items-center gap-2 mb-5 flex-wrap">
          {!["applied", "interview", "accepted"].includes(offer.application_status || "") && (
            <button onClick={markApplied} className="btn-success btn-sm" title="Marquer comme postulé (passe en suivi)">
              <Send size={14} /> Marquer postulé
            </button>
          )}
          {docs && (
            <>
              <button onClick={() => openPreview("cv")} className="btn-secondary btn-sm">
                <Eye size={14} /> Aperçu
              </button>
              <button onClick={copyLetter} className="btn-secondary btn-sm">
                {copied ? <Check size={14} /> : <Copy size={14} />}
                {copied ? "Copié !" : "Copier la lettre"}
              </button>
              <button onClick={copyCvText} className="btn-secondary btn-sm">
                <Copy size={14} /> Copier le CV
              </button>
            </>
          )}
          {offer.contact && offer.contact.includes("@") && (
            <a
              href={`mailto:${offer.contact}?subject=${encodeURIComponent(
                "Candidature alternance — " + offer.title
              )}`}
              className="btn-secondary btn-sm"
            >
              <Mail size={14} /> Écrire au recruteur
            </a>
          )}
        </div>

        {offer.is_favorite && (
          <Section title="Suivi de candidature">
            <div className="space-y-2.5">
              <div className="grid grid-cols-2 gap-2">
                <label className="block">
                  <span className="text-label-sm text-on-surface-variant">Postulé le</span>
                  <input
                    type="date"
                    value={tracking.applied_at || ""}
                    onChange={(e) => setTracking((t) => ({ ...t, applied_at: e.target.value }))}
                    onBlur={commitTracking}
                    className="input h-9 w-full mt-0.5"
                  />
                </label>
                <label className="block">
                  <span className="text-label-sm text-on-surface-variant">Relance prévue</span>
                  <input
                    type="date"
                    value={tracking.follow_up_at || ""}
                    onChange={(e) => setTracking((t) => ({ ...t, follow_up_at: e.target.value }))}
                    onBlur={commitTracking}
                    className="input h-9 w-full mt-0.5"
                  />
                </label>
              </div>
              <label className="block">
                <span className="text-label-sm text-on-surface-variant">Contact recruteur</span>
                <input
                  type="text"
                  placeholder="email ou nom"
                  value={tracking.contact || ""}
                  onChange={(e) => setTracking((t) => ({ ...t, contact: e.target.value }))}
                  onBlur={commitTracking}
                  className="input h-9 w-full mt-0.5"
                />
              </label>
              <label className="block">
                <span className="text-label-sm text-on-surface-variant">Notes</span>
                <textarea
                  rows={3}
                  placeholder="Numéro d'annonce, ressenti d'entretien, prochaine étape…"
                  value={tracking.notes || ""}
                  onChange={(e) => setTracking((t) => ({ ...t, notes: e.target.value }))}
                  onBlur={commitTracking}
                  className="input h-auto w-full mt-0.5 py-2 resize-y"
                />
              </label>

              <div>
                <span className="text-label-sm text-on-surface-variant">Étapes</span>
                <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-1">
                  {CHECKLIST_STEPS.map((s) => {
                    const done = !!checklist[s.key];
                    return (
                      <button
                        key={s.key}
                        onClick={() => toggleCheck(s.key)}
                        className="flex items-center gap-1.5 text-left text-[13px] text-on-surface py-0.5"
                      >
                        {done ? (
                          <CheckSquare size={15} className="text-secondary shrink-0" />
                        ) : (
                          <Square size={15} className="text-on-surface-variant shrink-0" />
                        )}
                        <span className={done ? "line-through text-on-surface-variant" : ""}>
                          {s.label}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </Section>
        )}

        {offer.company && (
          <CompanyCard offerId={offer.id} company={offer.company} />
        )}

        <InterviewPrep offerId={offer.id} title={offer.title} />

        {offer.reasoning && (
          <Section title="Analyse">
            <p className="text-body-md text-[13px] leading-relaxed text-on-surface-variant">
              {offer.reasoning}
            </p>
          </Section>
        )}

        {offer.skills.length > 0 && (
          <Section title="Compétences identifiées">
            <ul className="list-check space-y-1.5">
              {offer.skills.map((s) => (
                <li key={s} className="text-[13px]">
                  {s}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {offer.red_flags.length > 0 && (
          <Section title="Points d'attention">
            <ul className="space-y-1">
              {offer.red_flags.map((r, i) => (
                <li
                  key={i}
                  className="flex items-start gap-1.5 text-body-md text-[13px] text-on-error-container"
                >
                  <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        <Section title="Description">
          <div className="text-body-md text-[13px] leading-relaxed text-on-surface-variant whitespace-pre-wrap">
            {offer.description || "—"}
          </div>
        </Section>

        {docs && (
          <Section title="Fichiers générés">
            <div className="text-[12px] text-on-surface-variant font-mono break-all space-y-1">
              <div>{docs.adapted_cv_path}</div>
              <div>{docs.letter_path}</div>
            </div>
          </Section>
        )}
      </div>

      {preview && (
        <div
          className="fixed inset-0 z-50 bg-on-surface/40 flex items-center justify-center p-4"
          onClick={() => setPreview(null)}
        >
          <div
            className="card w-full max-w-3xl h-[85vh] flex flex-col shadow-level-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-outline-variant">
              <button
                onClick={() => setPreview((p) => p && { ...p, tab: "cv" })}
                className={preview.tab === "cv" ? "btn-primary btn-sm" : "btn-ghost btn-sm"}
              >
                CV
              </button>
              <button
                onClick={() => setPreview((p) => p && { ...p, tab: "letter" })}
                className={preview.tab === "letter" ? "btn-primary btn-sm" : "btn-ghost btn-sm"}
              >
                Lettre
              </button>
              <button onClick={() => setPreview(null)} className="ml-auto p-1.5 rounded hover:bg-surface-c">
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 overflow-hidden bg-surface-container-low">
              {preview.tab === "cv" ? (
                <iframe title="Aperçu CV" srcDoc={preview.cv} className="w-full h-full bg-white" />
              ) : (
                <div className="h-full overflow-y-auto p-6">
                  <div className="max-w-2xl mx-auto bg-surface-lowest border border-outline-variant rounded-lg p-6 text-body-md text-on-surface whitespace-pre-wrap">
                    {preview.letter}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-5">
      <h4 className="section-label mb-2">{title}</h4>
      {children}
    </div>
  );
}
