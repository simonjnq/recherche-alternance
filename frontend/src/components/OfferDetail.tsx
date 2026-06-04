import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Download,
  ExternalLink,
  EyeOff,
  Pencil,
  RefreshCw,
  Star,
  X,
} from "lucide-react";
import {
  downloadCVPdfUrl,
  downloadLetterPdfUrl,
  generateOffer,
  getOffer,
  hideOffer,
  setFavorite,
} from "../api";
import type { OfferDetail as OfferDetailType } from "../types";
import { SOURCE_LABEL } from "../types";
import { cn, scoreColor } from "../lib/utils";

interface Props {
  offerId: number;
  onClose: () => void;
  onChanged: () => void;
  onEdit: (offerId: number) => void;
}

export function OfferDetail({ offerId, onClose, onChanged, onEdit }: Props) {
  const [data, setData] = useState<OfferDetailType | null>(null);
  const [generating, setGenerating] = useState(false);

  const reload = () => {
    getOffer(offerId).then(setData).catch(console.error);
  };

  useEffect(() => {
    setData(null);
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offerId]);

  if (!data) {
    return (
      <div className="w-[480px] shrink-0 border-l border-neutral-200 bg-white p-6 text-sm text-neutral-500">
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
    <aside className="w-[480px] shrink-0 border-l border-neutral-200 bg-white flex flex-col overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-neutral-200">
        <button
          onClick={onClose}
          className="p-1 text-neutral-500 hover:text-neutral-900"
        >
          <X size={16} />
        </button>
        <span className="text-[13px] text-neutral-500">
          {SOURCE_LABEL[offer.source]}
        </span>
        <a
          href={offer.url}
          target="_blank"
          rel="noreferrer"
          className="ml-auto inline-flex items-center gap-1 text-[13px] text-neutral-600 hover:text-neutral-900"
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
            <span className="text-xl font-semibold tabular-nums">
              {offer.score}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="font-semibold text-[17px] leading-snug">
              {offer.title}
            </h2>
            <div className="mt-1 text-sm text-neutral-600">
              {offer.company && <span>{offer.company}</span>}
              {offer.location && (
                <>
                  {offer.company && <span className="text-neutral-300"> · </span>}
                  <span>{offer.location}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 flex-wrap mb-4 text-xs">
          {offer.contract && (
            <span className="px-2 py-0.5 rounded bg-neutral-100 text-neutral-700">
              {offer.contract}
            </span>
          )}
          {offer.salary && (
            <span className="px-2 py-0.5 rounded bg-neutral-100 text-neutral-700">
              {offer.salary}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 mb-5">
          <button
            onClick={handleGenerate}
            disabled={generating}
            className={cn(
              "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium",
              generating
                ? "bg-neutral-200 text-neutral-500 cursor-not-allowed"
                : "bg-neutral-900 text-white hover:bg-neutral-800"
            )}
          >
            <RefreshCw
              size={13}
              className={generating ? "animate-spin" : ""}
            />
            {docs ? "Régénérer" : "Générer candidature"}
          </button>
          {docs && (
            <>
              <button
                onClick={() => onEdit(offer.id)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm border border-neutral-200 hover:border-neutral-400 bg-white"
              >
                <Pencil size={13} /> Éditer
              </button>
              <a
                href={downloadCVPdfUrl(offer.id)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm border border-neutral-200 hover:border-neutral-400 bg-white"
              >
                <Download size={13} /> CV PDF
              </a>
              <a
                href={downloadLetterPdfUrl(offer.id)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm border border-neutral-200 hover:border-neutral-400 bg-white"
              >
                <Download size={13} /> Lettre PDF
              </a>
            </>
          )}
          <button
            onClick={handleFav}
            className="ml-auto p-1.5 text-neutral-500 hover:text-amber-500"
            aria-label="Favori"
          >
            <Star
              size={15}
              fill={offer.is_favorite ? "currentColor" : "none"}
              className={offer.is_favorite ? "text-amber-500" : ""}
            />
          </button>
          <button
            onClick={handleHide}
            className="p-1.5 text-neutral-500 hover:text-neutral-900"
            aria-label="Masquer"
            title="Masquer cette offre"
          >
            <EyeOff size={15} />
          </button>
        </div>

        {offer.reasoning && (
          <Section title="Analyse">
            <p className="text-[13px] leading-relaxed text-neutral-700">
              {offer.reasoning}
            </p>
          </Section>
        )}

        {offer.skills.length > 0 && (
          <Section title="Compétences identifiées">
            <div className="flex flex-wrap gap-1.5">
              {offer.skills.map((s) => (
                <span
                  key={s}
                  className="text-xs px-2 py-0.5 rounded bg-neutral-100 text-neutral-700"
                >
                  {s}
                </span>
              ))}
            </div>
          </Section>
        )}

        {offer.red_flags.length > 0 && (
          <Section title="Points d'attention">
            <ul className="space-y-1">
              {offer.red_flags.map((r, i) => (
                <li
                  key={i}
                  className="flex items-start gap-1.5 text-[13px] text-red-700"
                >
                  <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        <Section title="Description">
          <div className="text-[13px] leading-relaxed text-neutral-700 whitespace-pre-wrap">
            {offer.description || "—"}
          </div>
        </Section>

        {docs && (
          <Section title="Fichiers générés">
            <div className="text-[12px] text-neutral-500 font-mono break-all space-y-1">
              <div>{docs.adapted_cv_path}</div>
              <div>{docs.letter_path}</div>
            </div>
          </Section>
        )}
      </div>
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
      <h4 className="text-[11px] uppercase tracking-wide text-neutral-500 font-medium mb-2">
        {title}
      </h4>
      {children}
    </div>
  );
}
