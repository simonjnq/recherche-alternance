import { useCallback, useEffect, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { ProgressBar } from "./components/ProgressBar";
import { OffersView } from "./components/OffersView";
import { FavoritesBoard } from "./components/FavoritesBoard";
import { StatsView } from "./components/StatsView";
import { CVsView } from "./components/CVsView";
import { SettingsView } from "./components/SettingsView";
import { EditorView } from "./components/EditorView";
import {
  connectProgressWS,
  getProfile,
  getSearchStats,
  getSearchStatus,
  startSearch,
  updateProfile,
} from "./api";
import type { Profile, Progress, Source, ViewKey } from "./types";

export default function App() {
  const [view, setView] = useState<ViewKey>("offers");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [running, setRunning] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [editingOfferId, setEditingOfferId] = useState<number | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">(
    () => (localStorage.getItem("theme") as "light" | "dark") || "light"
  );
  const [overdueCount, setOverdueCount] = useState(0);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    getSearchStats()
      .then((s) => setOverdueCount(s.overdue_count ?? 0))
      .catch(() => undefined);
  }, [refreshKey]);

  useEffect(() => {
    getProfile().then(setProfile).catch(console.error);
    getSearchStatus()
      .then((s) => {
        setRunning(s.running);
        if (s.last_progress) setProgress(s.last_progress);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const disconnect = connectProgressWS((msg) => {
      setProgress(msg);
      if (msg.stage === "done" || msg.stage === "error") {
        setRunning(false);
        setRefreshKey((k) => k + 1);
      } else if (
        msg.stage === "scraping" ||
        msg.stage === "scoring" ||
        msg.stage === "generating"
      ) {
        setRunning(true);
      }
    });
    return disconnect;
  }, []);

  const handleStartSearch = useCallback(async () => {
    if (running) return;
    try {
      setRunning(true);
      await startSearch();
    } catch (e) {
      setRunning(false);
      alert(e instanceof Error ? e.message : String(e));
    }
  }, [running]);

  const handleToggleSource = useCallback(
    async (source: Source, enabled: boolean) => {
      if (!profile) return;
      const next: Profile = {
        ...profile,
        sources_enabled: { ...profile.sources_enabled, [source]: enabled },
      };
      setProfile(next);
      try {
        await updateProfile(next);
      } catch (e) {
        console.error(e);
      }
    },
    [profile]
  );

  return (
    <div className="flex h-full bg-background text-on-surface">
      <Sidebar
        view={view}
        onViewChange={setView}
        profile={profile}
        onToggleSource={handleToggleSource}
        running={running}
        onStartSearch={handleStartSearch}
        theme={theme}
        onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
        overdueCount={overdueCount}
      />
      <main className="flex-1 flex flex-col min-w-0">
        {editingOfferId !== null ? (
          <EditorView
            offerId={editingOfferId}
            onBack={() => setEditingOfferId(null)}
          />
        ) : (
          <>
            <ProgressBar progress={progress} running={running} />
            <div className="flex-1 overflow-y-auto">
              {view === "offers" && (
                <OffersView
                  favoritesOnly={false}
                  refreshKey={refreshKey}
                  onEdit={setEditingOfferId}
                />
              )}
              {view === "favorites" && (
                <FavoritesBoard
                  refreshKey={refreshKey}
                  onEdit={setEditingOfferId}
                />
              )}
              {view === "stats" && <StatsView refreshKey={refreshKey} />}
              {view === "cvs" && <CVsView />}
              {view === "settings" && (
                <SettingsView
                  profile={profile}
                  onProfileChange={setProfile}
                />
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
