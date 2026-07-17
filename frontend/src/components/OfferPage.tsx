import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Download,
  ExternalLink,
  Pencil,
  RefreshCw,
  Send,
  Star,
} from "lucide-react";
import {
  downloadCVPdfUrl,
  downloadLetterPdfUrl,
  generateOffer,
  getOffer,
  setFavorite,
  setOfferStatus,
} from "../api";
import type { OfferDetail as OfferDetailType } from "../types";
import { SOURCE_LABEL } from "../types";
import { CompanyCard } from "./CompanyCard";
import { InterviewPrep } from "./InterviewPrep";
import { OfferApplication } from "./OfferApplication";
import { OfferTracking } from "./OfferTracking";
import { cn, scoreColor } from "../lib/utils";

interface Props {
  offerId: number;
  onBack: () => void;
  onChanged: () => void;
  onEdit: (offerId: number) => void;
}

type Tab = "overview" | "company" | "application" | "interview" | "tracking";

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "L'offre" },
  { key: "company", label: "L'entreprise" },
  { key: "application", label: "Ma candidature" },
  { key: "interview", label: "Entretien" },
  { key: "tracking", label: "Suivi" },
];

function fmt(d?: string | null) {
  if (!d) return null;
  const dt = new Date(d);
  return isNaN(dt.getTime())
    ? d
    : dt.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
}

/** Page pleine d'une offre. Le panneau latéral fait 480 px : lisible pour un
 *  score et des badges, intenable pour une fiche entreprise ou une prépa
 *  d'entretien de 10 000 caractères. D'où les onglets, et une colonne de lecture
 *  bornée en largeur plutôt qu'un texte étalé sur tout l'écran. */
