import { useEffect, useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, ExternalLink, RefreshCw, Search } from "lucide-react";
import { getCompany, researchCompany } from "../api";
import type { CompanyResearch } from "../types";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <h4 className="section-label mb-2">{title}</h4>
      {children}
    </div>
  );
}

/** Fiche entreprise. Chargée depuis le cache à l'ouverture (gratuit, instantané) ;
 *  la recherche web n'est lancée que si l'utilisateur la demande — elle est
 *  facturée, donc jamais déclenchée par un simple clic sur une offre. */
export function CompanyCard({ offerId, company }: { offerId: number; company: string }) {
  const [data, setData] = useState<CompanyResearch | null>(null);
  const [missing, setMissing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setData(null);
    setMissing(false);
    setError(null);
    getCompany(offerId)
      .then((r) => {
        if ("missing" in r) setMissing(true);
        else {
          setData(r);
          setOpen(true);
        }
      })
      .catch(() => setMissing(true));
  }, [offerId]);

  const launch = async (refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const r = await researchCompany(offerId, refresh);
      setData(r);
      setMissing(false);
      setOpen(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Recherche impossible");
    } finally {
      setLoading(false);
    }
  };

  if (missing && !data) {
    return (
      <Section title="L'entreprise">
        <button onClick={() => launch()} disabled={loading} className="btn-secondary btn-sm">
          <Search size={14} className={loading ? "animate-pulse" : ""} />
          {loading ? "Recherche en cours… (~50 s)" : `Se renseigner sur ${company}`}
        </button>
        {error && <p className="mt-2 text-label-sm text-error">{error}</p>}
        {loading && (
          <p className="mt-2 text-label-sm text-on-surface-variant">
            Recherche web en cours. Le résultat est gardé en mémoire : tu ne le paieras
            qu'une fois pour cette entreprise.
          </p>
        )}
      </Section>
    );
  }

  if (!data) return null;

  return (
    <Section title="L'entreprise">
      <div className="rounded-lg border border-outline-variant bg-surface-c p-3">
        <div className="flex items-start gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-body-lg text-on-surface">{data.name}</span>
              {data.confidence === "low" && (
                <span className="badge badge-error" title="L'IA n'est pas certaine d'avoir trouvé la bonne entreprise (homonymes)">
                  à vérifier
                </span>
              )}
              {data.website && (
                <a
                  href={data.website}
                  target="_blank"
                  rel="noreferrer"
                  className="text-label-sm text-tertiary hover:underline inline-flex items-center gap-0.5"
                >
                  site <ExternalLink size={10} />
                </a>
              )}
            </div>
            {data.one_liner && (
              <p className="mt-1 text-body-md text-on-surface-variant">{data.one_liner}</p>
            )}
          </div>
          <button
            onClick={() => setOpen((o) => !o)}
            className="shrink-0 p-1 rounded text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low"
            aria-label={open ? "Replier" : "Déplier"}
          >
            {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>

        <div className="mt-2 flex items-center gap-1.5 flex-wrap">
          {data.size && <span className="badge badge-neutral">{data.size}</span>}
          {data.founded && <span className="badge badge-neutral">depuis {data.founded}</span>}
        </div>

        {open && (
          <div className="mt-3 space-y-3">
            {data.activity && (
              <p className="text-body-md text-on-surface-variant">{data.activity}</p>
            )}
            {data.ai_maturity && (
              <div>
                <div className="section-label mb-1">Où ils en sont sur l'IA</div>
                <p className="text-body-md text-on-surface-variant">{data.ai_maturity}</p>
              </div>
            )}
            {data.hooks.length > 0 && (
              <div>
                <div className="section-label mb-1">Angles pour ta lettre</div>
                <ul className="space-y-1">
                  {data.hooks.map((h, i) => (
                    <li key={i} className="text-body-md text-on-surface-variant flex gap-1.5">
                      <span className="text-tertiary shrink-0">·</span>
                      <span>{h}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {data.watch_outs.length > 0 && (
              <div>
                <div className="section-label mb-1">Points de vigilance</div>
                <ul className="space-y-1">
                  {data.watch_outs.map((w, i) => (
                    <li key={i} className="text-body-md text-on-error-container flex gap-1.5">
                      <AlertTriangle size={12} className="shrink-0 mt-1" />
                      <span>{w}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {data.recent_news.length > 0 && (
              <div>
                <div className="section-label mb-1">Actualités</div>
                <ul className="space-y-1">
                  {data.recent_news.map((n, i) => (
                    <li key={i} className="text-body-md text-on-surface-variant">
                      {n.date && <span className="text-outline">{n.date} — </span>}
                      {n.title}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {data.culture_values.length > 0 && (
              <div>
                <div className="section-label mb-1">Valeurs affichées</div>
                <div className="flex flex-wrap gap-1">
                  {data.culture_values.map((v, i) => (
                    <span key={i} className="badge badge-neutral">{v}</span>
                  ))}
                </div>
              </div>
            )}
            {data.sources && data.sources.length > 0 && (
              <details className="text-label-sm">
                <summary className="cursor-pointer text-on-surface-variant hover:text-on-surface">
                  {data.sources.length} source{data.sources.length > 1 ? "s" : ""}
                </summary>
                <ul className="mt-1 space-y-0.5">
                  {data.sources.map((s, i) => (
                    <li key={i}>
                      <a href={s} target="_blank" rel="noreferrer" className="text-tertiary hover:underline break-all">
                        {s}
                      </a>
                    </li>
                  ))}
                </ul>
              </details>
            )}
            <div className="flex items-center gap-2 pt-1">
              <button onClick={() => launch(true)} disabled={loading} className="btn-secondary btn-sm">
                <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
                {loading ? "Recherche…" : "Rafraîchir"}
              </button>
              {data.researched_at && (
                <span className="text-label-sm text-outline">
                  fiche du {new Date(data.researched_at).toLocaleDateString("fr-FR")}
                </span>
              )}
            </div>
            {error && <p className="text-label-sm text-error">{error}</p>}
          </div>
        )}
      </div>
    </Section>
  );
}
