import {
  Briefcase,
  FileText,
  Search,
  Settings,
  Star,
  Loader2,
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
}

const NAV: { key: ViewKey; label: string; icon: typeof Briefcase }[] = [
  { key: "offers", label: "Offres", icon: Briefcase },
  { key: "favorites", label: "Favoris", icon: Star },
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
}: Props) {
  return (
    <aside className="w-[260px] shrink-0 border-r border-neutral-200 bg-gradient-to-b from-white to-neutral-50 flex flex-col">
      <div className="h-14 px-5 flex items-center border-b border-neutral-200">
        <div className="w-7 h-7 rounded-md bg-gradient-to-br from-neutral-900 to-neutral-700 flex items-center justify-center mr-2.5 shadow-sm">
          <Search size={14} className="text-white" />
        </div>
        <span className="font-semibold text-[15px] tracking-tight">Recherche Alternance</span>
      </div>

      <nav className="p-3">
        <div className="px-2 pb-1.5 text-[11px] uppercase tracking-wide text-neutral-500 font-medium">
          Navigation
        </div>
        {NAV.map((item) => {
          const Icon = item.icon;
          const active = view === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onViewChange(item.key)}
              className={cn(
                "w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-sm transition-colors",
                active
                  ? "bg-neutral-100 text-neutral-900 font-medium"
                  : "text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900"
              )}
            >
              <Icon size={15} />
              {item.label}
            </button>
          );
        })}
      </nav>

      <div className="px-3 pb-3">
        <div className="px-2 pt-3 pb-1.5 text-[11px] uppercase tracking-wide text-neutral-500 font-medium">
          Sources
        </div>
        <div className="space-y-0.5">
          {SOURCES.map((s) => {
            const enabled = profile?.sources_enabled[s.key] ?? true;
            return (
              <label
                key={s.key}
                className="flex items-center justify-between px-2.5 py-1.5 rounded-md text-sm hover:bg-neutral-50 cursor-pointer"
              >
                <span className="text-neutral-700">{s.label}</span>
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => onToggleSource(s.key, e.target.checked)}
                  className="h-3.5 w-3.5 accent-neutral-900"
                />
              </label>
            );
          })}
        </div>
      </div>

      <div className="mt-auto p-3 border-t border-neutral-200">
        <button
          onClick={onStartSearch}
          disabled={running}
          className={cn(
            "w-full h-10 rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-all shadow-sm",
            running
              ? "bg-neutral-200 text-neutral-500 cursor-not-allowed"
              : "bg-gradient-to-br from-neutral-900 to-neutral-700 text-white hover:from-neutral-800 hover:to-neutral-600 hover:shadow-md active:scale-[0.98]"
          )}
        >
          {running ? (
            <>
              <Loader2 size={15} className="animate-spin" />
              Recherche en cours…
            </>
          ) : (
            <>
              <Search size={15} />
              Lancer la recherche
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
