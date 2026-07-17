import { useState } from "react";
import { AlertTriangle, Sparkles } from "lucide-react";
import { createSpontaneous } from "../api";

interface Props {
  onCreated: (offerId: number) => void;
}

/** Candidature spontanée : on recherche la boîte, l'IA en déduit la fiche de
 *  poste probable, et l'offre créée repart dans la chaîne normale (CV, lettre,
 *  éditeur, suivi). */
export function SpontaneousView({ onCreated }: Props) {
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [website, setWebsite] = useState("");
  const [location, setLocation] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    offerId: number;
    duplicate: boolean;
    cached: boolean;
    hypotheses: string[];
  } | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!company.trim() || !role.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await createSpontaneous({
        company: company.trim(),
        role: role.trim(),
        website: website.trim() || undefined,
        location: location.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      setResult({
        offerId: r.offer_id,
        duplicate: r.duplicate,
        cached: r.company_cached,
        hypotheses: r.hypotheses || [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-2xl">
      <div className="flex items-start gap-3 mb-1">
        <Sparkles size={20} className="text-tertiary mt-1 shrink-0" />
        <div>
          <h1 className="text-headline-md text-on-surface">Candidature spontanée</h1>
          <p className="mt-1 text-body-md text-on-surface-variant">
            Pour une boîte qui ne publie rien. L'IA la recherche sur le web, en déduit
            le poste le plus plausible chez eux, et crée la candidature : CV et lettre
            se génèrent ensuite comme pour n'importe quelle offre.
          </p>
        </div>
      </div>

      <form onSubmit={submit} className="mt-5 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-label-sm text-on-surface-variant">Entreprise *</span>
            <input
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="Doctolib"
              className="input h-9 w-full mt-0.5"
              required
            />
          </label>
          <label className="block">
            <span className="text-label-sm text-on-surface-variant">Poste visé *</span>
            <input
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="Chargé de projet IA"
              className="input h-9 w-full mt-0.5"
              required
            />
          </label>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-label-sm text-on-surface-variant">
              Site web <span className="text-outline">— lève les homonymes</span>
            </span>
            <input
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              placeholder="doctolib.fr"
              className="input h-9 w-full mt-0.5"
            />
          </label>
          <label className="block">
            <span className="text-label-sm text-on-surface-variant">
              Lieu <span className="text-outline">— optionnel</span>
            </span>
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Paris"
              className="input h-9 w-full mt-0.5"
            />
          </label>
        </div>

        <label className="block">
          <span className="text-label-sm text-on-surface-variant">
            Ce que tu veux y faire <span className="text-outline">— optionnel, mais ça oriente tout</span>
          </span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Automatiser leurs process internes, bosser sur leurs agents IA…"
            rows={3}
            className="input w-full mt-0.5 py-2 resize-y"
          />
        </label>

        <div className="flex items-center gap-3">
          <button type="submit" disabled={loading} className="btn-primary btn-sm">
            <Sparkles size={14} className={loading ? "animate-pulse" : ""} />
            {loading ? "Recherche et rédaction…" : "Créer la candidature"}
          </button>
          <span className="text-label-sm text-on-surface-variant">
            {loading
              ? "Ça prend ~1 min si la boîte est nouvelle."
              : "Une boîte déjà recherchée est servie du cache, sans coût."}
          </span>
        </div>
      </form>

      {error && (
        <p className="mt-4 text-body-md text-on-error-container">{error}</p>
      )}

      {result && (
        <div className="mt-5 rounded-lg border border-outline-variant bg-surface-c p-4">
          <p className="text-body-md text-on-surface">
            {result.duplicate
              ? "Cette candidature existait déjà."
              : "Candidature créée et mise en favori."}
            {result.cached && !result.duplicate && " (fiche entreprise servie du cache)"}
          </p>

          {result.hypotheses.length > 0 && (
            <div className="mt-3">
              <div className="section-label mb-1">
                Hypothèses de l'IA, à vérifier avant d'envoyer
              </div>
              <ul className="space-y-1">
                {result.hypotheses.map((h, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-1.5 text-body-md text-on-error-container"
                  >
                    <AlertTriangle size={12} className="mt-1 shrink-0" />
                    <span>{h}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button
            onClick={() => onCreated(result.offerId)}
            className="btn-primary btn-sm mt-3"
          >
            Voir dans mes favoris
          </button>
        </div>
      )}
    </div>
  );
}
