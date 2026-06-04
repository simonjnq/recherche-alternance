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
    <div className="px-6 py-3 border-b border-neutral-200 bg-gradient-to-r from-white to-neutral-50 flex items-center gap-3 overflow-x-auto">
      <Tile
        icon={<BarChart3 size={14} />}
        label="Total"
        value={stats.total}
        sub="offres scrapées"
      />
      {stats.new_count > 0 && (
        <Tile
          icon={<Sparkles size={14} className="text-emerald-700" />}
          label="Nouvelles"
          value={stats.new_count}
          sub="dernier run"
          tone="emerald"
        />
      )}
      <Tile
        icon={<TrendingUp size={14} className="text-emerald-700" />}
        label="Score ≥ 70"
        value={stats.high_score}
        sub={`moy ${stats.avg_score}`}
        tone="emerald"
      />
      <Tile
        icon={<FileCheck2 size={14} className="text-violet-700" />}
        label="Candidatures"
        value={stats.generated}
        sub="CV+lettre"
        tone="violet"
      />
      <div className="h-8 w-px bg-neutral-200" />
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[11px] uppercase tracking-wide text-neutral-500 font-medium pl-1">
          Sources
        </span>
        {stats.by_source.map((s) => (
          <span
            key={s.source}
            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-white border border-neutral-200"
            title={`${s.count} offres · score moyen ${s.avg_score}`}
          >
            <Globe2 size={10} className="text-neutral-400" />
            <span className="text-neutral-700">
              {SOURCE_LABEL[s.source as keyof typeof SOURCE_LABEL] ?? s.source}
            </span>
            <span className="text-neutral-500 tabular-nums">{s.count}</span>
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
  tone?: "emerald" | "violet";
}) {
  const valueClass =
    tone === "emerald"
      ? "text-emerald-700"
      : tone === "violet"
        ? "text-violet-700"
        : "text-neutral-900";
  return (
    <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-white border border-neutral-200">
      <div className="text-neutral-400">{icon}</div>
      <div>
        <div className="flex items-baseline gap-1.5">
          <span className={`text-base font-semibold tabular-nums ${valueClass}`}>
            {value}
          </span>
          <span className="text-[11px] text-neutral-500">{label}</span>
        </div>
        <div className="text-[10px] text-neutral-400 leading-none">{sub}</div>
      </div>
    </div>
  );
}
