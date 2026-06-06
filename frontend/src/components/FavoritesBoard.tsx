import { useEffect, useMemo, useState } from "react";
import { MapPin, Star, GripVertical, Clock, Download } from "lucide-react";
import { listOffers, setOfferStatus, exportCsvUrl, reorderOffers } from "../api";
import type { ApplicationStatus, Offer } from "../types";
import { APPLICATION_STATUSES, SOURCE_LABEL } from "../types";
import { cn, scoreColor } from "../lib/utils";
import { OfferDetail } from "./OfferDetail";

interface Props {
  refreshKey: number;
  onEdit: (offerId: number) => void;
}

function statusOf(o: Offer): ApplicationStatus {
  return (o.application_status as ApplicationStatus) || "to_apply";
}

function isOverdue(o: Offer): boolean {
  if (!o.follow_up_at) return false;
  const s = statusOf(o);
  if (s === "accepted" || s === "rejected") return false;
  const today = new Date().toISOString().slice(0, 10);
  return o.follow_up_at <= today;
}

export function FavoritesBoard({ refreshKey, onEdit }: Props) {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draggingId, setDraggingId] = useState<number | null>(null);
  const [overCol, setOverCol] = useState<ApplicationStatus | null>(null);

  const load = () => {
    listOffers({ favorites_only: true, limit: 500 })
      .then((data) => {
        setOffers(data);
        setLoading(false);
      })
      .catch((e) => {
        console.error(e);
        setLoading(false);
      });
  };

  useEffect(() => {
    setLoading(true);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  const byStatus = useMemo(() => {
    const m: Record<ApplicationStatus, Offer[]> = {
      to_apply: [], applied: [], interview: [], accepted: [], rejected: [],
    };
    for (const o of offers) m[statusOf(o)].push(o);
    // Ordre manuel (board_order) en priorité ; le reste garde l'ordre d'arrivée (score)
    for (const k of Object.keys(m) as ApplicationStatus[]) {
      m[k].sort((a, b) => (a.board_order ?? Infinity) - (b.board_order ?? Infinity));
    }
    return m;
  }, [offers]);

  const applyReorder = async (col: ApplicationStatus, newIds: number[]) => {
    setOffers((prev) =>
      prev.map((o) => {
        const i = newIds.indexOf(o.id);
        return i === -1 ? o : { ...o, application_status: col, board_order: i };
      })
    );
    const dragged = offers.find((o) => o.id === draggingId);
    try {
      if (dragged && statusOf(dragged) !== col && draggingId != null) {
        await setOfferStatus(draggingId, col);
      }
      await reorderOffers(newIds);
    } catch (e) {
      console.error(e);
      load();
    }
    setDraggingId(null);
    setOverCol(null);
  };

  const dropOnCard = (target: Offer) => {
    if (draggingId == null || draggingId === target.id) return;
    const col = statusOf(target);
    const colCards = byStatus[col].filter((o) => o.id !== draggingId);
    const idx = colCards.findIndex((o) => o.id === target.id);
    const newIds = [
      ...colCards.slice(0, idx).map((o) => o.id),
      draggingId,
      ...colCards.slice(idx).map((o) => o.id),
    ];
    applyReorder(col, newIds);
  };

  const dropOnColumnEnd = (col: ApplicationStatus) => {
    if (draggingId == null) return;
    const newIds = [
      ...byStatus[col].filter((o) => o.id !== draggingId).map((o) => o.id),
      draggingId,
    ];
    applyReorder(col, newIds);
  };

  const selected = offers.find((o) => o.id === selectedId) ?? null;

  // Métriques funnel
  const applied =
    byStatus.applied.length + byStatus.interview.length +
    byStatus.accepted.length + byStatus.rejected.length;
  const responded =
    byStatus.interview.length + byStatus.accepted.length + byStatus.rejected.length;
  const responseRate = applied > 0 ? Math.round((responded / applied) * 100) : null;
  const overdueCount = offers.filter(isOverdue).length;

  return (
    <div className="flex h-full min-h-0">
      <div className="flex-1 flex flex-col min-w-0">
        {/* Dashboard header — compteurs par étape + funnel */}
        <div className="px-6 py-3 border-b border-outline-variant bg-surface-container-low flex items-center gap-2 overflow-x-auto">
          <span className="section-label pr-1">Suivi</span>
          {APPLICATION_STATUSES.map((s) => (
            <div
              key={s.key}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-lowest border border-outline-variant"
            >
              <span className={cn("w-2 h-2 rounded-full", s.dot)} />
              <span className="text-label-sm text-on-surface-variant">{s.label}</span>
              <span className="text-label-md text-on-surface tabular-nums">
                {byStatus[s.key].length}
              </span>
            </div>
          ))}
          <div className="h-7 w-px bg-outline-variant mx-1" />
          <div
            className={cn(
              "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border",
              overdueCount > 0
                ? "border-error text-on-error-container"
                : "bg-surface-lowest border-outline-variant text-on-surface-variant"
            )}
            style={overdueCount > 0 ? { background: "var(--error-soft)" } : undefined}
            title="Favoris dont la relance est dépassée"
          >
            <Clock size={12} />
            <span className="text-label-sm">À relancer</span>
            <span className="text-label-md tabular-nums">{overdueCount}</span>
          </div>
          <div
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-lowest border border-outline-variant"
            title="Réponses reçues / candidatures envoyées"
          >
            <span className="text-label-sm text-on-surface-variant">Taux de réponse</span>
            <span className="text-label-md text-on-surface tabular-nums">
              {responseRate === null ? "–" : `${responseRate}%`}
            </span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <a
              href={exportCsvUrl(true)}
              className="btn-secondary btn-sm"
              title="Télécharger le suivi en CSV (Excel/Sheets)"
            >
              <Download size={13} /> Export CSV
            </a>
            <span className="text-label-sm text-on-surface-variant">
              {offers.length} favori{offers.length > 1 ? "s" : ""}
            </span>
          </div>
        </div>

        {loading ? (
          <div className="p-6 text-body-md text-on-surface-variant">Chargement…</div>
        ) : offers.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="flex-1 overflow-x-auto overflow-y-hidden p-4">
            <div className="flex gap-3 h-full min-w-max">
              {APPLICATION_STATUSES.map((col) => (
                <div
                  key={col.key}
                  onDragOver={(e) => {
                    e.preventDefault();
                    if (overCol !== col.key) setOverCol(col.key);
                  }}
                  onDragLeave={() => setOverCol((c) => (c === col.key ? null : c))}
                  onDrop={(e) => {
                    e.preventDefault();
                    setOverCol(null);
                    if (draggingId != null) dropOnColumnEnd(col.key);
                    setDraggingId(null);
                  }}
                  className={cn(
                    "w-[300px] shrink-0 flex flex-col rounded-xl border bg-surface-container-low transition-colors",
                    overCol === col.key
                      ? "border-tertiary bg-tertiary-container"
                      : "border-outline-variant"
                  )}
                >
                  <div className="flex items-center gap-2 px-3 py-2.5 border-b border-outline-variant">
                    <span className={cn("w-2.5 h-2.5 rounded-full", col.dot)} />
                    <span className="text-label-md text-on-surface">{col.label}</span>
                    <span className="ml-auto text-label-sm text-on-surface-variant tabular-nums">
                      {byStatus[col.key].length}
                    </span>
                  </div>
                  <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    {byStatus[col.key].map((o) => (
                      <BoardCard
                        key={o.id}
                        offer={o}
                        selected={selectedId === o.id}
                        dragging={draggingId === o.id}
                        onSelect={() => setSelectedId(o.id)}
                        onDragStart={() => setDraggingId(o.id)}
                        onDragEnd={() => {
                          setDraggingId(null);
                          setOverCol(null);
                        }}
                        onDropCard={() => dropOnCard(o)}
                      />
                    ))}
                    {byStatus[col.key].length === 0 && (
                      <div className="text-label-sm text-on-surface-variant text-center py-6">
                        Déposer ici
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {selected && (
        <OfferDetail
          offerId={selected.id}
          onClose={() => setSelectedId(null)}
          onChanged={load}
          onEdit={onEdit}
        />
      )}
    </div>
  );
}

function BoardCard({
  offer,
  selected,
  dragging,
  onSelect,
  onDragStart,
  onDragEnd,
  onDropCard,
}: {
  offer: Offer;
  selected: boolean;
  dragging: boolean;
  onSelect: () => void;
  onDragStart: () => void;
  onDragEnd: () => void;
  onDropCard: () => void;
}) {
  const color = scoreColor(offer.score);
  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(offer.id));
        onDragStart();
      }}
      onDragEnd={onDragEnd}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onDropCard();
      }}
      onClick={onSelect}
      className={cn(
        "group text-left p-3 cursor-pointer select-none",
        selected ? "card border-navy shadow-level-2" : "card-interactive",
        dragging && "opacity-50"
      )}
    >
      <div className="flex items-start gap-2">
        <GripVertical
          size={14}
          className="mt-0.5 shrink-0 text-outline-variant group-hover:text-on-surface-variant"
        />
        <div
          className={cn(
            "shrink-0 w-9 h-9 rounded-lg flex items-center justify-center ring-1",
            color.bg, color.text, color.ring
          )}
        >
          <span className="text-label-md tabular-nums">{offer.score}</span>
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-label-md text-[13px] text-on-surface line-clamp-2">
            {offer.title}
          </h3>
          <div className="mt-1 flex items-center gap-1 text-label-sm text-on-surface-variant">
            {offer.is_favorite && <Star size={11} className="text-secondary shrink-0" fill="currentColor" />}
            {offer.company && <span className="truncate">{offer.company}</span>}
          </div>
          <div className="mt-1.5 flex items-center gap-1.5 flex-wrap">
            <span className="badge badge-neutral">{SOURCE_LABEL[offer.source]}</span>
            {isOverdue(offer) && (
              <span className="badge badge-error inline-flex items-center gap-0.5">
                <Clock size={10} /> à relancer
              </span>
            )}
            {offer.location && (
              <span className="inline-flex items-center gap-0.5 text-label-sm text-on-surface-variant">
                <MapPin size={10} /> {offer.location}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="max-w-md mx-auto text-center py-20">
      <div className="w-12 h-12 mx-auto rounded-full bg-surface-container flex items-center justify-center mb-4">
        <Star size={20} className="text-secondary" />
      </div>
      <h3 className="text-headline-md text-[18px] text-on-surface mb-1">Aucun favori</h3>
      <p className="text-body-md text-on-surface-variant">
        Marque des offres en favori (★) depuis l'onglet Offres : elles arriveront
        ici dans « À postuler », prêtes à suivre.
      </p>
    </div>
  );
}
