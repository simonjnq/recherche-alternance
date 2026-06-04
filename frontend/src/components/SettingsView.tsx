import { useEffect, useRef, useState } from "react";
import { Plus, Trash2, Upload, X } from "lucide-react";
import {
  addLinkedIn,
  deleteProfilePhoto,
  getProfile,
  getProfilePhotoUrl,
  updateProfile,
  uploadProfilePhoto,
} from "../api";
import type { LetterStyle, Profile } from "../types";
import { LETTER_STYLES, SOURCES } from "../types";
import { cn } from "../lib/utils";

interface Props {
  profile: Profile | null;
  onProfileChange: (p: Profile) => void;
}

const CATEGORY_LABEL: Record<string, string> = {
  ia_automation: "IA / Automation",
  growth: "Growth",
  tech_builder: "Tech / Builder",
  data_product: "Data / Produit",
  combos: "Combinaisons",
};

export function SettingsView({ profile: p, onProfileChange }: Props) {
  const [profile, setProfile] = useState<Profile | null>(p);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [linkedinMsg, setLinkedinMsg] = useState<string | null>(null);
  const [photoVersion, setPhotoVersion] = useState<number>(() => Date.now());
  const [photoExists, setPhotoExists] = useState<boolean | null>(null);
  const [photoErr, setPhotoErr] = useState<string | null>(null);
  const photoInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    fetch(getProfilePhotoUrl(photoVersion), { method: "HEAD" })
      .then((r) => setPhotoExists(r.ok))
      .catch(() => setPhotoExists(false));
  }, [photoVersion]);

  useEffect(() => setProfile(p), [p]);

  useEffect(() => {
    if (!p) getProfile().then(setProfile).catch(console.error);
  }, [p]);

  if (!profile) {
    return <div className="p-6 text-sm text-neutral-500">Chargement…</div>;
  }

  const update = (patch: Partial<Profile>) =>
    setProfile({ ...profile, ...patch });

  const addKeyword = (cat: string, kw: string) => {
    const v = kw.trim();
    if (!v) return;
    const next = {
      ...profile.keywords,
      [cat]: [...(profile.keywords[cat] ?? []), v],
    };
    update({ keywords: next });
  };

  const removeKeyword = (cat: string, idx: number) => {
    const next = {
      ...profile.keywords,
      [cat]: profile.keywords[cat].filter((_, i) => i !== idx),
    };
    update({ keywords: next });
  };

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await updateProfile(profile);
      onProfileChange(profile);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const handlePhotoFile = async (file: File) => {
    setPhotoErr(null);
    try {
      await uploadProfilePhoto(file);
      setPhotoVersion(Date.now());
    } catch (e) {
      setPhotoErr(e instanceof Error ? e.message : String(e));
    } finally {
      if (photoInputRef.current) photoInputRef.current.value = "";
    }
  };

  const handlePhotoDelete = async () => {
    setPhotoErr(null);
    try {
      await deleteProfilePhoto();
      setPhotoVersion(Date.now());
      setPhotoExists(false);
    } catch (e) {
      setPhotoErr(e instanceof Error ? e.message : String(e));
    }
  };

  const handleAddLinkedin = async () => {
    setLinkedinMsg(null);
    try {
      await addLinkedIn(linkedinUrl);
      setLinkedinMsg("Offre LinkedIn ajoutée. Le scoring sera fait au prochain lancement.");
      setLinkedinUrl("");
    } catch (e) {
      setLinkedinMsg(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="p-6 max-w-3xl">
      <h1 className="text-xl font-semibold mb-1">Paramètres</h1>
      <p className="text-sm text-neutral-500 mb-6">
        Personnalise ton profil et tes critères de recherche.
      </p>

      <section className="mb-8">
        <h2 className="font-medium mb-3">Profil</h2>
        <div className="space-y-3 bg-white border border-neutral-200 rounded-xl p-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Nom">
              <input
                type="text"
                value={profile.name}
                onChange={(e) => update({ name: e.target.value })}
                className="w-full text-sm border border-neutral-200 rounded-md px-2.5 py-1.5"
              />
            </Field>
            <Field label="Localisation">
              <input
                type="text"
                value={profile.location}
                onChange={(e) => update({ location: e.target.value })}
                className="w-full text-sm border border-neutral-200 rounded-md px-2.5 py-1.5"
              />
            </Field>
            <Field label="Email">
              <input
                type="email"
                value={profile.email ?? ""}
                onChange={(e) => update({ email: e.target.value })}
                placeholder="prenom.nom@email.fr"
                className="w-full text-sm border border-neutral-200 rounded-md px-2.5 py-1.5"
              />
            </Field>
            <Field label="Téléphone">
              <input
                type="tel"
                value={profile.phone ?? ""}
                onChange={(e) => update({ phone: e.target.value })}
                placeholder="+33 6 …"
                className="w-full text-sm border border-neutral-200 rounded-md px-2.5 py-1.5"
              />
            </Field>
          </div>
          <Field label="LinkedIn">
            <input
              type="url"
              value={profile.linkedin ?? ""}
              onChange={(e) => update({ linkedin: e.target.value })}
              placeholder="linkedin.com/in/handle"
              className="w-full text-sm border border-neutral-200 rounded-md px-2.5 py-1.5"
            />
          </Field>
          <Field label="Contrats recherchés (séparés par virgule)">
            <input
              type="text"
              value={profile.contract_types.join(", ")}
              onChange={(e) =>
                update({
                  contract_types: e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
              className="w-full text-sm border border-neutral-200 rounded-md px-2.5 py-1.5"
            />
          </Field>
        </div>
      </section>

      <section className="mb-8">
        <h2 className="font-medium mb-3">Voix de la lettre</h2>
        <div className="space-y-3 bg-white border border-neutral-200 rounded-xl p-4">
          <Field label="Tagline / positionnement (1 phrase qui te résume)">
            <input
              type="text"
              value={profile.tagline ?? ""}
              onChange={(e) => update({ tagline: e.target.value })}
              placeholder="ex: Builder IA / no-code orienté growth & automatisation B2B"
              className="w-full text-sm border border-neutral-200 rounded-md px-2.5 py-1.5"
            />
          </Field>
          <Field label="Style d'écriture">
            <div className="flex flex-wrap gap-1.5">
              {LETTER_STYLES.map((s) => {
                const active = (profile.letter_style ?? "natural") === s.value;
                return (
                  <button
                    key={s.value}
                    type="button"
                    onClick={() => update({ letter_style: s.value as LetterStyle })}
                    className={cn(
                      "px-3 py-1.5 rounded-md text-sm border",
                      active
                        ? "bg-neutral-900 text-white border-neutral-900"
                        : "bg-white text-neutral-700 border-neutral-200 hover:border-neutral-400"
                    )}
                    title={s.hint}
                  >
                    {s.label}
                  </button>
                );
              })}
            </div>
            <div className="text-[11px] text-neutral-500 mt-1.5">
              {LETTER_STYLES.find((s) => s.value === (profile.letter_style ?? "natural"))?.hint}
            </div>
          </Field>
          <Field label="Réalisations signature (une par ligne — citées en priorité dans la lettre)">
            <textarea
              value={(profile.signature_achievements ?? []).join("\n")}
              onChange={(e) =>
                update({
                  signature_achievements: e.target.value
                    .split("\n")
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
              rows={4}
              placeholder={"ex: Lancé un SaaS d'agents IA orchestrés (Supabase, n8n) en prod\nAutomatisé X processus avec Power Automate → 8h gagnées/semaine"}
              className="w-full text-sm border border-neutral-200 rounded-md px-2.5 py-1.5 resize-y leading-snug"
            />
          </Field>
          <Field label="Tournures interdites (une par ligne — vide = liste par défaut)">
            <textarea
              value={(profile.forbidden_phrases ?? []).join("\n")}
              onChange={(e) =>
                update({
                  forbidden_phrases: e.target.value
                    .split("\n")
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
              rows={3}
              placeholder={"je suis passionné\nc'est avec un vif intérêt\nje serais ravi d'échanger"}
              className="w-full text-sm border border-neutral-200 rounded-md px-2.5 py-1.5 resize-y leading-snug"
            />
          </Field>
        </div>
      </section>

      <section className="mb-8">
        <h2 className="font-medium mb-3">Photo CV</h2>
        <div className="bg-white border border-neutral-200 rounded-xl p-4">
          <p className="text-sm text-neutral-500 mb-3">
            Optionnelle — intégrée dans le CV généré. PNG/JPG/WebP, 5 Mo max.
            Sans photo, les initiales de ton nom sont affichées.
          </p>
          <div className="flex items-center gap-4">
            <div className="w-24 h-24 rounded-full border-2 border-[#2d52c4] bg-neutral-100 overflow-hidden flex items-center justify-center text-neutral-400 text-xs">
              {photoExists ? (
                <img
                  src={getProfilePhotoUrl(photoVersion)}
                  alt="Photo"
                  className="w-full h-full object-cover"
                />
              ) : (
                <span>Pas de photo</span>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <input
                ref={photoInputRef}
                type="file"
                accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handlePhotoFile(f);
                }}
              />
              <button
                type="button"
                onClick={() => photoInputRef.current?.click()}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium bg-neutral-900 text-white hover:bg-neutral-800"
              >
                <Upload size={14} />
                {photoExists ? "Remplacer" : "Uploader une photo"}
              </button>
              {photoExists && (
                <button
                  type="button"
                  onClick={handlePhotoDelete}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-red-700 hover:bg-red-50"
                >
                  <Trash2 size={14} />
                  Supprimer
                </button>
              )}
            </div>
          </div>
          {photoErr && (
            <div className="mt-2 text-xs text-red-700">{photoErr}</div>
          )}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="font-medium mb-3">Mots-clés</h2>
        <div className="space-y-4 bg-white border border-neutral-200 rounded-xl p-4">
          {Object.keys(profile.keywords).map((cat) => (
            <KeywordGroup
              key={cat}
              label={CATEGORY_LABEL[cat] ?? cat}
              values={profile.keywords[cat]}
              onAdd={(kw) => addKeyword(cat, kw)}
              onRemove={(i) => removeKeyword(cat, i)}
            />
          ))}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="font-medium mb-3">Sources</h2>
        <div className="space-y-1 bg-white border border-neutral-200 rounded-xl p-4">
          {SOURCES.map((s) => (
            <label
              key={s.key}
              className="flex items-center justify-between px-1 py-1.5 text-sm"
            >
              <span>{s.label}</span>
              <input
                type="checkbox"
                checked={profile.sources_enabled[s.key] ?? true}
                onChange={(e) =>
                  update({
                    sources_enabled: {
                      ...profile.sources_enabled,
                      [s.key]: e.target.checked,
                    },
                  })
                }
                className="h-3.5 w-3.5 accent-neutral-900"
              />
            </label>
          ))}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="font-medium mb-3">Seuils</h2>
        <div className="space-y-4 bg-white border border-neutral-200 rounded-xl p-4">
          <Field label={`Score mini pour générer CV+lettre : ${profile.score_threshold_generate}`}>
            <input
              type="range"
              min={0}
              max={100}
              value={profile.score_threshold_generate}
              onChange={(e) =>
                update({ score_threshold_generate: Number(e.target.value) })
              }
              className="w-full accent-neutral-900"
            />
          </Field>
          <Field label={`Offres max par source : ${profile.max_offers_per_source}`}>
            <input
              type="range"
              min={10}
              max={100}
              step={5}
              value={profile.max_offers_per_source}
              onChange={(e) =>
                update({ max_offers_per_source: Number(e.target.value) })
              }
              className="w-full accent-neutral-900"
            />
          </Field>
        </div>
      </section>

      <section className="mb-8">
        <h2 className="font-medium mb-3">Ajouter une offre LinkedIn</h2>
        <div className="bg-white border border-neutral-200 rounded-xl p-4">
          <p className="text-sm text-neutral-500 mb-2">
            LinkedIn bloque le scraping automatique. Colle ici l'URL d'une offre
            pour l'importer manuellement.
          </p>
          <div className="flex gap-2">
            <input
              type="url"
              placeholder="https://www.linkedin.com/jobs/view/…"
              value={linkedinUrl}
              onChange={(e) => setLinkedinUrl(e.target.value)}
              className="flex-1 text-sm border border-neutral-200 rounded-md px-2.5 py-1.5"
            />
            <button
              onClick={handleAddLinkedin}
              disabled={!linkedinUrl.trim()}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium",
                linkedinUrl.trim()
                  ? "bg-neutral-900 text-white hover:bg-neutral-800"
                  : "bg-neutral-200 text-neutral-500 cursor-not-allowed"
              )}
            >
              Importer
            </button>
          </div>
          {linkedinMsg && (
            <div className="mt-2 text-xs text-neutral-600">{linkedinMsg}</div>
          )}
        </div>
      </section>

      <div className="flex items-center gap-3 sticky bottom-0 bg-neutral-50 py-3 -mx-6 px-6 border-t border-neutral-200">
        <button
          onClick={handleSave}
          disabled={saving}
          className={cn(
            "px-4 py-2 rounded-md text-sm font-medium",
            saving
              ? "bg-neutral-200 text-neutral-500 cursor-not-allowed"
              : "bg-neutral-900 text-white hover:bg-neutral-800"
          )}
        >
          {saving ? "Enregistrement…" : "Enregistrer"}
        </button>
        {saved && (
          <span className="text-sm text-emerald-700">Enregistré ✓</span>
        )}
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="text-xs text-neutral-600 mb-1">{label}</div>
      {children}
    </label>
  );
}

function KeywordGroup({
  label,
  values,
  onAdd,
  onRemove,
}: {
  label: string;
  values: string[];
  onAdd: (kw: string) => void;
  onRemove: (idx: number) => void;
}) {
  const [input, setInput] = useState("");
  return (
    <div>
      <div className="text-xs text-neutral-600 mb-1.5">{label}</div>
      <div className="flex flex-wrap gap-1.5 mb-1.5">
        {values.map((v, i) => (
          <span
            key={`${v}-${i}`}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-neutral-100 text-sm"
          >
            {v}
            <button
              onClick={() => onRemove(i)}
              className="text-neutral-400 hover:text-neutral-900"
              aria-label="Retirer"
            >
              <X size={11} />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-1.5">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && input.trim()) {
              onAdd(input);
              setInput("");
            }
          }}
          placeholder="Ajouter un mot-clé…"
          className="flex-1 text-sm border border-neutral-200 rounded-md px-2.5 py-1"
        />
        <button
          onClick={() => {
            if (input.trim()) {
              onAdd(input);
              setInput("");
            }
          }}
          className="px-2 py-1 rounded-md text-sm text-neutral-600 hover:bg-neutral-100 inline-flex items-center gap-1"
        >
          <Plus size={12} /> Ajouter
        </button>
      </div>
    </div>
  );
}
