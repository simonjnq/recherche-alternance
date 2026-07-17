import { useEffect, useState } from "react";
import { Gavel, Loader2 } from "lucide-react";
import {
  getGeneratedCV,
  getGeneratedLetter,
  getReview,
  reviewOffer,
  type RecruiterReview,
} from "../api";
import { cn } from "../lib/utils";

const VERDICT: Record<RecruiterReview["verdict"], { label: string; cls: string }> = {
  entretien: { label: "Il te prend en entretien", cls: "badge-success" },
  "peut-etre": { label: "Hésitant", cls: "badge-info" },
  non: { label: "Il ne te prend pas", cls: "badge-error" },
};

/** CV et lettre en vis-à-vis + verdict de l'agent recruteur. En pleine page on
 *  peut enfin les lire ensemble : dans le panneau, l'aperçu passait par une
 *  modale et le verdict était enfermé dans l'éditeur. */
export function OfferApplication({ offerId }: { offerId: number }) {
  const [cv, setCv] = useState<string | null>(null);
  const [letter, setLetter] = useState<string | null>(null);
  const [review, setReview] = useState<RecruiterReview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCv(null);
    setLetter(null);
    setReview(null);
    Promise.all([getGeneratedCV(offerId), getGeneratedLetter(offerId)])
      .then(([c, l]) => {
        setCv(c.html);
        setLetter(l.markdown);
      })
      .catch(() => setError("Candidature pas encore générée."));
    getReview(offerId)
      .then((r) => setReview(r.review))
      .catch(() => undefined);
  }, [offerId]);

  const runReview = async () => {
    setLoading(true);
    try {
      setReview(await reviewOffer(offerId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analyse impossible");
    } finally {
      setLoading(false);
    }
  };

  if (error && !cv) {
    return <p className="text-body-md text-on-surface-variant">{error}</p>;
  }

  return (
    <div className="space-y-6">
      <section>
        <div className="flex items-center gap-3 mb-2">
          <h2 className="section-label">L'avis du recruteur</h2>
          <button onClick={runReview} disabled={loading} className="btn-secondary btn-sm">
            {loading ? <Loader2 size={13} className="animate-spin" /> : <Gavel size={13} />}
            {loading ? "Analyse…" : review ? "Refaire l'analyse" : "Faire juger la candidature"}
          </button>
        </div>

        {review ? (
          <div className="rounded-lg border border-outline-variant bg-surface-c p-4">
            <div className="flex items-center gap-2">
              <span className={cn("badge", VERDICT[review.verdict]?.cls)}>
                {VERDICT[review.verdict]?.label || review.verdict}
              </span>
              <span className="text-body-md text-on-surface-variant tabular-nums">
                {review.score}/100
              </span>
            </div>
            <p className="mt-2 text-body-md text-on-surface-variant">
              {review.verdict_reason}
            </p>
            <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-4">
              {review.strengths.length > 0 && (
                <div>
                  <div className="section-label mb-1">Ce qui accroche</div>
                  <ul className="space-y-1">
                    {review.strengths.map((s, i) => (
                      <li key={i} className="text-body-md text-on-surface-variant">· {s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {review.weaknesses.length > 0 && (
                <div>
                  <div className="section-label mb-1">Ce qui coince</div>
                  <ul className="space-y-1">
                    {review.weaknesses.map((w, i) => (
                      <li key={i} className="text-body-md text-on-error-container">· {w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <p className="mt-3 text-label-sm text-on-surface-variant">
              Pour appliquer ses corrections au CV ou à la lettre, passe par l'éditeur :
              tu y coches celles que tu veux garder.
            </p>
          </div>
        ) : (
          <p className="text-body-md text-on-surface-variant">
            Un recruteur simulé lit ta candidature et dit s'il te prendrait en entretien.
          </p>
        )}
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <section className="min-w-0">
          <h2 className="section-label mb-2">CV</h2>
          {cv ? (
            <iframe
              title="CV"
              srcDoc={cv}
              className="w-full h-[800px] bg-white rounded-lg border border-outline-variant"
            />
          ) : (
            <div className="h-[800px] rounded-lg border border-outline-variant animate-pulse bg-surface-c" />
          )}
        </section>
        <section className="min-w-0">
          <h2 className="section-label mb-2">Lettre</h2>
          {letter ? (
            <div className="h-[800px] overflow-y-auto rounded-lg border border-outline-variant bg-surface-lowest p-5 text-body-md text-on-surface whitespace-pre-wrap">
              {letter}
            </div>
          ) : (
            <div className="h-[800px] rounded-lg border border-outline-variant animate-pulse bg-surface-c" />
          )}
        </section>
      </div>
    </div>
  );
}
