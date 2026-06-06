import { useEffect, useMemo, useState } from "react";
import { BarChart3, FileCheck2, Sparkles, Clock, TrendingUp } from "lucide-react";
import { getSearchStats, getTimeline, listOffers, type SearchStats } from "../api";
import type { ApplicationStatus, Offer } from "../types";
import { APPLICATION_STATUSES, SOURCE_LABEL } from "../types";
import { cn } from "../lib/utils";

interface Props {
  refreshKey: number;
}

export function StatsView({ refreshKey }: Props) {
  const [stats, setStats] = useState<SearchStats | null>(null);
  const [timeline, setTimeline] = useState<{ day: string; count: number }[]>([]);
  const [favs, setFavs] = useState<Offer[]>([]);

  useEffect(() => {
    getSearchStats().then(setStats).catch(() => setStats(null));
    getTimeline(21).then((t) => setTimeline(t.days)).catch(() => setTimeline([]));
    listOffers({ favorites_only: true, limit: 500 }).then(setFavs).catch(() => setFavs([]));
  }, [refreshKey]);

  const funnel = useMemo(() => {
    const m: Record<ApplicationStatus, number> = {
      to_apply: 0, applied: 0, interview: 0, accepted: 0, rejected: 0,
    };
    for (const o of favs) m[(o.application_status as ApplicationStatus) || "to_apply"]++;
    return m;
  }, [favs]);

  const maxDay = Math.max(1, ...timeline.map((d) => d.count));
  const maxSrc = Math.max(1, ...(stats?.by_source.map((s) => s.count) ?? [1]));

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-container mx-auto">
        <h1 className="text-headline-lg text-[28px] text-on-surface mb-5">Statistiques</h1>

        {/* Tuiles */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          <Tile icon={<BarChart3 size={16} />} label="Offres" value={stats?.total ?? 0} sub="visibles" />
          <Tile icon={<TrendingUp size={16} className="text-secondary" />} label="Score ≥ 70" value={stats?.high_score ?? 0} sub={`moy ${stats?.avg_score ?? 0}`} tone="success" />
          <Tile icon={<Sparkles size={16} className="text-secondary" />} label="Nouvelles" value={stats?.new_count ?? 0} sub="dernier run" tone="success" />
          <Tile icon={<FileCheck2 size={16} className="text-tertiary" />} label="Candidatures" value={stats?.generated ?? 0} sub="CV+lettre" tone="info" />
          <Tile icon={<Clock size={16} className="text-error" />} label="À relancer" value={stats?.overdue_count ?? 0} sub="favoris" tone={stats && stats.overdue_count > 0 ? "error" : undefined} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Entonnoir candidatures */}
          <section className="card p-4">
            <h2 className="section-label mb-3">Entonnoir candidatures</h2>
            <div className="space-y-2">
              {APPLICATION_STATUSES.map((s) => {
                const n = funnel[s.key];
                const pct = favs.length ? Math.round((n / favs.length) * 100) : 0;
                return (
                  <div key={s.key} className="flex items-center gap-2">
                    <span className="w-24 text-label-sm text-on-surface-variant shrink-0">{s.label}</span>
                    <div className="flex-1 h-5 rounded bg-surface-container overflow-hidden">
                      <div className={cn("h-full rounded", s.dot)} style={{ width: `${pct}%` }} />
                    </div>
                    <span className="w-8 text-right text-label-md tabular-nums">{n}</span>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Qualité par source */}
          <section className="card p-4">
            <h2 className="section-label mb-3">Par source</h2>
            <div className="space-y-2">
              {(stats?.by_source ?? []).map((s) => (
                <div key={s.source} className="flex items-center gap-2">
                  <span className="w-36 text-label-sm text-on-surface-variant shrink-0 truncate">
                    {SOURCE_LABEL[s.source as keyof typeof SOURCE_LABEL] ?? s.source}
                  </span>
                  <div className="flex-1 h-5 rounded bg-surface-container overflow-hidden">
                    <div className="h-full rounded bg-tertiary" style={{ width: `${(s.count / maxSrc) * 100}%` }} />
                  </div>
                  <span className="w-8 text-right text-label-md tabular-nums">{s.count}</span>
                  <span className="w-14 text-right text-label-sm text-on-surface-variant">moy {s.avg_score}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Offres par jour */}
          <section className="card p-4 lg:col-span-2">
            <h2 className="section-label mb-3">Offres par jour (21 j)</h2>
            {timeline.length === 0 ? (
              <p className="text-body-md text-on-surface-variant">Pas encore de données.</p>
            ) : (
              <div className="flex items-end gap-1 h-32">
                {timeline.map((d) => (
                  <div key={d.day} className="flex-1 flex flex-col items-center justify-end gap-1" title={`${d.day} : ${d.count}`}>
                    <div className="w-full rounded-t bg-tertiary" style={{ height: `${(d.count / maxDay) * 100}%` }} />
                    <span className="text-[9px] text-on-surface-variant">{d.day.slice(8)}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        {stats?.last_run && (
          <p className="mt-4 text-label-sm text-on-surface-variant">
            Dernier run : {stats.last_run.finished_at?.slice(0, 16).replace("T", " ") || stats.last_run.status}
            {stats.last_run.stats?.scored != null && ` · ${stats.last_run.stats.scored} offres analysées`}
            {stats.last_run.stats?.dropped_irrelevant != null && ` · ${stats.last_run.stats.dropped_irrelevant} hors-domaine écartées`}
          </p>
        )}
      </div>
    </div>
  );
}

function Tile({
  icon, label, value, sub, tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  sub: string;
  tone?: "success" | "info" | "error";
}) {
  const c = tone === "success" ? "text-secondary" : tone === "info" ? "text-tertiary" : tone === "error" ? "text-error" : "text-on-surface";
  return (
    <div className="card p-3">
      <div className="flex items-center gap-2 text-on-surface-variant mb-1">{icon}<span className="text-label-sm">{label}</span></div>
      <div className={cn("text-headline-md tabular-nums", c)}>{value}</div>
      <div className="text-[10px] text-on-surface-variant">{sub}</div>
    </div>
  );
}
