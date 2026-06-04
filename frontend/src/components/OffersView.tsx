import { useEffect, useMemo, useState } from "react";
import { Search, Sparkles } from "lucide-react";
import { listOffers } from "../api";
import type { Offer, Source } from "../types";
import { SOURCES } from "../types";
import { OfferCard } from "./OfferCard";
import { OfferDetail } from "./OfferDetail";
import { StatsBar } from "./StatsBar";

interface Props {
  favoritesOnly: boolean;
  refreshKey: number;
  onEdit: (offerId: number) => void;
}

const SCORE_OPTIONS = [
  { value: 0, label: "Tous" },
  { value: 50, label: "≥ 50" },
  { value: 70, label: "≥ 70" },
  { value: 85, label: "≥ 85" },
];

export function OffersView({ favoritesOnly, refreshKey, onEdit }: Props) {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [source, setSource] = useState<Source | "">("");
  const [newOnly, setNewOnly] = useState(false);

  const params = useMemo(
    () => ({
      favorites_only: favoritesOnly,
      min_score: minScore,
      source: source || undefined,
      search: search || undefined,
      new_only: newOnly || undefined,
    }),
    [favoritesOnly, minScore, source, search, newOnly]
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const t = window.setTimeout(() => {
      listOffers(params)
        .then((data) => {
          if (!cancelled) {
            setOffers(data);
            setLoading(false);
          }
        })
        .catch((e) => {
          console.error(e);
          if (!cancelled) setLoading(false);
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [params, refreshKey]);

  const refreshList = () => {
    listOffers(params).then(setOffers).catch(console.error);
  };

  const selected = offers.find((o) => o.id === selectedId) ?? null;

  return (
    <div className="flex h-full min-h-0">
      <div className="flex-1 flex flex-col min-w-0">
        {!favoritesOnly && <StatsBar refreshKey={refreshKey} />}
        <div className="px-6 py-4 border-b border-neutral-200 bg-white flex items-center gap-3">
          <div className="relative flex-1 max-w-md">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400"
            />
            <input
              type="text"
              placeholder="Rechercher titre, entreprise…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-sm border border-neutral-200 rounded-md focus:outline-none focus:ring-2 focus:ring-neutral-900/10 focus:border-neutral-400"
            />
          </div>
          <select
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="text-sm border border-neutral-200 rounded-md px-2.5 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-neutral-900/10"
          >
            {SCORE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                Score {o.label}
              </option>
            ))}
          </select>
          <select
            value={source}
            onChange={(e) => setSource(e.target.value as Source | "")}
            className="text-sm border border-neutral-200 rounded-md px-2.5 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-neutral-900/10"
          >
            <option value="">Toutes sources</option>
            {SOURCES.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setNewOnly((v) => !v)}
            className={
              "inline-flex items-center gap-1.5 text-sm rounded-md px-2.5 py-1.5 border transition-colors " +
              (newOnly
                ? "bg-emerald-600 border-emerald-600 text-white"
                : "bg-white border-neutral-200 text-neutral-600 hover:border-neutral-300")
            }
            title="N'afficher que les offres trouvées au dernier lancement"
          >
            <Sparkles size={13} />
            Nouvelles
          </button>
          <div className="ml-auto text-sm text-neutral-500">
            {offers.length} offre{offers.length > 1 ? "s" : ""}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="text-sm text-neutral-500">Chargement…</div>
          ) : offers.length === 0 ? (
            <EmptyState favoritesOnly={favoritesOnly} />
          ) : (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 max-w-6xl">
              {offers.map((o) => (
                <OfferCard
                  key={o.id}
                  offer={o}
                  selected={selectedId === o.id}
                  onSelect={() => setSelectedId(o.id)}
                  onChanged={refreshList}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {selected && (
        <OfferDetail
          offerId={selected.id}
          onClose={() => setSelectedId(null)}
          onChanged={refreshList}
          onEdit={onEdit}
        />
      )}
    </div>
  );
}

function EmptyState({ favoritesOnly }: { favoritesOnly: boolean }) {
  return (
    <div className="max-w-md mx-auto text-center py-20">
      <div className="w-12 h-12 mx-auto rounded-full bg-neutral-100 flex items-center justify-center mb-4">
        <Search size={20} className="text-neutral-400" />
      </div>
      <h3 className="font-medium text-neutral-900 mb-1">
        {favoritesOnly ? "Aucun favori" : "Aucune offre"}
      </h3>
      <p className="text-sm text-neutral-500">
        {favoritesOnly
          ? "Marque des offres en favori pour les retrouver ici."
          : "Clique sur « Lancer la recherche » dans la barre latérale."}
      </p>
    </div>
  );
}
