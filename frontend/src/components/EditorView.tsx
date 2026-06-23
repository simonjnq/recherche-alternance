import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import {
  ArrowLeft,
  Bold as BoldIcon,
  Download,
  Italic as ItalicIcon,
  List as ListIcon,
  ListOrdered,
  Loader2,
  RefreshCw,
  Save,
  Sparkles,
  Strikethrough,
  UserCheck,
  X,
} from "lucide-react";
import {
  aiEditLetter,
  downloadLetterPdfUrl,
  getGeneratedLetter,
  getOffer,
  getReview,
  putGeneratedLetter,
  regenerateDoc,
  reviewOffer,
  type RecruiterReview,
} from "../api";
import type { OfferDetail } from "../types";
import { cn } from "../lib/utils";
import { CVVisualEditor } from "./CVVisualEditor";

type Tab = "cv" | "letter";

interface Props {
  offerId: number;
  onBack: () => void;
}

export function EditorView({ offerId, onBack }: Props) {
  const [data, setData] = useState<OfferDetail | null>(null);
  const [tab, setTab] = useState<Tab>("cv");
  const [review, setReview] = useState<RecruiterReview | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [improving, setImproving] = useState<"cv" | "letter" | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [reloadKey, setReloadKey] = useState(0); // force le remontage des éditeurs après régé
  const [checkedCv, setCheckedCv] = useState<Set<number>>(new Set());
  const [checkedLetter, setCheckedLetter] = useState<Set<number>>(new Set());

  useEffect(() => {
    getOffer(offerId).then(setData).catch((e) => console.error(e));
    getReview(offerId).then((r) => setReview(r.review)).catch(() => undefined);
  }, [offerId]);

  // Réinitialise les cases quand un nouvel avis arrive
  useEffect(() => {
    setCheckedCv(new Set());
    setCheckedLetter(new Set());
  }, [review]);

  const toggle = (set: Set<number>, setter: (s: Set<number>) => void, i: number) => {
    const next = new Set(set);
    next.has(i) ? next.delete(i) : next.add(i);
    setter(next);
  };

  const runReview = async () => {
    setReviewing(true);
    setPanelOpen(true);
    try {
      setReview(await reviewOffer(offerId));
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setReviewing(false);
    }
  };

  const improveDoc = async (target: "cv" | "letter") => {
    if (!review) return;
    const list = target === "cv" ? review.cv_suggestions : review.letter_suggestions;
    const checked = target === "cv" ? checkedCv : checkedLetter;
    const suggestions = list.filter((_, i) => checked.has(i));
    if (suggestions.length === 0) {
      alert("Coche au moins une correction à appliquer.");
      return;
    }
    setImproving(target);
    try {
      const r = await regenerateDoc(offerId, target, suggestions);
      setReview(r.review);
      setReloadKey((k) => k + 1); // recharge le document régénéré
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setImproving(null);
    }
  };

  const title = data?.offer.title ?? "…";
  const subtitle = data
    ? [data.offer.company, data.offer.location].filter(Boolean).join(" · ")
    : "";

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center gap-3 px-5 py-3 border-b border-outline-variant bg-surface-lowest">
        <button
          onClick={onBack}
          className="p-1 text-on-surface-variant hover:text-on-surface"
          aria-label="Retour"
        >
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm truncate">{title}</div>
          <div className="text-xs text-on-surface-variant truncate">{subtitle}</div>
        </div>
        <div className="flex gap-1 bg-surface-container rounded-md p-0.5">
          <TabBtn active={tab === "cv"} onClick={() => setTab("cv")}>
            CV
          </TabBtn>
          <TabBtn active={tab === "letter"} onClick={() => setTab("letter")}>
            Lettre
          </TabBtn>
        </div>
        <button
          onClick={review && !reviewing ? () => setPanelOpen((v) => !v) : runReview}
          disabled={reviewing}
          className="btn-primary btn-sm"
          title="Faire évaluer CV + lettre par un agent recruteur"
        >
          {reviewing ? <RefreshCw size={14} className="animate-spin" /> : <UserCheck size={14} />}
          Avis recruteur
          {review && (
            <span className="ml-1 text-[11px] opacity-90">{review.score}/100</span>
          )}
        </button>
      </header>

      <div className="flex-1 min-h-0 overflow-hidden relative">
        {data ? (
          tab === "cv" ? (
            <CVVisualEditor key={`cv-${reloadKey}`} offerId={offerId} />
          ) : (
            <LetterEditor key={`letter-${reloadKey}`} offerId={offerId} />
          )
        ) : (
          <div className="p-6 text-sm text-on-surface-variant">Chargement…</div>
        )}

        {review && panelOpen && (
          <div className="absolute top-3 right-3 z-30 w-[360px] max-h-[calc(100%-24px)] overflow-y-auto card shadow-level-3 p-4">
            <div className="flex items-center gap-2 mb-2">
              <UserCheck size={15} className="text-on-surface-variant" />
              <span className="section-label">Avis recruteur</span>
              <span
                className={
                  "badge ml-1 " +
                  (review.verdict === "entretien"
                    ? "badge-success"
                    : review.verdict === "non"
                      ? "badge-error"
                      : "badge-info")
                }
              >
                {review.verdict === "entretien"
                  ? "Convoque en entretien"
                  : review.verdict === "non"
                    ? "Ne convoque pas"
                    : "Mitigé"}
              </span>
              <span className="ml-auto text-label-md text-on-surface tabular-nums">{review.score}/100</span>
              <button onClick={() => setPanelOpen(false)} className="p-1 rounded hover:bg-surface-c" aria-label="Fermer">
                <X size={14} />
              </button>
            </div>
            {review.verdict_reason && (
              <p className="text-[13px] text-on-surface-variant mb-2">{review.verdict_reason}</p>
            )}
            {review.strengths.length > 0 && <RevList title="Points forts" items={review.strengths} tone="ok" />}
            {review.weaknesses.length > 0 && <RevList title="Faiblesses" items={review.weaknesses} tone="bad" />}

            <SuggestionGroup
              title="Corrections CV"
              items={review.cv_suggestions}
              checked={checkedCv}
              onToggle={(i) => toggle(checkedCv, setCheckedCv, i)}
              onApply={() => improveDoc("cv")}
              applying={improving === "cv"}
              applyLabel="Corriger le CV"
            />
            <SuggestionGroup
              title="Corrections lettre"
              items={review.letter_suggestions}
              checked={checkedLetter}
              onToggle={(i) => toggle(checkedLetter, setCheckedLetter, i)}
              onApply={() => improveDoc("letter")}
              applying={improving === "letter"}
              applyLabel="Corriger la lettre"
            />

            <button onClick={runReview} disabled={reviewing} className="btn-secondary btn-sm w-full mt-3">
              {reviewing ? <RefreshCw size={13} className="animate-spin" /> : <UserCheck size={13} />} Ré-évaluer
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function SuggestionGroup({
  title, items, checked, onToggle, onApply, applying, applyLabel,
}: {
  title: string;
  items: string[];
  checked: Set<number>;
  onToggle: (i: number) => void;
  onApply: () => void;
  applying: boolean;
  applyLabel: string;
}) {
  if (items.length === 0) return null;
  return (
    <div className="mt-2.5">
      <div className="text-label-sm text-on-surface-variant mb-1">{title}</div>
      <ul className="space-y-1">
        {items.map((it, i) => (
          <li key={i}>
            <label className="flex gap-1.5 text-[12px] text-on-surface cursor-pointer">
              <input
                type="checkbox"
                checked={checked.has(i)}
                onChange={() => onToggle(i)}
                className="mt-0.5 h-3.5 w-3.5 accent-[var(--tertiary)] shrink-0"
              />
              <span>{it}</span>
            </label>
          </li>
        ))}
      </ul>
      <button
        onClick={onApply}
        disabled={applying || checked.size === 0}
        className="btn-primary btn-sm w-full mt-1.5"
      >
        {applying ? <RefreshCw size={13} className="animate-spin" /> : <RefreshCw size={13} />}
        {applyLabel} ({checked.size})
      </button>
    </div>
  );
}

function RevList({ title, items, tone }: { title: string; items: string[]; tone: "ok" | "bad" | "info" }) {
  const dot = tone === "ok" ? "text-secondary" : tone === "bad" ? "text-error" : "text-tertiary";
  return (
    <div className="mt-1.5">
      <div className="text-label-sm text-on-surface-variant">{title}</div>
      <ul className="mt-0.5 space-y-0.5">
        {items.map((it, i) => (
          <li key={i} className="flex gap-1.5 text-[12px] text-on-surface">
            <span className={dot}>•</span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-3 py-1 text-xs font-medium rounded",
        active
          ? "bg-surface-lowest text-on-surface shadow-sm"
          : "text-on-surface-variant hover:text-on-surface"
      )}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------
// Letter editor — TipTap gauche, instructions IA droite
// ---------------------------------------------------------------------

function LetterEditor({ offerId }: { offerId: number }) {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [instruction, setInstruction] = useState("");
  const [applying, setApplying] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const loadedRef = useRef(false);

  const initialHtml = useMemo(
    () => (markdown !== null ? mdToHtml(markdown) : ""),
    [markdown]
  );

  const editor = useEditor(
    {
      extensions: [StarterKit],
      content: initialHtml,
      onUpdate: () => {
        if (loadedRef.current) setStatus(null);
      },
    },
    [initialHtml]
  );

  useEffect(() => {
    getGeneratedLetter(offerId)
      .then((r) => {
        setMarkdown(r.markdown);
        loadedRef.current = true;
      })
      .catch((e) => setStatus(e instanceof Error ? e.message : String(e)));
  }, [offerId]);

  const handleApply = useCallback(async () => {
    if (!instruction.trim() || !editor) return;
    setApplying(true);
    setStatus(null);
    try {
      const r = await aiEditLetter(offerId, instruction.trim());
      setMarkdown(r.markdown);
      editor.commands.setContent(mdToHtml(r.markdown));
      setInstruction("");
      setStatus("Modifié ✓");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : String(e));
    } finally {
      setApplying(false);
    }
  }, [editor, instruction, offerId]);

  const handleSave = useCallback(async () => {
    if (!editor) return;
    setSaving(true);
    setStatus(null);
    try {
      const html = editor.getHTML();
      const md = htmlToMd(html);
      await putGeneratedLetter(offerId, md);
      setMarkdown(md);
      setStatus("Enregistré ✓");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }, [editor, offerId]);

  if (markdown === null || !editor) {
    return (
      <div className="p-6 text-sm text-on-surface-variant">Chargement de la lettre…</div>
    );
  }

  return (
    <div className="flex h-full">
      <div className="flex-1 min-w-0 flex flex-col border-r border-outline-variant bg-surface-container-low">
        <div className="flex items-center gap-1 px-3 py-1.5 border-b border-outline-variant bg-surface-lowest">
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleBold().run()}
            active={editor.isActive("bold")}
            label="Gras"
          >
            <BoldIcon size={13} />
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleItalic().run()}
            active={editor.isActive("italic")}
            label="Italique"
          >
            <ItalicIcon size={13} />
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleStrike().run()}
            active={editor.isActive("strike")}
            label="Barré"
          >
            <Strikethrough size={13} />
          </ToolbarBtn>
          <div className="w-px h-4 bg-surface-highest mx-1" />
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            active={editor.isActive("bulletList")}
            label="Liste"
          >
            <ListIcon size={13} />
          </ToolbarBtn>
          <ToolbarBtn
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            active={editor.isActive("orderedList")}
            label="Liste numérotée"
          >
            <ListOrdered size={13} />
          </ToolbarBtn>
          <a
            href={downloadLetterPdfUrl(offerId)}
            className="ml-auto text-xs px-2 py-1 rounded-md border border-outline-variant hover:border-outline bg-surface-lowest inline-flex items-center gap-1"
            target="_blank"
            rel="noreferrer"
          >
            <Download size={12} /> PDF
          </a>
        </div>
        <div className="flex-1 overflow-auto p-8 bg-surface-container-low">
          <div className="max-w-[720px] mx-auto bg-surface-lowest shadow-sm rounded-md p-10 min-h-[80vh]">
            <EditorContent
              editor={editor}
              className="prose-sm max-w-none focus:outline-none [&_p]:my-2 [&_h1]:text-xl [&_h2]:text-base [&_h2]:font-semibold [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5"
            />
          </div>
        </div>
      </div>

      <aside className="w-[340px] shrink-0 flex flex-col bg-surface-lowest">
        <div className="p-4 border-b border-outline-variant">
          <label className="text-xs font-medium text-on-surface-variant mb-1.5 inline-flex items-center gap-1.5">
            <Sparkles size={12} /> Instructions pour l'IA
          </label>
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="ex: rends la lettre plus courte et plus directe, ajoute une phrase sur mes valeurs…"
            className="w-full text-sm border border-outline-variant rounded-md px-2.5 py-2 h-32 resize-none focus:border-tertiary outline-none"
          />
          <button
            onClick={handleApply}
            disabled={applying || !instruction.trim()}
            className={cn(
              "mt-2 w-full inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium",
              applying || !instruction.trim()
                ? "bg-surface-highest text-on-surface-variant cursor-not-allowed"
                : "bg-navy text-white hover:bg-[#1d2841]"
            )}
          >
            {applying ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <Sparkles size={13} />
            )}
            {applying ? "L'IA réfléchit…" : "Appliquer avec l'IA"}
          </button>
        </div>
        <div className="p-4 border-b border-outline-variant">
          <div className="text-xs font-medium text-on-surface-variant mb-1.5">Raccourcis</div>
          <div className="flex flex-wrap gap-1.5">
            <QuickBtn onClick={() => setInstruction("Rends la lettre plus courte (~250 mots) sans rien perdre de concret.")}>Plus court</QuickBtn>
            <QuickBtn onClick={() => setInstruction("Rends-la plus directe : phrases plus brèves, moins de connecteurs, aucun superlatif.")}>Plus direct</QuickBtn>
            <QuickBtn onClick={() => setInstruction("Réécris uniquement le paragraphe 1 (accroche) en partant d'un élément concret de l'offre. Ne touche pas au reste.")}>Réécrire intro</QuickBtn>
            <QuickBtn onClick={() => setInstruction("Réécris uniquement le paragraphe 2 en gardant 2 preuves max, chacune chiffrée ou nommée. Ne touche pas au reste.")}>Réécrire para 2</QuickBtn>
            <QuickBtn onClick={() => setInstruction("Réécris uniquement le dernier paragraphe (projection + CTA), 2 phrases max, concret.")}>Réécrire CTA</QuickBtn>
            <QuickBtn onClick={() => setInstruction("Supprime tous les tics : 'passionné', 'vif intérêt', 'ravi d'échanger', 'force de proposition', 'exactement l'environnement'.")}>Supprimer tics</QuickBtn>
          </div>
        </div>
        <div className="p-4 flex items-center gap-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium border border-navy bg-navy text-white hover:bg-[#1d2841] disabled:opacity-60"
          >
            <Save size={13} /> {saving ? "…" : "Enregistrer"}
          </button>
          {status && (
            <span className="text-xs text-on-surface-variant">{status}</span>
          )}
        </div>
      </aside>
    </div>
  );
}

function QuickBtn({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="px-2.5 py-1 rounded-md text-xs font-medium bg-surface-container text-on-surface hover:bg-surface-highest border border-outline-variant"
    >
      {children}
    </button>
  );
}

function ToolbarBtn({
  onClick,
  active,
  label,
  children,
}: {
  onClick: () => void;
  active: boolean;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        "p-1.5 rounded text-on-surface-variant hover:bg-surface-container",
        active && "bg-surface-highest text-on-surface"
      )}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------
// Conversion markdown ⇄ HTML (légère, suffisante pour gras/italique/listes)
// ---------------------------------------------------------------------

function mdToHtml(md: string): string {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];
  let inUl = false;
  let inOl = false;
  const closeLists = () => {
    if (inUl) {
      out.push("</ul>");
      inUl = false;
    }
    if (inOl) {
      out.push("</ol>");
      inOl = false;
    }
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      closeLists();
      continue;
    }
    if (line.startsWith("## ")) {
      closeLists();
      out.push(`<h2>${inline(line.slice(3))}</h2>`);
    } else if (line.startsWith("# ")) {
      closeLists();
      out.push(`<h1>${inline(line.slice(2))}</h1>`);
    } else if (/^\s*[-*]\s+/.test(line)) {
      if (!inUl) {
        closeLists();
        out.push("<ul>");
        inUl = true;
      }
      out.push(`<li>${inline(line.replace(/^\s*[-*]\s+/, ""))}</li>`);
    } else if (/^\s*\d+\.\s+/.test(line)) {
      if (!inOl) {
        closeLists();
        out.push("<ol>");
        inOl = true;
      }
      out.push(`<li>${inline(line.replace(/^\s*\d+\.\s+/, ""))}</li>`);
    } else {
      closeLists();
      out.push(`<p>${inline(line)}</p>`);
    }
  }
  closeLists();
  return out.join("");
}

