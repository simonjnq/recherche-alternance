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
  Save,
  Sparkles,
  Strikethrough,
} from "lucide-react";
import {
  aiEditLetter,
  downloadLetterPdfUrl,
  getGeneratedLetter,
  getOffer,
  putGeneratedLetter,
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

  useEffect(() => {
    getOffer(offerId).then(setData).catch((e) => console.error(e));
  }, [offerId]);

  const title = data?.offer.title ?? "…";
  const subtitle = data
    ? [data.offer.company, data.offer.location].filter(Boolean).join(" · ")
    : "";

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center gap-3 px-5 py-3 border-b border-neutral-200 bg-white">
        <button
          onClick={onBack}
          className="p-1 text-neutral-500 hover:text-neutral-900"
          aria-label="Retour"
        >
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm truncate">{title}</div>
          <div className="text-xs text-neutral-500 truncate">{subtitle}</div>
        </div>
        <div className="flex gap-1 bg-neutral-100 rounded-md p-0.5">
          <TabBtn active={tab === "cv"} onClick={() => setTab("cv")}>
            CV
          </TabBtn>
          <TabBtn active={tab === "letter"} onClick={() => setTab("letter")}>
            Lettre
          </TabBtn>
        </div>
      </header>

      <div className="flex-1 min-h-0 overflow-hidden">
        {data ? (
          tab === "cv" ? (
            <CVVisualEditor offerId={offerId} />
          ) : (
            <LetterEditor offerId={offerId} />
          )
        ) : (
          <div className="p-6 text-sm text-neutral-500">Chargement…</div>
        )}
      </div>
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
          ? "bg-white text-neutral-900 shadow-sm"
          : "text-neutral-600 hover:text-neutral-900"
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
      <div className="p-6 text-sm text-neutral-500">Chargement de la lettre…</div>
    );
  }

  return (
    <div className="flex h-full">
      <div className="flex-1 min-w-0 flex flex-col border-r border-neutral-200 bg-neutral-50">
        <div className="flex items-center gap-1 px-3 py-1.5 border-b border-neutral-200 bg-white">
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
          <div className="w-px h-4 bg-neutral-200 mx-1" />
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
            className="ml-auto text-xs px-2 py-1 rounded-md border border-neutral-200 hover:border-neutral-400 bg-white inline-flex items-center gap-1"
            target="_blank"
            rel="noreferrer"
          >
            <Download size={12} /> PDF
          </a>
        </div>
        <div className="flex-1 overflow-auto p-8 bg-neutral-50">
          <div className="max-w-[720px] mx-auto bg-white shadow-sm rounded-md p-10 min-h-[80vh]">
            <EditorContent
              editor={editor}
              className="prose-sm max-w-none focus:outline-none [&_p]:my-2 [&_h1]:text-xl [&_h2]:text-base [&_h2]:font-semibold [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5"
            />
          </div>
        </div>
      </div>

      <aside className="w-[340px] shrink-0 flex flex-col bg-white">
        <div className="p-4 border-b border-neutral-200">
          <label className="text-xs font-medium text-neutral-600 mb-1.5 inline-flex items-center gap-1.5">
            <Sparkles size={12} /> Instructions pour l'IA
          </label>
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="ex: rends la lettre plus courte et plus directe, ajoute une phrase sur mes valeurs…"
            className="w-full text-sm border border-neutral-200 rounded-md px-2.5 py-2 h-32 resize-none focus:border-neutral-400 outline-none"
          />
          <button
            onClick={handleApply}
            disabled={applying || !instruction.trim()}
            className={cn(
              "mt-2 w-full inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium",
              applying || !instruction.trim()
                ? "bg-neutral-200 text-neutral-500 cursor-not-allowed"
                : "bg-neutral-900 text-white hover:bg-neutral-800"
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
        <div className="p-4 border-b border-neutral-200">
          <div className="text-xs font-medium text-neutral-600 mb-1.5">Raccourcis</div>
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
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium border border-neutral-900 bg-neutral-900 text-white hover:bg-neutral-800 disabled:opacity-60"
          >
            <Save size={13} /> {saving ? "…" : "Enregistrer"}
          </button>
          {status && (
            <span className="text-xs text-neutral-600">{status}</span>
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
      className="px-2.5 py-1 rounded-md text-xs font-medium bg-neutral-100 text-neutral-700 hover:bg-neutral-200 border border-neutral-200"
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
        "p-1.5 rounded text-neutral-600 hover:bg-neutral-100",
        active && "bg-neutral-200 text-neutral-900"
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
