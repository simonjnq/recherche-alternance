import { MapPin, Star, ExternalLink, Trash2, Clock, FileCheck2 } from "lucide-react";
import type { Offer } from "../types";
import { SOURCE_LABEL } from "../types";
import { cn, scoreColor, relativeDays } from "../lib/utils";
import { setFavorite } from "../api";

interface Props {
  offer: Offer;
  selected: boolean;
  onSelect: () => void;
  onChanged: () => void;
  onTrash?: (offer: Offer) => void;
  highlight?: string;
  isDuplicate?: boolean;
  checked?: boolean;
  onCheck?: (checked: boolean) => void;
}

function hl(text: string, q?: string): React.ReactNode {
  const term = (q || "").trim();
  if (!term) return text;
  const esc = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = text.split(new RegExp(`(${esc})`, "ig"));
  return parts.map((p, i) =>
    p.toLowerCase() === term.toLowerCase() ? (
      <mark key={i} className="bg-tertiary-container text-on-tertiary-container rounded px-0.5">
        {p}
      </mark>
    ) : (
      p
    )
  );
}

export function OfferCard({ offer, selected, onSelect, onChanged, onTrash, highlight, isDuplicate, checked, onCheck }: Props) {
  const color = scoreColor(offer.score);

  const toggleFav = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await setFavorite(offer.id, !offer.is_favorite);
    onChanged();
  };

  const trash = (e: React.MouseEvent) => {
    e.stopPropagation();
    onTrash?.(offer);
  };

  return (
    <button
      onClick={onSelect}
      className={cn(
        "text-left p-4 w-full",
        selected
          ? "card border-navy shadow-level-2"
          : "card-interactive",
        offer.seen && !selected && "opacity-60"
      )}
    >
      <div className="flex items-start gap-3">
        {onCheck && (
          <input
            type="checkbox"
            checked={!!checked}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => {
              e.stopPropagation();
              onCheck(e.target.checked);
            }}
            className="mt-1 h-4 w-4 rounded-sm accent-[var(--tertiary)] shrink-0"
            aria-label="Sélectionner"
          />
        )}
        <div
          className={cn(
            "shrink-0 w-12 h-12 rounded-lg flex items-center justify-center ring-1",
            color.bg,
            color.text,
            color.ring
          )}
        >
          <span className="text-body-lg font-bold tabular-nums">
            {offer.score}
          </span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start gap-2">
            <h3 className="text-label-md text-[15px] text-on-surface line-clamp-2 flex-1">
              {offer.is_new && (
                <span className="badge badge-success align-middle mr-1.5 uppercase tracking-wide">
                  Nouveau
                </span>
              )}
              {hl(offer.title, highlight)}
            </h3>
            <div className="shrink-0 flex items-center gap-0.5 -mr-1 -mt-1">
              <button
                onClick={toggleFav}
                className="p-1 text-on-surface-variant hover:text-secondary transition-colors"
                aria-label="Sauvegarder"
              >
                <Star
                  size={16}
                  fill={offer.is_favorite ? "currentColor" : "none"}
                  className={offer.is_favorite ? "text-secondary" : ""}
                />
              </button>
              {onTrash && (
                <button
                  onClick={trash}
                  className="p-1 text-on-surface-variant hover:text-error transition-colors"
                  aria-label="Pas intéressé — masquer"
                  title="Pas intéressé (masquer l'offre)"
                >
                  <Trash2 size={15} />
                </button>
              )}
            </div>
          </div>

          <div className="mt-1 flex items-center gap-1.5 text-body-md text-[13px] text-on-surface-variant">
            {offer.company && <span className="truncate">{hl(offer.company, highlight)}</span>}
            {offer.location && (
              <>
                <span className="text-outline-variant">·</span>
                <MapPin size={12} className="shrink-0" />
                <span className="truncate">{offer.location}</span>
              </>
            )}
          </div>

          <div className="mt-2.5 flex items-center gap-1.5 flex-wrap">
            <span className="badge badge-neutral">{SOURCE_LABEL[offer.source]}</span>
            {(offer.posted_at || offer.scraped_at) && (
              <span className="badge badge-neutral inline-flex items-center gap-0.5">
                <Clock size={10} />
                {relativeDays(offer.posted_at || offer.scraped_at)}
              </span>
            )}
            {offer.has_docs && (
              <span className="badge badge-success inline-flex items-center gap-0.5" title="CV + lettre générés">
                <FileCheck2 size={10} /> CV
              </span>
            )}
            {isDuplicate && (
              <span className="badge badge-neutral" title="Offre probablement en double (même poste/entreprise)">
                doublon ?
              </span>
            )}
            {offer.contract && (
              <span className="badge badge-info">{offer.contract}</span>
            )}
            {offer.skills.slice(0, 3).map((s) => (
              <span
                key={s}
                className="badge bg-surface-container-low text-on-surface-variant ring-1 ring-outline-variant"
              >
                {s}
              </span>
            ))}
            {offer.skills.length > 3 && (
              <span className="text-label-sm text-on-surface-variant">
                +{offer.skills.length - 3}
              </span>
            )}
            <a
              href={offer.url}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="ml-auto text-on-surface-variant hover:text-tertiary"
              aria-label="Ouvrir l'offre"
            >
              <ExternalLink size={14} />
            </a>
          </div>
        </div>
      </div>
    </button>
  );
}
