import { AlertCircle, CheckCircle2, Globe2, Loader2 } from "lucide-react";
import type { Progress, SourceProgress } from "../types";
import { SOURCE_LABEL } from "../types";
import { cn } from "../lib/utils";

interface Props {
  progress: Progress | null;
  running: boolean;
}

const STAGE_LABEL: Record<string, string> = {
  scraping: "Scraping des offres",
  scoring: "Analyse & scoring",
  generating: "Génération des candidatures",
  done: "Terminé",
  error: "Erreur",
  idle: "",
};

export function ProgressBar({ progress, running }: Props) {
  if (!progress || progress.stage === "idle") return null;

  const pct =
    progress.total > 0
      ? Math.min(100, Math.round((progress.current / progress.total) * 100))
      : null;
  const isError = progress.stage === "error";
  const isDone = progress.stage === "done";
  const isScraping = progress.stage === "scraping";

  return (
    <div
      className={cn(
        "border-b border-neutral-200",
        isError ? "bg-red-50" : isDone ? "bg-emerald-50" : "bg-neutral-50"
      )}
    >
      <div
        className={cn(
          "px-6 py-2.5 flex items-center gap-3 text-[13px]",
          isError ? "text-red-800" : isDone ? "text-emerald-800" : "text-neutral-700"
        )}
      >
        {running && !isDone && !isError ? (
          <Loader2 size={14} className="animate-spin shrink-0" />
        ) : isError ? (
          <AlertCircle size={14} className="shrink-0" />
        ) : (
          <CheckCircle2 size={14} className="shrink-0" />
        )}
        <span className="font-medium">{STAGE_LABEL[progress.stage]}</span>
        {!isScraping && progress.source && (
          <span className="text-neutral-500">· {progress.source}</span>
        )}
        {pct !== null && !isDone && !isError && (
          <span className="text-neutral-500">
            · {progress.current} / {progress.total}
          </span>
        )}
        <span className="truncate text-neutral-600 flex-1">
          {progress.message && <>· {progress.message}</>}
        </span>
        {pct !== null && !isDone && !isError && (
          <div className="w-40 h-1.5 bg-neutral-200 rounded-full overflow-hidden shrink-0">
            <div
              className="h-full bg-neutral-900 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        )}
      </div>
      {progress.per_source && progress.per_source.length > 0 && !isDone && !isError && (
        <div className="px-6 pb-2 pt-0.5 flex flex-wrap gap-1.5">
          {progress.per_source.map((s) => (
            <SourceChip key={s.source} sp={s} />
          ))}
        </div>
      )}
    </div>
  );
}

function SourceChip({ sp }: { sp: SourceProgress }) {
  const label = SOURCE_LABEL[sp.source as keyof typeof SOURCE_LABEL] ?? sp.source;
  const tone =
    sp.state === "done"
      ? "bg-emerald-100 text-emerald-800 border-emerald-200"
      : sp.state === "error"
        ? "bg-red-100 text-red-800 border-red-200"
        : sp.state === "running"
          ? "bg-neutral-900 text-white border-neutral-900"
          : "bg-neutral-100 text-neutral-500 border-neutral-200";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium border",
        tone
      )}
      title={sp.error ?? sp.last_title ?? ""}
    >
      {sp.state === "running" ? (
        <Loader2 size={10} className="animate-spin" />
      ) : sp.state === "done" ? (
        <CheckCircle2 size={10} />
      ) : sp.state === "error" ? (
        <AlertCircle size={10} />
      ) : (
        <Globe2 size={10} />
      )}
      <span>{label}</span>
      <span className="tabular-nums opacity-80">{sp.count}</span>
      {sp.duration_s != null && (
        <span className="tabular-nums opacity-60">{sp.duration_s.toFixed(1)}s</span>
      )}
    </span>
  );
}
