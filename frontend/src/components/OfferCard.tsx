import { MapPin, Star, ExternalLink } from "lucide-react";
import type { Offer } from "../types";
import { SOURCE_LABEL } from "../types";
import { cn, scoreColor } from "../lib/utils";
import { setFavorite } from "../api";

interface Props {
  offer: Offer;
  selected: boolean;
  onSelect: () => void;
  onChanged: () => void;
}

export function OfferCard({ offer, selected, onSelect, onChanged }: Props) {
  const color = scoreColor(offer.score);

  const toggleFav = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await setFavorite(offer.id, !offer.is_favorite);
    onChanged();
  };

  return (
    <button
      onClick={onSelect}
      className={cn(
        "text-left border rounded-xl bg-white p-4 transition-all",
        selected
          ? "border-neutral-900 shadow-sm"
          : "border-neutral-200 hover:border-neutral-300 hover:shadow-sm"
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "shrink-0 w-12 h-12 rounded-lg flex items-center justify-center ring-1",
            color.bg,
            color.text,
            color.ring
          )}
        >
          <span className="text-base font-semibold tabular-nums">
            {offer.score}
          </span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start gap-2">
            <h3 className="font-medium text-[15px] text-neutral-900 line-clamp-2 flex-1">
              {offer.is_new && (
                <span className="align-middle mr-1.5 text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700">
                  Nouveau
                </span>
              )}
              {offer.title}
            </h3>
            <button
              onClick={toggleFav}
              className="shrink-0 p-1 -mr-1 -mt-1 text-neutral-400 hover:text-amber-500 transition-colors"
              aria-label="Favori"
            >
              <Star
                size={15}
                fill={offer.is_favorite ? "currentColor" : "none"}
                className={offer.is_favorite ? "text-amber-500" : ""}
              />
            </button>
          </div>

          <div className="mt-1 flex items-center gap-1.5 text-[13px] text-neutral-600">
            {offer.company && <span className="truncate">{offer.company}</span>}
            {offer.location && (
              <>
                <span className="text-neutral-300">·</span>
                <MapPin size={11} className="shrink-0" />
                <span className="truncate">{offer.location}</span>
              </>
            )}
          </div>

          <div className="mt-2.5 flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-600 font-medium">
              {SOURCE_LABEL[offer.source]}
            </span>
            {offer.contract && (
              <span className="text-[11px] px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-600">
                {offer.contract}
              </span>
            )}
            {offer.skills.slice(0, 3).map((s) => (
              <span
                key={s}
                className="text-[11px] px-1.5 py-0.5 rounded bg-neutral-50 text-neutral-600 ring-1 ring-neutral-200"
              >
                {s}
              </span>
            ))}
            {offer.skills.length > 3 && (
              <span className="text-[11px] text-neutral-500">
                +{offer.skills.length - 3}
              </span>
            )}
            <a
              href={offer.url}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="ml-auto text-neutral-400 hover:text-neutral-700"
              aria-label="Ouvrir l'offre"
            >
              <ExternalLink size={13} />
            </a>
          </div>
        </div>
      </div>
    </button>
  );
}
