import { useEffect, useState } from "react";
import { BarChart3, FileCheck2, Globe2, Sparkles, TrendingUp } from "lucide-react";
import { getSearchStats, type SearchStats } from "../api";
import { SOURCE_LABEL } from "../types";

interface Props {
  refreshKey: number;
}

export function StatsBar({ refreshKey }: Props) {
  const [stats, setStats] = useState<SearchStats | null>(null);

  useEffect(() => {
    getSearchStats().then(setStats).catch(() => setStats(null));
  }, [refreshKey]);

  if (!stats || stats.total === 0) return null;

  return (
    <div className="px-6 py-3 border-b border-outline-variant bg-surface-container-low flex items-center gap-3 overflow-x-auto">
      <Tile
        icon={<BarChart3 size={14} />}
        label="Total"
        value={stats.total}
        sub="offres scrapées"
      />
      {stats.new_count > 0 && (
        <Tile
          icon={<Sparkles size={14} className="text-secondary" />}
          label="Nouvelles"
          value={stats.new_count}
          sub="dernier run"
          tone="success"
        />
      )}
      <Tile
        icon={<TrendingUp size={14} className="text-secondary" />}
        label="Score ≥ 70"
        value={stats.high_score}
        sub={`moy ${stats.avg_score}`}
        tone="success"
      />
      <Tile
        icon={<FileCheck2 size={14} className="text-tertiary" />}
        label="Candidatures"
        value={stats.generated}
        sub="CV+lettre"
        tone="info"
      />
      <div className="h-8 w-px bg-outline-variant" />
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="section-label pl-1">Sources</span>
        {stats.by_source.map((s) => (
          <span
            key={s.source}
            className="inline-flex items-center gap-1 badge bg-surface-lowest border border-outline-variant"
            title={`${s.count} offres · score moyen ${s.avg_score}`}
          >
            <Globe2 size={10} className="text-on-surface-variant" />
            <span className="text-on-surface">
              {SOURCE_LABEL[s.source as keyof typeof SOURCE_LABEL] ?? s.source}
            </span>
            <span className="text-on-surface-variant tabular-nums">{s.count}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function Tile({
  icon,
  label,
  value,
  sub,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  sub: string;
  tone?: "success" | "info";
}) {
  const valueClass =
    tone === "success"
      ? "text-secondary"
      : tone === "info"
        ? "text-tertiary"
        : "text-on-surface";
  return (
    <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-surface-lowest border border-outline-variant">
      <div className="text-on-surface-variant">{icon}</div>
      <div>
        <div className="flex items-baseline gap-1.5">
          <span className={`text-body-lg font-bold tabular-nums ${valueClass}`}>
            {value}
          </span>
          <span className="text-label-sm text-on-surface-variant">{label}</span>
        </div>
        <div className="text-[10px] text-on-surface-variant leading-none">{sub}</div>
      </div>
    </div>
  );
}
