import {
  Briefcase,
  FileText,
  Search,
  Settings,
  Star,
  Loader2,
  Moon,
  Sun,
  BarChart3,
} from "lucide-react";
import type { Profile, Source, ViewKey } from "../types";
import { SOURCES } from "../types";
import { cn } from "../lib/utils";

interface Props {
  view: ViewKey;
  onViewChange: (v: ViewKey) => void;
  profile: Profile | null;
  onToggleSource: (s: Source, enabled: boolean) => void;
  running: boolean;
  onStartSearch: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  overdueCount?: number;
}

const NAV: { key: ViewKey; label: string; icon: typeof Briefcase }[] = [
  { key: "offers", label: "Offres", icon: Briefcase },
  { key: "favorites", label: "Favoris", icon: Star },
  { key: "stats", label: "Stats", icon: BarChart3 },
  { key: "cvs", label: "CVs", icon: FileText },
  { key: "settings", label: "Paramètres", icon: Settings },
];

export function Sidebar({
  view,
  onViewChange,
  profile,
  onToggleSource,
  running,
  onStartSearch,
  theme,
  onToggleTheme,
  overdueCount = 0,
}: Props) {
  return (
    <aside className="w-[260px] shrink-0 border-r border-outline-variant bg-surface-container-low flex flex-col">
      <div className="h-16 px-5 flex items-center border-b border-outline-variant">
        <div className="w-8 h-8 rounded bg-navy flex items-center justify-center mr-2.5 shadow-soft">
          <Search size={15} className="text-on-primary" />
        </div>
        <span className="text-label-md text-on-surface tracking-tight">
          Recherche Alternance
        </span>
        <button
          onClick={onToggleTheme}
          className="ml-auto p-1.5 rounded text-on-surface-variant hover:bg-surface-c hover:text-on-surface"
          title={theme === "dark" ? "Passer en clair" : "Passer en sombre"}
          aria-label="Basculer le thème"
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>

      <nav className="p-3">
        <div className="section-label px-2 pb-2">Navigation</div>
        <div className="space-y-0.5">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = view === item.key;
            return (
              <button
                key={item.key}
                onClick={() => onViewChange(item.key)}
                className={cn(
                  "w-full flex items-center gap-2.5 px-2.5 py-2 rounded text-body-md transition-colors",
                  active
                    ? "bg-surface-container-highest text-navy font-semibold"
                    : "text-on-surface-variant hover:bg-surface-c hover:text-on-surface"
                )}
              >
                <Icon size={16} className={active ? "text-tertiary" : ""} />
                {item.label}
                {item.key === "favorites" && overdueCount > 0 && (
                  <span
                    className="ml-auto badge badge-error"
                    title={`${overdueCount} relance(s) en retard`}
                  >
                    {overdueCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </nav>

      <div className="px-3 pb-3">
        <div className="section-label px-2 pt-3 pb-2">Sources</div>
        <div className="space-y-0.5">
          {SOURCES.map((s) => {
            const enabled = profile?.sources_enabled[s.key] ?? true;
            return (
              <label
                key={s.key}
                className="flex items-center justify-between px-2.5 py-1.5 rounded text-body-md text-on-surface-variant hover:bg-surface-c cursor-pointer"
              >
                <span>{s.label}</span>
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => onToggleSource(s.key, e.target.checked)}
                  className="h-4 w-4 rounded-sm accent-[var(--tertiary)]"
                />
              </label>
            );
          })}
        </div>
      </div>

      <div className="mt-auto p-3 border-t border-outline-variant">
        {profile &&
          (() => {
            const auto = ["la_bonne_alternance", "indeed", "wttj", "hellowork", "apec", "linkedin"];
            const n = auto.filter((s) => profile.sources_enabled[s as Source]).length;
            const cap = profile.max_offers_per_source || 60;
            const scoring = n * cap * 0.008;
            const gen = profile.auto_generate ? cap * 0.07 : 0; // approx si auto-génération
            const est = scoring + gen;
            return (
              <p className="text-label-sm text-on-surface-variant mb-2 text-center">
                ~{est.toFixed(1)} € / recherche{" "}
                <span className="opacity-70">(1er passage, scoring{profile.auto_generate ? " + génération" : ""})</span>
              </p>
            );
          })()}
        <button
          onClick={onStartSearch}
          disabled={running}
          className="btn-primary w-full"
        >
          {running ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Recherche en cours…
            </>
          ) : (
            <>
              <Search size={16} />
              Lancer la recherche
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
