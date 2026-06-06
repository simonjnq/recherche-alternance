import { useEffect, useMemo, useRef, useState } from "react";
import { Search, Sparkles, Trash2, Undo2 } from "lucide-react";
import { cleanupOffers, hideOffer, listOffers, setFavorite, unhideOffer } from "../api";
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
  const [sort, setSort] = useState<"score" | "recent" | "company">(
    () => (localStorage.getItem("offers_sort") as "score" | "recent" | "company") || "score"
  );
  const [showHelp, setShowHelp] = useState(false);
  useEffect(() => {
    localStorage.setItem("offers_sort", sort);
  }, [sort]);
  const [noDocsOnly, setNoDocsOnly] = useState(false);
  const [contractFilter, setContractFilter] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [daysFilter, setDaysFilter] = useState(0);

  const params = useMemo(
    () => ({
      favorites_only: favoritesOnly,
      min_score: minScore,
      source: source || undefined,
      search: search || undefined,
      new_only: newOnly || undefined,
      sort,
      generated: noDocsOnly ? false : undefined,
      contract: contractFilter || undefined,
      location: locationFilter || undefined,
      days_max: daysFilter || undefined,
    }),
    [favoritesOnly, minScore, source, search, newOnly, sort, noDocsOnly, contractFilter, locationFilter, daysFilter]
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

  // Sélection = marque l'offre comme vue (optimiste local ; serveur l'enregistre à l'ouverture)
  const selectOffer = (id: number) => {
    setSelectedId(id);
    setOffers((prev) => prev.map((o) => (o.id === id ? { ...o, seen: true } : o)));
  };

  // Détection de doublons probables (même entreprise + même début de titre)
  const dupIds = useMemo(() => {
    const firstSeen = new Map<string, number>();
    const dups = new Set<number>();
    for (const o of offers) {
      if (!o.company) continue;
      const key = `${o.company.toLowerCase().trim()}|${o.title
        .toLowerCase()
        .split(/\s+/)
        .slice(0, 4)
        .join(" ")}`;
      const prev = firstSeen.get(key);
      if (prev !== undefined) {
        dups.add(o.id);
        dups.add(prev);
      } else {
        firstSeen.set(key, o.id);
      }
    }
    return dups;
  }, [offers]);

  // --- Sélection multiple + comparateur ---
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [compareOpen, setCompareOpen] = useState(false);
  const toggleCheck = (id: number, on: boolean) =>
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  const clearSelection = () => setSelectedIds(new Set());
  const bulkHide = async () => {
    const ids = [...selectedIds];
    setOffers((prev) => prev.filter((o) => !selectedIds.has(o.id)));
    clearSelection();
    await Promise.all(ids.map((id) => hideOffer(id).catch(console.error)));
  };
  const bulkFav = async () => {
    const ids = [...selectedIds];
    await Promise.all(ids.map((id) => setFavorite(id, true).catch(console.error)));
    clearSelection();
    refreshList();
  };
  const compareOffers = offers.filter((o) => selectedIds.has(o.id));

  const handleCleanup = async (mode: "old" | "unscored") => {
    const label =
      mode === "old"
        ? "les offres de plus de 30 jours"
        : "les offres jamais scorées (score 0)";
    if (!confirm(`Masquer ${label} ? (les favoris sont préservés)`)) return;
    try {
      const r = await cleanupOffers(mode);
      refreshList();
      alert(`${r.hidden} offre(s) masquée(s).`);
    } catch (e) {
      console.error(e);
    }
  };

  // --- Corbeille (masquage) avec annulation ---
  const [trashed, setTrashed] = useState<Offer | null>(null);
  const trashTimer = useRef<number | null>(null);

  const handleTrash = (offer: Offer) => {
    // Retrait optimiste + masquage côté serveur (réversible via "Annuler")
    setOffers((prev) => prev.filter((o) => o.id !== offer.id));
    if (selectedId === offer.id) setSelectedId(null);
    hideOffer(offer.id).catch(console.error);
    setTrashed(offer);
    if (trashTimer.current) window.clearTimeout(trashTimer.current);
    trashTimer.current = window.setTimeout(() => setTrashed(null), 6000);
  };

  const undoTrash = async () => {
    if (!trashed) return;
    if (trashTimer.current) window.clearTimeout(trashTimer.current);
    const o = trashed;
    setTrashed(null);
    try {
      await unhideOffer(o.id);
    } catch (e) {
      console.error(e);
    }
    refreshList();
  };

  // --- Raccourcis clavier : j/k naviguer, f favori, e masquer ---
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      const tag = el?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || el?.isContentEditable) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (!offers.length) return;
      const idx = offers.findIndex((o) => o.id === selectedId);
      if (e.key === "j") {
        e.preventDefault();
        const n = offers[idx < 0 ? 0 : Math.min(offers.length - 1, idx + 1)];
        if (n) selectOffer(n.id);
      } else if (e.key === "k") {
        e.preventDefault();
        const n = offers[idx < 0 ? 0 : Math.max(0, idx - 1)];
        if (n) selectOffer(n.id);
      } else if (e.key === "f" && selectedId != null) {
        const o = offers.find((x) => x.id === selectedId);
        if (o) setFavorite(o.id, !o.is_favorite).then(refreshList).catch(console.error);
      } else if (e.key === "e" && selectedId != null) {
        const o = offers.find((x) => x.id === selectedId);
        if (o) handleTrash(o);
      } else if (e.key === "?") {
        e.preventDefault();
        setShowHelp((v) => !v);
      } else if (e.key === "Escape") {
        setShowHelp(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offers, selectedId]);

  const selected = offers.find((o) => o.id === selectedId) ?? null;

  return (
    <div className="flex h-full min-h-0">
      <div className="flex-1 flex flex-col min-w-0">
        {!favoritesOnly && <StatsBar refreshKey={refreshKey} />}
        <div className="px-6 py-4 border-b border-outline-variant bg-surface-lowest flex flex-wrap items-center gap-x-3 gap-y-2">
          <div className="relative flex-1 max-w-md">
            <Search
              size={15}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant"
            />
            <input
              type="text"
              placeholder="Rechercher titre, entreprise…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input h-9 w-full pl-9"
            />
          </div>
          <select
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="select h-9 text-label-sm"
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
            className="select h-9 text-label-sm"
          >
            <option value="">Toutes sources</option>
            {SOURCES.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as "score" | "recent")}
            className="select h-9 text-label-sm"
            title="Trier les offres"
          >
            <option value="score">Tri : pertinence</option>
            <option value="recent">Tri : récentes</option>
            <option value="company">Tri : entreprise</option>
          </select>
          <select
            value={contractFilter}
            onChange={(e) => setContractFilter(e.target.value)}
            className="select h-9 text-label-sm"
            title="Filtrer par contrat"
          >
            <option value="">Tout contrat</option>
            <option value="altern">Alternance</option>
            <option value="apprent">Apprentissage</option>
          </select>
          <select
            value={daysFilter}
            onChange={(e) => setDaysFilter(Number(e.target.value))}
            className="select h-9 text-label-sm"
            title="Filtrer par fraîcheur"
          >
            <option value={0}>Toutes dates</option>
            <option value={7}>&lt; 7 j</option>
            <option value={14}>&lt; 14 j</option>
            <option value={30}>&lt; 30 j</option>
          </select>
          <input
            type="text"
            placeholder="Lieu…"
            value={locationFilter}
            onChange={(e) => setLocationFilter(e.target.value)}
            className="input h-9 w-28"
          />
          <button
            type="button"
            onClick={() => setNewOnly((v) => !v)}
            className={newOnly ? "btn-success btn-sm" : "btn-secondary btn-sm"}
            title="N'afficher que les offres trouvées au dernier lancement"
          >
            <Sparkles size={14} />
            Nouvelles
          </button>
          <button
            type="button"
            onClick={() => setNoDocsOnly((v) => !v)}
            className={noDocsOnly ? "btn-primary btn-sm" : "btn-secondary btn-sm"}
            title="Offres sans CV/lettre générés"
          >
            Sans candidature
          </button>
          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              onClick={() => handleCleanup("old")}
              className="btn-ghost btn-sm"
              title="Masquer les offres de plus de 30 jours (favoris préservés)"
            >
              <Trash2 size={13} /> Nettoyer
            </button>
            <span className="text-label-sm text-on-surface-variant">
              {offers.length} offre{offers.length > 1 ? "s" : ""}
            </span>
          </div>
        </div>

        {selectedIds.size > 0 && (
          <div className="px-6 py-2 border-b border-outline-variant bg-surface-container flex items-center gap-2">
            <span className="text-label-md text-on-surface">{selectedIds.size} sélectionnée(s)</span>
            <button onClick={bulkFav} className="btn-secondary btn-sm">★ Favori</button>
            <button onClick={bulkHide} className="btn-secondary btn-sm"><Trash2 size={13} /> Masquer</button>
            {selectedIds.size >= 2 && selectedIds.size <= 4 && (
              <button onClick={() => setCompareOpen(true)} className="btn-primary btn-sm">Comparer</button>
            )}
            <button onClick={clearSelection} className="btn-ghost btn-sm ml-auto">Désélectionner</button>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="text-body-md text-on-surface-variant">Chargement…</div>
          ) : offers.length === 0 ? (
            <EmptyState favoritesOnly={favoritesOnly} />
          ) : (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-gutter max-w-container">
              {offers.map((o) => (
                <OfferCard
                  key={o.id}
                  offer={o}
                  selected={selectedId === o.id}
                  onSelect={() => selectOffer(o.id)}
                  onChanged={refreshList}
                  onTrash={handleTrash}
                  highlight={search}
                  isDuplicate={dupIds.has(o.id)}
                  checked={selectedIds.has(o.id)}
                  onCheck={(on) => toggleCheck(o.id, on)}
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

      {compareOpen && compareOffers.length > 0 && (
        <div
          className="fixed inset-0 z-50 bg-on-surface/40 flex items-center justify-center p-4"
          onClick={() => setCompareOpen(false)}
        >
          <div
            className="card w-full max-w-5xl max-h-[85vh] overflow-auto p-5 shadow-level-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center mb-4">
              <h3 className="text-headline-md text-[18px]">Comparer {compareOffers.length} offres</h3>
              <button onClick={() => setCompareOpen(false)} className="ml-auto p-1.5 rounded hover:bg-surface-c">
                <Trash2 size={0} className="hidden" />✕
              </button>
            </div>
            <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${compareOffers.length}, minmax(0,1fr))` }}>
              {compareOffers.map((o) => (
                <div key={o.id} className="card p-3">
                  <div className="text-label-md text-on-surface line-clamp-2 mb-1">{o.title}</div>
                  <div className="text-label-sm text-on-surface-variant mb-2">{o.company} · {o.location}</div>
                  <dl className="space-y-1.5 text-[13px]">
                    <Row k="Score" v={String(o.score)} />
                    <Row k="Contrat" v={o.contract || "—"} />
                    <Row k="Source" v={SOURCES.find((s) => s.key === o.source)?.label || o.source} />
                    <Row k="Compétences" v={(o.skills || []).slice(0, 6).join(", ") || "—"} />
                  </dl>
                  <a href={o.url} target="_blank" rel="noreferrer" className="btn-secondary btn-sm w-full mt-3">Ouvrir</a>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {showHelp && (
        <div
          className="fixed inset-0 z-50 bg-on-surface/30 flex items-center justify-center p-4"
          onClick={() => setShowHelp(false)}
        >
          <div
            className="card p-5 max-w-sm w-full shadow-level-3"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-headline-md text-[18px] text-on-surface mb-3">
              Raccourcis clavier
            </h3>
            <div className="space-y-1.5 text-body-md">
              {[
                ["j", "Offre suivante"],
                ["k", "Offre précédente"],
                ["f", "Favori (★) sur l'offre sélectionnée"],
                ["e", "Masquer l'offre sélectionnée"],
                ["?", "Afficher/masquer cette aide"],
              ].map(([key, desc]) => (
                <div key={key} className="flex items-center gap-3">
                  <kbd className="min-w-[28px] text-center px-1.5 py-0.5 rounded bg-surface-container border border-outline-variant text-label-md">
                    {key}
                  </kbd>
                  <span className="text-on-surface-variant">{desc}</span>
                </div>
              ))}
            </div>
            <button onClick={() => setShowHelp(false)} className="btn-secondary btn-sm mt-4 w-full">
              Fermer
            </button>
          </div>
        </div>
      )}

      {trashed && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-2.5 rounded-lg bg-inverse-surface text-inverse-on-surface shadow-level-3">
          <Trash2 size={15} className="shrink-0" />
          <span className="text-body-md text-[13px] max-w-[280px] truncate">
            Masqué : {trashed.title}
          </span>
          <button
            onClick={undoTrash}
            className="inline-flex items-center gap-1.5 text-label-md text-tertiary hover:underline"
          >
            <Undo2 size={14} /> Annuler
          </button>
        </div>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-on-surface-variant w-24 shrink-0">{k}</dt>
      <dd className="text-on-surface flex-1">{v}</dd>
    </div>
  );
}

function EmptyState({ favoritesOnly }: { favoritesOnly: boolean }) {
  return (
    <div className="max-w-md mx-auto text-center py-20">
      <div className="w-12 h-12 mx-auto rounded-full bg-surface-container flex items-center justify-center mb-4">
        <Search size={20} className="text-tertiary" />
      </div>
      <h3 className="text-headline-md text-[18px] text-on-surface mb-1">
        {favoritesOnly ? "Aucun favori" : "Aucune offre"}
      </h3>
      <p className="text-body-md text-on-surface-variant">
        {favoritesOnly
          ? "Marque des offres en favori pour les retrouver ici."
          : "Clique sur « Lancer la recherche » dans la barre latérale."}
      </p>
    </div>
  );
}
