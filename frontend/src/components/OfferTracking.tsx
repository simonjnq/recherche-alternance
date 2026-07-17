import { useEffect, useState } from "react";
import { AlertTriangle, CheckSquare, Mail, Plus, Square, Trash2 } from "lucide-react";
import {
  addEvent,
  deleteEvent,
  listEvents,
  setOfferStatus,
  updateOfferTracking,
  type OfferTracking as TrackingFields,
} from "../api";
import type { EventKind, Offer, OfferEvent } from "../types";
import { APPLICATION_STATUSES, EVENT_KINDS } from "../types";
import { cn } from "../lib/utils";

const CHECKLIST_STEPS = [
  { key: "cv", label: "CV & lettre prêts" },
  { key: "applied", label: "Candidature envoyée" },
  { key: "relance", label: "Relance envoyée" },
  { key: "test", label: "Test technique" },
  { key: "entretien", label: "Entretien" },
  { key: "reponse", label: "Réponse reçue" },
];

const KIND_LABEL: Record<EventKind, string> = Object.fromEntries(
  EVENT_KINDS.map((k) => [k.key, k.label])
) as Record<EventKind, string>;

function isOverdue(date?: string | null) {
  if (!date) return false;
  return new Date(date) < new Date(new Date().toDateString());
}

/** Suivi de candidature en pleine page. Les mêmes données que le panneau
 *  latéral, mais lisibles : le panneau tassait deux dates, six cases et les
 *  notes dans 480 px. */