function inline(s: string): string {
  const esc = s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return esc
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/~~([^~]+)~~/g, "<del>$1</del>");
}

function htmlToMd(html: string): string {
  const container = document.createElement("div");
  container.innerHTML = html;
  const parts: string[] = [];
  for (const node of Array.from(container.childNodes)) {
    parts.push(nodeToMd(node));
  }
  return parts.filter(Boolean).join("\n\n").trim() + "\n";
}

function nodeToMd(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) {
    return node.textContent ?? "";
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return "";
  const el = node as HTMLElement;
  const tag = el.tagName.toLowerCase();
  const inner = Array.from(el.childNodes).map(nodeToMd).join("");
  switch (tag) {
    case "h1":
      return `# ${inner}`;
    case "h2":
      return `## ${inner}`;
    case "h3":
      return `### ${inner}`;
    case "p":
      return inner;
    case "strong":
    case "b":
      return `**${inner}**`;
    case "em":
    case "i":
      return `*${inner}*`;
    case "del":
    case "s":
      return `~~${inner}~~`;
    case "br":
      return "\n";
    case "ul":
      return Array.from(el.children)
        .map((li) => `- ${nodeToMd(li).replace(/\n/g, " ")}`)
        .join("\n");
    case "ol":
      return Array.from(el.children)
        .map((li, i) => `${i + 1}. ${nodeToMd(li).replace(/\n/g, " ")}`)
        .join("\n");
    case "li":
      return inner;
    default:
      return inner;
  }
}