export function OfferPage({ offerId, onBack, onChanged, onEdit }: Props) {
  const [data, setData] = useState<OfferDetailType | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [generating, setGenerating] = useState(false);

  const reload = () => {
    getOffer(offerId).then(setData).catch(console.error);
  };

  useEffect(() => {
    setData(null);
    setTab("overview");
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offerId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onBack();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onBack]);

  if (!data) {
    return (
      <div className="p-8 text-body-md text-on-surface-variant">Chargement…</div>
    );
  }

  const { offer, docs } = data;
  const color = scoreColor(offer.score);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await generateOffer(offer.id);
      reload();
      onChanged();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setGenerating(false);
    }
  };

  const handleFav = async () => {
    await setFavorite(offer.id, !offer.is_favorite);
    reload();
    onChanged();
  };

  const markApplied = async () => {
    await setOfferStatus(offer.id, "applied");
    reload();
    onChanged();
  };

  return (
    <div className="flex-1 overflow-y-auto">
      {/* En-tête collant : les actions restent atteignables en bas de page */}
      <header className="sticky top-0 z-10 bg-surface-lowest border-b border-outline-variant">
        <div className="max-w-5xl mx-auto px-6 py-4">
          <div className="flex items-center gap-2 mb-3">
            <button
              onClick={onBack}
              className="inline-flex items-center gap-1.5 text-label-sm text-on-surface-variant hover:text-on-surface"
            >
              <ArrowLeft size={14} /> Retour
            </button>
            <span className="badge badge-neutral">{SOURCE_LABEL[offer.source]}</span>
            {offer.contract && <span className="badge badge-info">{offer.contract}</span>}
            {offer.salary && <span className="badge badge-neutral">{offer.salary}</span>}
            {offer.url && (
              <a
                href={offer.url}
                target="_blank"
                rel="noreferrer"
                className="ml-auto inline-flex items-center gap-1 text-label-sm text-tertiary hover:underline"
              >
                Voir l'offre d'origine <ExternalLink size={12} />
              </a>
            )}
          </div>

          <div className="flex items-start gap-4">
            <div
              className={cn(
                "shrink-0 w-16 h-16 rounded-lg flex items-center justify-center ring-1",
                color.bg,
                color.text,
                color.ring
              )}
            >
              <span className="text-headline-md tabular-nums">{offer.score}</span>
            </div>
            <div className="flex-1 min-w-0">
              <h1 className="text-headline-lg text-on-surface leading-tight">
                {offer.title}
              </h1>
              <div className="mt-1 text-body-lg text-on-surface-variant">
                {offer.company}
                {offer.location && (
                  <>
                    <span className="text-outline-variant"> · </span>
                    {offer.location}
                  </>
                )}
              </div>
            </div>
            <button
              onClick={handleFav}
              className="shrink-0 p-2 rounded text-on-surface-variant hover:text-secondary hover:bg-surface-c"
              aria-label="Favori"
            >
              <Star
                size={20}
                fill={offer.is_favorite ? "currentColor" : "none"}
                className={offer.is_favorite ? "text-secondary" : ""}
              />
            </button>
          </div>

          <div className="mt-3 flex items-center gap-2 flex-wrap">
            <button onClick={handleGenerate} disabled={generating} className="btn-primary btn-sm">
              <RefreshCw size={14} className={generating ? "animate-spin" : ""} />
              {docs ? "Régénérer" : "Générer candidature"}
            </button>
            {docs && (
              <>
                <button onClick={() => onEdit(offer.id)} className="btn-secondary btn-sm">
                  <Pencil size={14} /> Éditer
                </button>
                <a href={downloadCVPdfUrl(offer.id)} target="_blank" rel="noreferrer" className="btn-secondary btn-sm">
                  <Download size={14} /> CV PDF
                </a>
                <a href={downloadLetterPdfUrl(offer.id)} target="_blank" rel="noreferrer" className="btn-secondary btn-sm">
                  <Download size={14} /> Lettre PDF
                </a>
              </>
            )}
            {!["applied", "interview", "accepted"].includes(offer.application_status || "") && (
              <button onClick={markApplied} className="btn-success btn-sm">
                <Send size={14} /> Marquer postulé
              </button>
            )}
          </div>

          <nav className="mt-4 -mb-px flex items-center gap-1">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={cn(
                  "px-3 py-2 text-label-md border-b-2 transition-colors",
                  tab === t.key
                    ? "border-primary text-on-surface"
                    : "border-transparent text-on-surface-variant hover:text-on-surface"
                )}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-6">
        {tab === "overview" && (
          <div className="max-w-3xl space-y-6">
            {offer.reasoning && (
              <section>
                <h2 className="section-label mb-2">Pourquoi ce score</h2>
                <p className="text-body-md text-on-surface-variant leading-relaxed">
                  {offer.reasoning}
                </p>
              </section>
            )}

            {offer.skills.length > 0 && (
              <section>
                <h2 className="section-label mb-2">Compétences identifiées</h2>
                <div className="flex flex-wrap gap-1.5">
                  {offer.skills.map((s, i) => (
                    <span key={i} className="badge badge-neutral">{s}</span>
                  ))}
                </div>
              </section>
            )}

            {offer.red_flags.length > 0 && (
              <section>
                <h2 className="section-label mb-2">Points d'attention</h2>
                <ul className="space-y-1">
                  {offer.red_flags.map((r, i) => (
                    <li key={i} className="text-body-md text-on-error-container">
                      {r}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section>
              <h2 className="section-label mb-2">Infos & chronologie</h2>
              <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-2">
                {[
                  ["Source", SOURCE_LABEL[offer.source]],
                  ["Contrat", offer.contract],
                  ["Lieu", offer.location],
                  ["Salaire", offer.salary],
                  ["Publiée le", fmt(offer.posted_at)],
                  ["Trouvée le", fmt(offer.scraped_at)],
                  ["Scorée le", fmt(offer.scored_at)],
                  ["Candidature générée", docs ? fmt(docs.generated_at) || "oui" : "pas encore"],
                ]
                  .filter(([, v]) => v)
                  .map(([k, v]) => (
                    <div key={k as string}>
                      <dt className="text-label-sm text-on-surface-variant">{k}</dt>
                      <dd className="text-body-md text-on-surface">{v}</dd>
                    </div>
                  ))}
              </dl>
            </section>

            <section>
              <h2 className="section-label mb-2">Description</h2>
              <div className="text-body-md text-on-surface-variant leading-relaxed whitespace-pre-wrap">
                {offer.description}
              </div>
            </section>
          </div>
        )}

        {tab === "company" && (
          <div className="max-w-3xl">
            {offer.company ? (
              <CompanyCard offerId={offer.id} company={offer.company} />
            ) : (
              <p className="text-body-md text-on-surface-variant">
                Cette offre n'a pas de nom d'entreprise, impossible de la rechercher.
              </p>
            )}
          </div>
        )}

        {tab === "application" && (
          <OfferApplication offerId={offer.id} />
        )}

        {tab === "tracking" && (
          <OfferTracking
            offer={offer}
            onChanged={() => {
              reload();
              onChanged();
            }}
          />
        )}

        {tab === "interview" && (
          <div className="max-w-3xl">
            <InterviewPrep offerId={offer.id} title={offer.title} />
          </div>
        )}
      </div>
    </div>
  );
}