export function OfferTracking({
  offer,
  onChanged,
}: {
  offer: Offer;
  onChanged: () => void;
}) {
  const [fields, setFields] = useState<TrackingFields>({});
  const [checklist, setChecklist] = useState<Record<string, boolean>>({});
  const [events, setEvents] = useState<OfferEvent[]>([]);
  const [kind, setKind] = useState<EventKind>("relance");
  const [at, setAt] = useState(new Date().toISOString().slice(0, 10));
  const [note, setNote] = useState("");

  useEffect(() => {
    setFields({
      applied_at: offer.applied_at ?? "",
      follow_up_at: offer.follow_up_at ?? "",
      notes: offer.notes ?? "",
      contact: offer.contact ?? "",
    });
    setChecklist(offer.checklist ?? {});
    listEvents(offer.id).then(setEvents).catch(console.error);
  }, [offer.id]);

  const commit = async (patch?: TrackingFields) => {
    await updateOfferTracking(offer.id, patch ?? fields);
    onChanged();
  };

  const toggleCheck = (key: string) => {
    const next = { ...checklist, [key]: !checklist[key] };
    setChecklist(next);
    updateOfferTracking(offer.id, { checklist: next }).then(onChanged).catch(console.error);
  };

  const submitEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    await addEvent(offer.id, { kind, at, note: note.trim() || undefined });
    setNote("");
    setEvents(await listEvents(offer.id));
  };

  const removeEvent = async (id: number) => {
    await deleteEvent(offer.id, id);
    setEvents(await listEvents(offer.id));
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="space-y-6">
        <section>
          <h2 className="section-label mb-2">Où en est cette candidature</h2>
          <div className="flex flex-wrap gap-1.5">
            {APPLICATION_STATUSES.map((s) => (
              <button
                key={s.key}
                onClick={async () => {
                  await setOfferStatus(offer.id, s.key);
                  onChanged();
                }}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-label-md transition-colors",
                  offer.application_status === s.key
                    ? "border-primary bg-surface-c text-on-surface"
                    : "border-outline-variant text-on-surface-variant hover:text-on-surface hover:bg-surface-c"
                )}
              >
                <span className={cn("w-2 h-2 rounded-full", s.dot)} />
                {s.label}
              </button>
            ))}
          </div>
        </section>

        <section>
          <h2 className="section-label mb-2">Dates</h2>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-label-sm text-on-surface-variant">Postulé le</span>
              <input
                type="date"
                value={fields.applied_at || ""}
                onChange={(e) => setFields((f) => ({ ...f, applied_at: e.target.value }))}
                onBlur={() => commit()}
                className="input h-9 w-full mt-0.5"
              />
            </label>
            <label className="block">
              <span className="text-label-sm text-on-surface-variant">Relance prévue</span>
              <input
                type="date"
                value={fields.follow_up_at || ""}
                onChange={(e) => setFields((f) => ({ ...f, follow_up_at: e.target.value }))}
                onBlur={() => commit()}
                className="input h-9 w-full mt-0.5"
              />
            </label>
          </div>
          {isOverdue(fields.follow_up_at) && (
            <p className="mt-2 inline-flex items-center gap-1.5 text-body-md text-on-error-container">
              <AlertTriangle size={13} /> Relance en retard.
            </p>
          )}
        </section>

        <section>
          <h2 className="section-label mb-2">Étapes</h2>
          <div className="space-y-1">
            {CHECKLIST_STEPS.map((s) => (
              <button
                key={s.key}
                onClick={() => toggleCheck(s.key)}
                className="flex items-center gap-2 w-full text-left px-2 py-1.5 rounded hover:bg-surface-c text-body-md text-on-surface-variant"
              >
                {checklist[s.key] ? (
                  <CheckSquare size={15} className="text-secondary shrink-0" />
                ) : (
                  <Square size={15} className="shrink-0" />
                )}
                <span className={checklist[s.key] ? "line-through text-outline" : ""}>
                  {s.label}
                </span>
              </button>
            ))}
          </div>
        </section>

        <section>
          <h2 className="section-label mb-2">Contact</h2>
          <input
            value={fields.contact || ""}
            onChange={(e) => setFields((f) => ({ ...f, contact: e.target.value }))}
            onBlur={() => commit()}
            placeholder="prenom.nom@boite.fr"
            className="input h-9 w-full"
          />
          {fields.contact?.includes("@") && (
            <a
              href={`mailto:${fields.contact}?subject=${encodeURIComponent(
                "Candidature alternance — " + offer.title
              )}`}
              className="btn-secondary btn-sm mt-2"
            >
              <Mail size={14} /> Écrire
            </a>
          )}
        </section>

        <section>
          <h2 className="section-label mb-2">Notes</h2>
          <textarea
            value={fields.notes || ""}
            onChange={(e) => setFields((f) => ({ ...f, notes: e.target.value }))}
            onBlur={() => commit()}
            rows={8}
            placeholder="Ce que tu retiens : interlocuteur, ambiance, ce qu'ils cherchent vraiment, ce que tu dois creuser…"
            className="input w-full py-2 resize-y"
          />
        </section>
      </div>

      <div>
        <h2 className="section-label mb-2">Journal</h2>
        <form onSubmit={submitEvent} className="rounded-lg border border-outline-variant bg-surface-c p-3">
          <div className="grid grid-cols-2 gap-2">
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as EventKind)}
              className="input h-9"
            >
              {EVENT_KINDS.map((k) => (
                <option key={k.key} value={k.key}>{k.label}</option>
              ))}
            </select>
            <input
              type="date"
              value={at}
              onChange={(e) => setAt(e.target.value)}
              className="input h-9"
            />
          </div>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Détail (optionnel) : à qui, quoi, réponse obtenue…"
            className="input h-9 w-full mt-2"
          />
          <button type="submit" className="btn-secondary btn-sm mt-2">
            <Plus size={14} /> Ajouter au journal
          </button>
        </form>

        {events.length === 0 ? (
          <p className="mt-3 text-body-md text-on-surface-variant">
            Rien pour l'instant. Note ici ce que tu fais au fil de l'eau : dans trois
            semaines, tu ne te souviendras plus de qui t'a répondu quoi.
          </p>
        ) : (
          <ol className="mt-3 space-y-2">
            {events.map((ev) => (
              <li key={ev.id} className="flex items-start gap-2 group">
                <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-tertiary shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-body-md text-on-surface">
                    {KIND_LABEL[ev.kind] || ev.kind}
                    <span className="text-outline"> · </span>
                    <span className="text-on-surface-variant">
                      {new Date(ev.at).toLocaleDateString("fr-FR", {
                        day: "numeric",
                        month: "long",
                        year: "numeric",
                      })}
                    </span>
                  </div>
                  {ev.note && (
                    <p className="text-body-md text-on-surface-variant">{ev.note}</p>
                  )}
                </div>
                <button
                  onClick={() => removeEvent(ev.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded text-on-surface-variant hover:text-error hover:bg-surface-c"
                  aria-label="Supprimer"
                >
                  <Trash2 size={13} />
                </button>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
